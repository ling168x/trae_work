"""
新版微信 (Weixin 4.x / WCDB) 数据库读取器

新版微信使用 WCDB (基于 SQLite + SQLCipher 4) 加密，每个数据库有独立的 32 字节密钥。
消息表结构:
  - Name2Id: 用户名 -> hash 映射
  - Msg_<hash>: 每个聊天的消息表
  - 列: local_id, server_id, local_type, sort_seq, real_sender_id,
         create_time, status, upload_status, download_status,
         server_seq, origin_source, source, message_content,
         compress_content, packed_info_data
  - message_content 格式: "username:\n消息内容"
"""

import os
import re
import sqlite3
from datetime import datetime
from typing import Optional


# ============================================================
# 数据库打开
# ============================================================

def open_new_db(db_path: str, key: str):
    """使用 sqlcipher3 打开新版微信加密数据库"""
    import sqlcipher3
    conn = sqlcipher3.connect(db_path)
    c = conn.cursor()
    c.execute(f"PRAGMA key = \"x'{key}'\"")
    c.execute('PRAGMA cipher_page_size = 4096')
    c.execute('PRAGMA kdf_iter = 256000')
    c.execute('PRAGMA cipher_compatibility = 4')
    # 验证
    c.execute("SELECT COUNT(*) FROM sqlite_master")
    c.fetchone()
    return conn, c


# ============================================================
# 消息类型映射
# ============================================================

MSG_TYPE_MAP = {
    1: '文本',
    2: '图片',
    3: '语音',
    4: '视频',
    5: '表情',
    6: '文件',
    7: '系统消息',
    8: '链接',
    9: '红包',
    10: '转账',
    11: '位置',
    12: '名片',
    13: '小程序',
    14: '视频号',
    15: '引用',
    16: '拍一拍',
    17: '语音通话',
    18: '视频通话',
    47: '表情',
    49: '链接/小程序',
    10000: '系统消息',
    10002: '系统消息',
    436207665: '红包',
}

# 系统消息类型
SYSTEM_MSG_TYPES = {7, 10000, 10002}

# 自己发送的消息类型判断
# 在新版中，消息的 origin_source 和 status 可以判断是否是自己发的


def get_msg_type_name(msg_type: int) -> str:
    return MSG_TYPE_MAP.get(msg_type, f'未知({msg_type})')


def format_createtime(ts) -> str:
    if not ts:
        return ''
    try:
        # 新版微信时间戳是毫秒
        ts_int = int(ts)
        if ts_int > 1e12:
            ts_int = ts_int // 1000
        dt = datetime.fromtimestamp(ts_int)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return str(ts)


# ============================================================
# 读取 Name2Id 映射
# ============================================================

def read_name2id(conn) -> dict:
    """
    读取 Name2Id 表，通过 MD5(username) 计算 hash 映射。
    Name2Id 表结构: user_name (TEXT), is_session (INTEGER)
    每个 Msg_<hash> 表对应一个聊天，hash = MD5(username)
    返回 {username: hash} 和 {hash: username}
    """
    import hashlib

    c = conn.cursor()
    try:
        c.execute("SELECT user_name FROM Name2Id WHERE user_name != ''")
        rows = c.fetchall()
    except Exception:
        return {}, {}

    name_to_hash = {}
    hash_to_name = {}
    for row in rows:
        username = row[0]
        if username:
            hash_id = hashlib.md5(username.encode()).hexdigest()
            name_to_hash[username] = hash_id
            hash_to_name[hash_id] = username

    return name_to_hash, hash_to_name


# ============================================================
# 读取消息
# ============================================================

def parse_message_content(raw_content: bytes) -> str:
    """解析 message_content 字段（可能是压缩的）"""
    if raw_content is None:
        return ''
    if isinstance(raw_content, str):
        return raw_content
    if isinstance(raw_content, bytes):
        try:
            return raw_content.decode('utf-8', errors='replace')
        except Exception:
            return str(raw_content)
    return str(raw_content)


def parse_source(raw_source: bytes) -> str:
    """解析 source 字段"""
    if raw_source is None:
        return ''
    if isinstance(raw_source, str):
        return raw_source
    if isinstance(raw_source, bytes):
        try:
            return raw_source.decode('utf-8', errors='replace')
        except Exception:
            return raw_source.hex()
    return str(raw_source)


def read_msgs_from_table(conn, table_name: str, limit: int = None) -> list:
    """从单个 Msg_<hash> 表中读取消息"""
    c = conn.cursor()

    query = f'SELECT * FROM "{table_name}" ORDER BY create_time'
    if limit:
        query += f' LIMIT {limit}'

    try:
        c.execute(query)
        rows = c.fetchall()
    except Exception as e:
        print(f"  [!] 读取表 {table_name} 失败: {e}")
        return []

    # 获取列名
    c.execute(f'PRAGMA table_info("{table_name}")')
    col_names = [r[1] for r in c.fetchall()]

    messages = []
    for row in rows:
        msg = dict(zip(col_names, row))
        # 标准化字段
        msg['local_id'] = msg.get('local_id', 0)
        msg['create_time'] = msg.get('create_time', 0)
        msg['local_type'] = msg.get('local_type', 0)
        msg['server_id'] = msg.get('server_id', 0)

        # 解析消息内容
        content_raw = msg.get('message_content', '')
        content = parse_message_content(content_raw)

        # 解析 source (可能包含附加信息)
        source_raw = msg.get('source', '')
        source = parse_source(source_raw)

        msg['content'] = content
        msg['source'] = source
        msg['table_name'] = table_name

        messages.append(msg)

    return messages


def read_all_messages(conn, table_filter: str = None, limit_per_table: int = None) -> list:
    """读取所有 Msg_ 表中的消息"""
    c = conn.cursor()

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'")
    tables = [r[0] for r in c.fetchall()]

    all_messages = []
    for table_name in tables:
        if table_filter and table_filter not in table_name:
            continue
        msgs = read_msgs_from_table(conn, table_name, limit_per_table)
        if msgs:
            print(f"  [{table_name}] 读取到 {len(msgs)} 条消息")
        all_messages.extend(msgs)

    return all_messages


def read_chat_messages(conn, chat_hash: str, limit: int = None) -> list:
    """读取指定聊天的消息"""
    table_name = f'Msg_{chat_hash}'
    return read_msgs_from_table(conn, table_name, limit)


# ============================================================
# 联系人信息读取
# ============================================================

def get_chat_list(conn) -> list:
    """获取聊天列表（从 Name2Id 和 Msg 表）"""
    name_to_hash, hash_to_name = read_name2id(conn)

    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'")
    msg_tables = [r[0] for r in c.fetchall()]

    chat_list = []
    for table_name in msg_tables:
        hash_id = table_name.replace('Msg_', '')
        username = hash_to_name.get(hash_id, '')
        # 获取该聊天的消息数和最新消息时间
        try:
            c.execute(f'SELECT COUNT(*), MAX(create_time) FROM "{table_name}"')
            count, last_time = c.fetchone()
        except Exception:
            count, last_time = 0, 0

        chat_list.append({
            'hash_id': hash_id,
            'username': username,
            'table_name': table_name,
            'msg_count': count or 0,
            'last_time': last_time or 0,
            'is_chatroom': '@chatroom' in username,
        })

    # 按最新消息时间排序
    chat_list.sort(key=lambda x: x['last_time'], reverse=True)
    return chat_list


def get_contacts_from_new_db(conn) -> list:
    """从新版数据库中提取联系人列表"""
    name_to_hash, hash_to_name = read_name2id(conn)

    contacts = []
    for username, hash_id in name_to_hash.items():
        contacts.append({
            'username': username,
            'hash_id': hash_id,
            'nickname': username,  # 新版 Name2Id 中可能没有昵称
            'remark': '',
            'type': 1 if '@chatroom' in username else 0,
        })

    return contacts


# ============================================================
# 消息标准化
# ============================================================

def normalize_message(msg: dict, hash_to_name: dict = None) -> dict:
    """
    将新版消息格式标准化为与旧版兼容的格式，方便 exporter 使用。
    """
    content = msg.get('content', '')
    create_time = msg.get('create_time', 0)
    local_type = msg.get('local_type', 0)

    # 从 content 中解析发送者
    sender = '未知'
    text = content

    if ':\n' in content:
        parts = content.split(':\n', 1)
        sender = parts[0]
        text = parts[1] if len(parts) > 1 else ''

    # 判断是否是群聊消息
    chat_username = ''
    if hash_to_name:
        chat_username = hash_to_name.get(msg.get('table_name', '').replace('Msg_', ''), '')
    is_chatroom = '@chatroom' in chat_username

    # 判断是否是系统消息
    is_system = local_type in SYSTEM_MSG_TYPES

    # 判断内容是否可读文本
    # 非文本消息（图片、视频等）的 content 是二进制数据
    type_name = get_msg_type_name(local_type)
    if local_type != 1 and local_type not in SYSTEM_MSG_TYPES:
        # 非文本消息：显示类型标签
        text = f'[{type_name}]'
    elif local_type == 1:
        # 文本消息：检查是否包含可读文本
        if text and not _is_readable_text(text):
            text = f'[{type_name}]'

    normalized = {
        'CreateTime': create_time,
        'createtime': create_time,
        'Type': local_type,
        'type': local_type,
        'Content': text,
        'content': text,
        'StrContent': text,
        'strcontent': text,
        'Sender': sender,
        'sender': sender,
        'IsSender': 0,
        'issender': 0,
        'Talker': msg.get('table_name', ''),
        'talker': msg.get('table_name', ''),
        'MsgSvrID': msg.get('server_id', 0),
        '_raw': msg,
        '_table_name': msg.get('table_name', ''),
        '_is_system': is_system,
        '_is_chatroom': is_chatroom,
        '_chat_username': chat_username,
    }

    return normalized


def _is_readable_text(text: str) -> bool:
    """检查文本是否可读（非二进制乱码）"""
    if not text:
        return True
    # 统计可读字符比例
    printable = sum(1 for c in text if c.isprintable() or c in '\n\r\t')
    # 如果超过 80% 是可打印字符，认为是可读文本
    if len(text) > 0:
        ratio = printable / len(text)
        return ratio > 0.8
    return True


if __name__ == '__main__':
    # 测试
    key = '4c64d04ecd632d43eaf1cccecd944c98388da266521f19ce855e07126f7d09e7'
    db = r'D:\wechat\xwechat_files\LING827323180_96c1\db_storage\message\message_0.db'

    print("[*] 打开数据库...")
    conn, c = open_new_db(db, key)

    print("\n[*] 读取 Name2Id...")
    name_to_hash, hash_to_name = read_name2id(conn)
    print(f"  共 {len(name_to_hash)} 个映射")

    print("\n[*] 获取聊天列表...")
    chats = get_chat_list(conn)
    for chat in chats[:10]:
        time_str = format_createtime(chat['last_time'])
        print(f"  {chat['username'] or chat['hash_id']}: {chat['msg_count']} 条消息 (最后: {time_str})")

    print(f"\n[*] 读取消息 (前 5 条)...")
    msgs = read_all_messages(conn, limit_per_table=5)
    for msg in msgs[:5]:
        norm = normalize_message(msg, hash_to_name)
        print(f"  [{format_createtime(norm['CreateTime'])}] {norm['Sender']}: {norm['StrContent'][:80]}")

    conn.close()