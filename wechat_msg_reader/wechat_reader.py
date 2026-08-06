"""
WeChat 本地消息读取器
从微信 PC 版本地数据库中解密并读取聊天记录

原理:
  微信本地数据库 (MSG.db / MicroMsg.db) 使用 SQLCipher 加密,
  密钥存储在 WeChat.exe 进程内存中, 通过读取进程内存获取密钥后即可解密数据库。
"""

import os
import re
import sys
import hashlib
import sqlite3
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional


# ============================================================
# 工具函数
# ============================================================

# 自定义微信数据目录候选列表
CUSTOM_DATA_PATHS = [
    r'D:\wechat\xwechat_files',
    r'D:\WeChat Files',
    r'E:\wechat\xwechat_files',
    r'E:\WeChat Files',
]


def find_wechat_data_path(custom_path: str = None) -> Optional[str]:
    """查找微信数据目录 (支持自定义路径)"""
    # 参数传入的路径优先级最高
    if custom_path and os.path.exists(custom_path):
        return custom_path

    # 优先使用环境变量
    env_path = os.environ.get('WECHAT_DATA_PATH', '')
    if env_path and os.path.exists(env_path):
        return env_path

    # 收集所有候选路径
    candidates = []

    # 候选1: 自定义路径列表
    for p in CUSTOM_DATA_PATHS:
        if os.path.exists(p):
            candidates.append(p)

    # 候选2: 默认路径
    default_base = os.path.expandvars(r'%USERPROFILE%\Documents\WeChat Files')
    if os.path.exists(default_base):
        candidates.append(default_base)

    # 遍历候选路径, 找到包含 Msg 子目录的 wxid 目录
    for base in candidates:
        if not os.path.exists(base):
            continue
        # 检查 base 本身是否就是 wxid 目录 (直接包含 Msg)
        msg_dir = os.path.join(base, 'Msg')
        if os.path.exists(msg_dir):
            return base
        # 否则遍历子目录
        for name in os.listdir(base):
            full = os.path.join(base, name)
            if not os.path.isdir(full):
                continue
            if name in ('All Users', 'Applet', 'WMPF'):
                continue
            msg_dir = os.path.join(full, 'Msg')
            if os.path.exists(msg_dir):
                return full

    return None


def get_wxid_from_path(data_path: str) -> str:
    """从数据路径中提取 wxid"""
    return os.path.basename(data_path)


WECHAT_PROCESS_KEYWORDS = [
    'weixin', 'wechat', 'wechatApp', 'wechatplayer', 'wechatbrowser', 'wechatappex',
    '微信',  # 中文名
]

# 可能的微信 DLL 模块名称 (按优先级)
WECHAT_MODULE_NAMES = [
    'Weixin.dll',
    'Weixin.exe',
    'WeChatAppEx.exe',
    'WeChatAppEx.dll',
    'WeChatWin.dll',
    'WeChat.dll',
    'WeChat.exe',
]


def get_wechat_process_pid(verbose: bool = False) -> Optional[int]:
    """获取微信进程 PID"""
    # 方法1: tasklist (无需额外依赖, 最可靠)
    try:
        import subprocess
        result = subprocess.run(
            ['tasklist', '/NH', '/FO', 'CSV'],
            capture_output=True, text=True, timeout=10
        )
        if verbose:
            print(f"[*] tasklist 输出行数: {len(result.stdout.strip().split(chr(10)))}")

        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            parts = line.replace('"', '').split(',')
            if len(parts) >= 2:
                name = parts[0].strip().lower()
                pid_str = parts[1].strip()
                if verbose:
                    print(f"    {name} -> PID {pid_str}")
                for kw in WECHAT_PROCESS_KEYWORDS:
                    if kw.lower() in name:
                        return int(pid_str)
        if verbose:
            print("[*] tasklist 未找到匹配的微信进程")
    except Exception as e:
        if verbose:
            print(f"[!] tasklist 执行失败: {e}")

    # 方法2: psutil
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = (proc.info['name'] or '').lower()
                for kw in WECHAT_PROCESS_KEYWORDS:
                    if kw.lower() in name:
                        return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except ImportError:
        if verbose:
            print("[*] psutil 未安装")

    # 方法3: pymem
    try:
        import pymem
        # 枚举所有进程
        for proc in pymem.process.list_processes():
            try:
                name = (proc.get('name', '') or '').lower()
                for kw in WECHAT_PROCESS_KEYWORDS:
                    if kw.lower() in name:
                        return proc['pid']
            except Exception:
                continue
    except ImportError:
        if verbose:
            print("[*] pymem 未安装")

    return None


def diagnose_processes() -> list:
    """诊断: 列出所有包含 wechat 的进程"""
    found = []
    try:
        import subprocess
        result = subprocess.run(
            ['tasklist', '/NH', '/FO', 'CSV'],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            parts = line.replace('"', '').split(',')
            if len(parts) >= 2:
                name = parts[0].strip()
                pid = parts[1].strip()
                found.append({'name': name, 'pid': pid})
    except Exception as e:
        print(f"[!] tasklist 失败: {e}")
    return found


# ============================================================
# 密钥提取 (从 WeChat 进程内存中获取)
# ============================================================

def extract_key_from_memory(data_path: str) -> Optional[str]:
    """
    从 WeChat 进程内存中提取数据库密钥。
    支持新版微信 (WeChatAppEx.exe) 和旧版微信 (WeChat.exe)。
    """
    try:
        import pymem
        import pymem.process
    except ImportError:
        print("[!] 请先安装 pymem: pip install pymem")
        return None

    pid = get_wechat_process_pid()
    if not pid:
        print("[!] 未找到微信进程, 请确保微信已登录运行")
        return None

    try:
        pm = pymem.Pymem(pid)
        print(f"[*] 已连接微信进程 PID: {pid}")
    except Exception as e:
        print(f"[!] 无法连接到微信进程: {e}")
        return None

    # 收集所有微信相关模块
    modules_to_search = []
    for mod_name in WECHAT_MODULE_NAMES:
        try:
            mod = pymem.process.module_from_name(
                pm.process_handle, mod_name
            )
            if mod is not None:
                modules_to_search.append(mod)
                print(f"[*] 找到模块: {mod_name}, 基址=0x{mod.lpBaseOfDll:X}")
        except Exception:
            continue

    if not modules_to_search:
        print("[!] 未找到微信核心模块, 密钥提取失败")
        pm.close_process()
        return None

    # 搜索所有模块
    for wechat_module in modules_to_search:
        base = wechat_module.lpBaseOfDll
        size = wechat_module.SizeOfImage

        if size > 500 * 1024 * 1024:  # 跳过超大模块 (>500MB)
            continue

        # 分块读取内存
        chunk_size = 0x100000  # 1 MB
        data = bytearray()
        try:
            for offset in range(0, size, chunk_size):
                actual_size = min(chunk_size, size - offset)
                try:
                    chunk = pm.read_bytes(base + offset, actual_size)
                    data.extend(chunk)
                except Exception:
                    data.extend(b'\x00' * actual_size)
            data = bytes(data)
        except Exception:
            continue

        # 搜索数据库路径字符串 (UTF-16LE)
        db_names = ['MSG0.db', 'MSG.db', 'MicroMsg.db', 'MSG1.db',
                     'message_0.db', 'message\\message_0.db', 'contact.db']
        key = None

        for db_name in db_names:
            db_name_bytes = db_name.encode('utf-16-le')
            idx = 0
            while True:
                idx = data.find(db_name_bytes, idx)
                if idx == -1:
                    break
                start = max(0, idx - 0x1000)
                end = min(len(data), idx + 0x1000)
                nearby = data[start:end]
                key_pattern = re.compile(rb'[0-9a-fA-F]{32}')
                for match in key_pattern.finditer(nearby):
                    candidate = match.group().decode('ascii').lower()
                    if candidate == '0' * 32 or candidate == 'f' * 32:
                        continue
                    key = candidate
                    break
                if key:
                    break
                idx += len(db_name_bytes)
            if key:
                break

        if key:
            pm.close_process()
            return key

        # 方法2: 搜索重复密钥对
        key_pattern = re.compile(rb'([0-9a-fA-F]{64})')
        matches = key_pattern.findall(data)
        for match in matches:
            candidate = match.decode('ascii').lower()
            if candidate[:32] == candidate[32:]:
                key = candidate[:32]
                if key not in ('0' * 32, 'f' * 32):
                    pm.close_process()
                    return key

    pm.close_process()
    return None


def extract_key_alternative(data_path: str) -> Optional[str]:
    """
    备选方案: 通过读取 WeChat 账户信息计算密钥。
    密钥计算方式: MD5(某种组合)
    """
    wxid = get_wxid_from_path(data_path)

    # 尝试读取账户信息文件
    accinfo_path = os.path.join(data_path, 'config', 'AccInfo.dat')
    if not os.path.exists(accinfo_path):
        return None

    # 这里可以尝试从 AccInfo.dat 中解析 UIN 等信息
    # 不同版本的微信密钥生成算法不同, 以下是常见的一种
    # 注: 此方法在新版微信中可能失效
    return None


def get_db_key(data_path: str) -> Optional[str]:
    """获取数据库密钥 (自动尝试多种方法)"""
    print("[*] 正在提取数据库密钥...")

    # 方法1: 从内存中提取
    key = extract_key_from_memory(data_path)
    if key:
        print(f"[+] 成功从内存提取密钥: {key}")
        return key

    # 方法2: 备选方案
    key = extract_key_alternative(data_path)
    if key:
        print(f"[+] 通过备选方案获取密钥: {key}")
        return key

    print("[!] 自动提取密钥失败")
    return None


# ============================================================
# 数据库解密与读取
# ============================================================

def decrypt_db(db_path: str, key: str, output_path: str) -> bool:
    """
    使用 SQLCipher 解密数据库。自动尝试多种参数组合。
    """
    # 方法1: 使用 sqlcipher3 Python 包
    try:
        import sqlcipher3

        # 尝试多种参数组合
        configs = [
            # 新版微信 (SQLCipher 4): AES-256-CBC + HMAC-SHA512 + PBKDF2-HMAC-SHA512
            (4096, 256000, 4),     # 新版微信标准参数
            # 旧版微信参数
            (4096, 64000, 3),      # 常见旧版微信
            (4096, 64000, 4),
            (4096, 4000, 3),
            (1024, 64000, 3),
            (1024, 4000, 3),
            (4096, 64000, 1),
            (4096, 64000, 2),
        ]

        for page_size, kdf_iter, compat in configs:
            try:
                conn = sqlcipher3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA key = \"x'{key}'\"")
                cursor.execute(f"PRAGMA cipher_page_size = {page_size}")
                cursor.execute(f"PRAGMA kdf_iter = {kdf_iter}")
                cursor.execute(f"PRAGMA cipher_compatibility = {compat}")
                cursor.execute("SELECT COUNT(*) FROM sqlite_master")
                conn.close()
                print(f"[+] 密钥验证通过! (page_size={page_size}, kdf_iter={kdf_iter}, compat={compat})")

                # 解密并导出
                conn = sqlcipher3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA key = \"x'{key}'\"")
                cursor.execute(f"PRAGMA cipher_page_size = {page_size}")
                cursor.execute(f"PRAGMA kdf_iter = {kdf_iter}")
                cursor.execute(f"PRAGMA cipher_compatibility = {compat}")
                plain_conn = sqlite3.connect(output_path)
                cursor.execute("PRAGMA cipher_export = ''")
                conn.close()
                plain_conn.close()
                return True
            except Exception:
                try:
                    conn.close()
                except:
                    pass
                continue

        # 尝试 raw key (二进制, 不是十六进制)
        raw_key = bytes.fromhex(key)
        for page_size in [4096, 1024]:
            for kdf_iter in [64000, 4000, 256000]:
                try:
                    conn = sqlcipher3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute(f"PRAGMA key = \"x'{raw_key.hex()}'\"")
                    cursor.execute(f"PRAGMA cipher_page_size = {page_size}")
                    cursor.execute(f"PRAGMA kdf_iter = {kdf_iter}")
                    cursor.execute(f"PRAGMA cipher_default_kdf_iter = {kdf_iter}")
                    cursor.execute("SELECT COUNT(*) FROM sqlite_master")
                    conn.close()
                    print(f"[+] raw key 验证通过! (page_size={page_size}, kdf_iter={kdf_iter})")

                    conn = sqlcipher3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute(f"PRAGMA key = \"x'{raw_key.hex()}'\"")
                    cursor.execute(f"PRAGMA cipher_page_size = {page_size}")
                    cursor.execute(f"PRAGMA kdf_iter = {kdf_iter}")
                    plain_conn = sqlite3.connect(output_path)
                    cursor.execute("PRAGMA cipher_export = ''")
                    conn.close()
                    plain_conn.close()
                    return True
                except Exception:
                    try:
                        conn.close()
                    except:
                        pass
                    continue

        print("[!] 所有参数组合均验证失败")
        return False
    except ImportError:
        pass

    # 方法2: 使用 sqlcipher.exe 命令行工具
    sqlcipher_exe = shutil.which('sqlcipher.exe') or shutil.which('sqlcipher')
    if sqlcipher_exe:
        return _decrypt_with_sqlcipher_cli(db_path, key, output_path, sqlcipher_exe)

    print("[!] 未找到 sqlcipher3 包或 sqlcipher.exe, 请安装其中之一")
    print("    安装 sqlcipher3: pip install sqlcipher3")
    print("    或下载 sqlcipher.exe 并放到 PATH 中")
    return False


def _decrypt_with_sqlcipher_cli(db_path: str, key: str, output_path: str, exe: str) -> bool:
    """使用 sqlcipher 命令行工具解密"""
    try:
        # 构建 SQL 命令
        sql_cmds = f"""
PRAGMA key = "x'{key}'";
PRAGMA cipher_page_size = 4096;
PRAGMA kdf_iter = 64000;
PRAGMA cipher_hmac_algorithm = HMAC_SHA1;
PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA1;
ATTACH DATABASE '{output_path}' AS plaintext KEY '';
SELECT sqlcipher_export('plaintext');
DETACH DATABASE plaintext;
"""
        result = subprocess.run(
            [exe, db_path],
            input=sql_cmds,
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0 and os.path.exists(output_path):
            return True
        print(f"[!] sqlcipher CLI 解密失败: {result.stderr}")
        return False
    except Exception as e:
        print(f"[!] sqlcipher CLI 执行失败: {e}")
        return False


def verify_key(db_path: str, key: str) -> bool:
    """验证密钥是否正确"""
    try:
        import sqlcipher3
        conn = sqlcipher3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA key = \"x'{key}'\"")
        cursor.execute("PRAGMA cipher_page_size = 4096")
        cursor.execute("PRAGMA kdf_iter = 64000")
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA1")
        cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA1")
        cursor.execute("SELECT COUNT(*) FROM sqlite_master")
        conn.close()
        return True
    except ImportError:
        pass
    except Exception:
        return False

    # 备选: 使用 sqlcipher CLI
    sqlcipher_exe = shutil.which('sqlcipher.exe') or shutil.which('sqlcipher')
    if sqlcipher_exe:
        try:
            sql = f"PRAGMA key = \"x'{key}'\"; SELECT COUNT(*) FROM sqlite_master;"
            result = subprocess.run(
                [sqlcipher_exe, db_path],
                input=sql,
                capture_output=True,
                text=True,
                timeout=30
            )
            return 'Error' not in result.stdout
        except Exception:
            pass

    return False


# ============================================================
# 消息查询
# ============================================================

def get_contacts(decrypted_db_path: str) -> list:
    """从解密后的数据库中获取联系人列表 (兼容新旧版本)"""
    conn = sqlite3.connect(decrypted_db_path)
    cursor = conn.cursor()

    contacts = []
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        # 尝试多种可能的联系人表名
        table_candidates = [
            ('Contact', ['UserName', 'NickName', 'Remark', 'Type']),
            ('rcontact', ['username', 'nickname', 'alias', 'type']),
            ('contact', ['UserName', 'NickName', 'Remark', 'Type']),
            ('contact', ['username', 'nickname', 'alias', 'type']),
            ('ContactHeadImgUrl', []),  # 跳过
            ('ChatRoom', ['UserName', 'NickName', 'Remark', 'Type']),
        ]

        for table_name, cols in table_candidates:
            if table_name in tables:
                try:
                    # 尝试获取列名
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    col_names = [row[1].lower() for row in cursor.fetchall()]

                    # 找到合适的列
                    username_col = next((c for c in col_names if 'user' in c and 'name' in c), None)
                    nickname_col = next((c for c in col_names if 'nick' in c or 'nickname' in c), None)
                    remark_col = next((c for c in col_names if 'remark' in c or 'alias' in c), None)
                    type_col = next((c for c in col_names if 'type' in c), None)

                    if not username_col:
                        continue

                    select_cols = [username_col]
                    if nickname_col:
                        select_cols.append(nickname_col)
                    else:
                        select_cols.append('""')
                    if remark_col:
                        select_cols.append(remark_col)
                    else:
                        select_cols.append('""')
                    if type_col:
                        select_cols.append(type_col)
                    else:
                        select_cols.append('0')

                    cols_str = ', '.join(select_cols)
                    cursor.execute(f"SELECT {cols_str} FROM {table_name}")
                    for row in cursor.fetchall():
                        contacts.append({
                            'username': row[0] or '',
                            'nickname': row[1] or '',
                            'remark': row[2] or '',
                            'type': row[3] or 0
                        })
                    break  # 找到合适的表就停止
                except Exception:
                    continue
    except Exception as e:
        print(f"[!] 读取联系人失败: {e}")
    finally:
        conn.close()

    return contacts


def get_chat_messages(decrypted_db_path: str, chat_id: str = None, limit: int = 1000) -> list:
    """
    从解密后的 MSG 数据库中读取聊天记录 (兼容新旧版本)。
    """
    conn = sqlite3.connect(decrypted_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    messages = []
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        msg_table = None
        for t in ['MSG', 'message', 'Chat_', 'msg']:
            if t in tables:
                msg_table = t
                break

        if not msg_table:
            for t in tables:
                if 'msg' in t.lower() or 'chat' in t.lower():
                    msg_table = t
                    break

        if not msg_table:
            print(f"[!] 未找到消息表, 可用表: {tables}")
            conn.close()
            return messages

        # 自动检测列名
        cursor.execute(f"PRAGMA table_info({msg_table})")
        col_info = cursor.fetchall()
        col_names = [row[1].lower() for row in col_info]

        # 找到关键列
        talker_col = next((c for c in col_names if c in ('talker', 'talkerid')), None)
        if not talker_col:
            talker_col = next((c for c in col_names if 'talk' in c), None)
        time_col = next((c for c in col_names if c in ('createtime', 'createts', 'time')), None)
        if not time_col:
            time_col = next((c for c in col_names if 'time' in c or 'create' in c), None)

        if not talker_col or not time_col:
            # 回退到 SELECT *
            print(f"[*] 表 {msg_table} 列名: {col_names}, 使用 SELECT *")
            if chat_id:
                # 尝试定位 talker 列
                cursor.execute(f"SELECT * FROM {msg_table} LIMIT 1")
                row = cursor.fetchone()
                if row:
                    print(f"[*] 示例行: {dict(row)}")

            conn.close()
            return messages

        # 构建查询
        if chat_id:
            query = f"SELECT * FROM {msg_table} WHERE {talker_col} = ? ORDER BY {time_col} DESC LIMIT ?"
            cursor.execute(query, (chat_id, limit))
        else:
            query = f"SELECT * FROM {msg_table} ORDER BY {time_col} DESC LIMIT ?"
            cursor.execute(query, (limit,))

        for row in cursor.fetchall():
            msg = dict(row)
            # 标准化字段名 (兼容新旧版本)
            if 'MsgSvrID' in msg:
                msg['CreateTime'] = msg.get('CreateTime', msg.get('CreateTs', 0))
            messages.append(msg)

    except Exception as e:
        print(f"[!] 读取消息失败: {e}")
    finally:
        conn.close()

    return messages


def get_chatrooms(decrypted_db_path: str) -> list:
    """获取群聊列表"""
    contacts = get_contacts(decrypted_db_path)
    chatrooms = [c for c in contacts if '@chatroom' in c.get('username', '')]
    return chatrooms


def get_chatroom_members(decrypted_db_path: str, chatroom_id: str) -> list:
    """获取群聊成员"""
    conn = sqlite3.connect(decrypted_db_path)
    cursor = conn.cursor()

    members = []
    try:
        cursor.execute(
            "SELECT UserName, NickName, DisplayName FROM ChatRoomMember WHERE ChatRoomName = ?",
            (chatroom_id,)
        )
        for row in cursor.fetchall():
            members.append({
                'username': row[0],
                'nickname': row[1] or '',
                'display_name': row[2] or ''
            })
    except Exception:
        pass
    finally:
        conn.close()

    return members


# ============================================================
# 数据库路径适配 (兼容新旧版本微信)
# ============================================================

def get_msg_dir(data_path: str) -> str:
    """获取消息数据库目录 (兼容新旧版本)"""
    # 新版微信: db_storage/message/
    new_path = os.path.join(data_path, 'db_storage', 'message')
    if os.path.exists(new_path):
        return new_path
    # 旧版微信: Msg/
    old_path = os.path.join(data_path, 'Msg')
    if os.path.exists(old_path):
        return old_path
    return None


def get_contact_db_path(data_path: str) -> str:
    """获取联系人数据库路径"""
    # 新版: db_storage/contact/contact.db
    new_path = os.path.join(data_path, 'db_storage', 'contact', 'contact.db')
    if os.path.exists(new_path):
        return new_path
    # 旧版: Msg/MicroMsg.db
    old_path = os.path.join(data_path, 'Msg', 'MicroMsg.db')
    if os.path.exists(old_path):
        return old_path
    return None


def get_message_db_paths(data_path: str) -> list:
    """获取所有消息数据库路径列表"""
    msg_dir = get_msg_dir(data_path)
    if not msg_dir:
        return []

    db_files = []
    if os.path.isdir(msg_dir):
        for f in os.listdir(msg_dir):
            # 新版微信: message_0.db, message_1.db, ...
            # 旧版微信: MSG0.db, MSG1.db, ...
            if f.endswith('.db'):
                # 过滤掉非消息数据库 (media, biz, fts, resource, weclaw)
                name_lower = f.lower()
                if any(kw in name_lower for kw in ['media', 'biz', 'fts', 'resource', 'weclaw']):
                    continue
                db_files.append(os.path.join(msg_dir, f))

    return sorted(db_files)


def scan_databases(data_path: str) -> dict:
    """扫描数据目录中的所有数据库文件"""
    dbs = {}

    # 新版微信: db_storage/ 目录
    db_storage = os.path.join(data_path, 'db_storage')
    if os.path.exists(db_storage):
        for root, dirs, files in os.walk(db_storage):
            for f in files:
                if f.endswith('.db'):
                    full_path = os.path.join(root, f)
                    relative = os.path.relpath(full_path, data_path)
                    dbs[relative] = full_path

    # 旧版微信: Msg/ 目录
    msg_dir = os.path.join(data_path, 'Msg')
    if os.path.exists(msg_dir):
        for root, dirs, files in os.walk(msg_dir):
            for f in files:
                if f.endswith('.db') and 'Multi' not in root:
                    full_path = os.path.join(root, f)
                    relative = os.path.relpath(full_path, msg_dir)
                    dbs[relative] = full_path

    return dbs


if __name__ == '__main__':
    # 测试用
    data_path = find_wechat_data_path()
    if data_path:
        print(f"微信数据目录: {data_path}")
        dbs = scan_databases(data_path)
        print(f"找到 {len(dbs)} 个数据库文件:")
        for name in dbs:
            print(f"  {name}")
    else:
        print("未找到微信数据目录")