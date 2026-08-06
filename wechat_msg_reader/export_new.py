"""
新版微信消息导出工具
直接使用已知密钥解密并导出聊天记录

用法:
  python export_new.py                          # 交互式选择聊天
  python export_new.py --list                   # 列出所有聊天
  python export_new.py --export <username>      # 导出指定聊天
  python export_new.py --export-all             # 导出全部聊天
  python export_new.py --key <hex_key>          # 手动指定密钥
"""

import os
import sys
import argparse
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from new_reader import (
    open_new_db, get_chat_list, read_all_messages,
    read_chat_messages, normalize_message, format_createtime,
    get_msg_type_name, read_name2id,
)
from exporter import export_to_html, export_to_csv, export_to_txt, export_to_xlsx


# 默认配置
DEFAULT_KEY = '4c64d04ecd632d43eaf1cccecd944c98388da266521f19ce855e07126f7d09e7'
DEFAULT_DB_DIR = r'D:\wechat\xwechat_files\LING827323180_96c1\db_storage\message'


def find_db_files(db_dir: str) -> list:
    """查找所有 message_*.db 文件"""
    db_files = []
    if os.path.isdir(db_dir):
        for f in os.listdir(db_dir):
            if f.startswith('message_') and f.endswith('.db'):
                db_files.append(os.path.join(db_dir, f))
    return sorted(db_files)


def export_chat(db_paths: list, key: str, username: str, output_dir: str, fmt: str, limit: int):
    """导出指定聊天的消息"""
    all_msgs = []
    hash_to_name_all = {}

    for db_path in db_paths:
        print(f"[*] 读取 {os.path.basename(db_path)}...")
        try:
            conn, c = open_new_db(db_path, key)
        except Exception as e:
            print(f"  [!] 打开失败: {e}")
            continue

        name_to_hash, hash_to_name = read_name2id(conn)
        hash_to_name_all.update(hash_to_name)

        if username in name_to_hash:
            chat_hash = name_to_hash[username]
            msgs = read_chat_messages(conn, chat_hash, limit)
            if msgs:
                print(f"  [+] 找到 {len(msgs)} 条消息 (表: Msg_{chat_hash})")
                all_msgs.extend(msgs)
        else:
            # 尝试在所有表中搜索
            for chat_hash, name in hash_to_name.items():
                if name == username:
                    msgs = read_chat_messages(conn, chat_hash, limit)
                    if msgs:
                        print(f"  [+] 找到 {len(msgs)} 条消息 (表: Msg_{chat_hash})")
                        all_msgs.extend(msgs)
                    break

        conn.close()

    if not all_msgs:
        print(f"[!] 未找到 {username} 的聊天记录")
        return

    # 标准化消息
    normalized = [normalize_message(m, hash_to_name_all) for m in all_msgs]
    normalized.sort(key=lambda m: m.get('CreateTime', 0))

    # 导出
    os.makedirs(output_dir, exist_ok=True)
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    safe_name = username.replace('@', '_').replace(':', '_')
    filename = f"chat_{safe_name}_{timestamp}.{fmt}"
    output_path = os.path.join(output_dir, filename)

    if fmt == 'html':
        export_to_html(normalized, output_path, title=f"聊天记录 - {username}")
    elif fmt == 'csv':
        export_to_csv(normalized, output_path)
    elif fmt == 'txt':
        export_to_txt(normalized, output_path)
    elif fmt == 'xlsx':
        export_to_xlsx(normalized, output_path, title=f"聊天记录 - {username}")

    print(f"\n[+] 导出完成: {output_path}")
    print(f"[+] 共 {len(normalized)} 条消息")

    if fmt == 'html':
        try:
            os.startfile(output_path)
        except Exception:
            pass


def export_all(db_paths: list, key: str, output_dir: str, fmt: str, limit: int):
    """导出全部聊天记录"""
    all_msgs = []
    hash_to_name_all = {}

    for db_path in db_paths:
        print(f"[*] 读取 {os.path.basename(db_path)}...")
        try:
            conn, c = open_new_db(db_path, key)
        except Exception as e:
            print(f"  [!] 打开失败: {e}")
            continue

        name_to_hash, hash_to_name = read_name2id(conn)
        hash_to_name_all.update(hash_to_name)

        msgs = read_all_messages(conn, limit_per_table=limit)
        if msgs:
            print(f"  [+] 找到 {len(msgs)} 条消息")
            all_msgs.extend(msgs)

        conn.close()

    if not all_msgs:
        print("[!] 未找到任何消息")
        return

    # 标准化消息
    normalized = [normalize_message(m, hash_to_name_all) for m in all_msgs]
    normalized.sort(key=lambda m: m.get('CreateTime', 0))

    # 导出
    os.makedirs(output_dir, exist_ok=True)
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    filename = f"all_messages_{timestamp}.{fmt}"
    output_path = os.path.join(output_dir, filename)

    if fmt == 'html':
        export_to_html(normalized, output_path, title="全部聊天记录")
    elif fmt == 'csv':
        export_to_csv(normalized, output_path)
    elif fmt == 'txt':
        export_to_txt(normalized, output_path)
    elif fmt == 'xlsx':
        export_to_xlsx(normalized, output_path, title="全部聊天记录")

    print(f"\n[+] 导出完成: {output_path}")
    print(f"[+] 共 {len(normalized)} 条消息")

    if fmt == 'html':
        try:
            os.startfile(output_path)
        except Exception:
            pass


def list_chats(db_paths: list, key: str):
    """列出所有聊天"""
    all_chats = {}

    for db_path in db_paths:
        print(f"[*] 读取 {os.path.basename(db_path)}...")
        try:
            conn, c = open_new_db(db_path, key)
        except Exception as e:
            print(f"  [!] 打开失败: {e}")
            continue

        chats = get_chat_list(conn)
        for chat in chats:
            username = chat['username'] or chat['hash_id']
            if username not in all_chats or chat['msg_count'] > all_chats[username]['msg_count']:
                all_chats[username] = chat

        conn.close()

    if not all_chats:
        print("[!] 未找到任何聊天")
        return

    print(f"\n聊天列表 (共 {len(all_chats)} 个):")
    print("=" * 70)

    # 分类显示
    chatrooms = []
    individuals = []
    for username, chat in all_chats.items():
        if chat['is_chatroom']:
            chatrooms.append(chat)
        else:
            individuals.append(chat)

    if chatrooms:
        print(f"\n[群聊] ({len(chatrooms)} 个):")
        print("-" * 70)
        for i, chat in enumerate(chatrooms, 1):
            time_str = format_createtime(chat['last_time'])
            print(f"  {i:3d}. {chat['username']}")
            print(f"       消息数: {chat['msg_count']}, 最后消息: {time_str}")

    if individuals:
        print(f"\n[个人聊天] ({len(individuals)} 个):")
        print("-" * 70)
        for i, chat in enumerate(individuals, 1):
            time_str = format_createtime(chat['last_time'])
            print(f"  {i:3d}. {chat['username']}")
            print(f"       消息数: {chat['msg_count']}, 最后消息: {time_str}")


def interactive(db_paths: list, key: str):
    """交互式模式"""
    all_chats = {}
    hash_to_name_all = {}

    for db_path in db_paths:
        try:
            conn, c = open_new_db(db_path, key)
        except Exception:
            continue
        name_to_hash, hash_to_name = read_name2id(conn)
        hash_to_name_all.update(hash_to_name)
        chats = get_chat_list(conn)
        for chat in chats:
            username = chat['username'] or chat['hash_id']
            if username not in all_chats or chat['msg_count'] > all_chats[username]['msg_count']:
                all_chats[username] = chat
        conn.close()

    if not all_chats:
        print("[!] 未找到任何聊天")
        return

    # 先显示群聊
    chatrooms = [(u, c) for u, c in all_chats.items() if c['is_chatroom']]
    individuals = [(u, c) for u, c in all_chats.items() if not c['is_chatroom']]

    items = chatrooms + individuals

    print(f"\n聊天列表 (共 {len(items)} 个):")
    print("-" * 60)
    for i, (username, chat) in enumerate(items, 1):
        tag = "[群]" if chat['is_chatroom'] else "[私]"
        time_str = format_createtime(chat['last_time'])
        print(f"  [{i:3d}] {tag} {username}")
        print(f"        消息数: {chat['msg_count']}, 最后: {time_str}")
    print(f"  [0]    导出全部")
    print("-" * 60)

    try:
        choice = input("\n请选择要导出的聊天 (输入编号): ").strip()
        choice = int(choice)
    except (ValueError, EOFError):
        print("[!] 无效输入")
        return

    if choice == 0:
        export_all(db_paths, key, 'exports', 'html', None)
    elif 1 <= choice <= len(items):
        username, chat = items[choice - 1]

        print("\n导出格式:")
        print("  [1] HTML (推荐)")
        print("  [2] CSV")
        print("  [3] TXT")
        print("  [4] Excel (xlsx)")
        fmt_choice = input("请选择格式 (默认1): ").strip() or '1'
        fmt_map = {'1': 'html', '2': 'csv', '3': 'txt', '4': 'xlsx'}
        fmt = fmt_map.get(fmt_choice, 'html')

        export_chat(db_paths, key, username, 'exports', fmt, None)
    else:
        print("[!] 无效选择")


def main():
    parser = argparse.ArgumentParser(description='新版微信消息导出工具')
    parser.add_argument('--list', action='store_true', help='列出所有聊天')
    parser.add_argument('--export', type=str, metavar='USERNAME', help='导出指定聊天')
    parser.add_argument('--export-all', action='store_true', help='导出全部聊天')
    parser.add_argument('--key', type=str, help='数据库密钥 (64位十六进制)')
    parser.add_argument('--db-dir', type=str, help='消息数据库目录')
    parser.add_argument('--format', type=str, choices=['html', 'csv', 'txt', 'xlsx'],
                        default='html', help='导出格式 (默认: html)')
    parser.add_argument('--output', type=str, default='exports', help='输出目录')
    parser.add_argument('--limit', type=int, help='限制每个聊天的消息数')

    args = parser.parse_args()

    key = args.key or DEFAULT_KEY
    db_dir = args.db_dir or DEFAULT_DB_DIR

    print("=" * 50)
    print("  新版微信消息导出工具")
    print("=" * 50)

    db_paths = find_db_files(db_dir)
    if not db_paths:
        print(f"[!] 未找到数据库文件: {db_dir}")
        print("[*] 请使用 --db-dir 指定正确的目录")
        return

    print(f"[*] 数据库目录: {db_dir}")
    print(f"[*] 找到 {len(db_paths)} 个数据库文件\n")

    if args.list:
        list_chats(db_paths, key)
    elif args.export:
        export_chat(db_paths, key, args.export, args.output, args.format, args.limit)
    elif args.export_all:
        export_all(db_paths, key, args.output, args.format, args.limit)
    else:
        interactive(db_paths, key)


if __name__ == '__main__':
    main()