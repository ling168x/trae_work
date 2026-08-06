"""
WeChat 消息读取与导出工具
============================
用法:
  python main.py                    # 交互式模式
  python main.py --list-db          # 列出所有数据库
  python main.py --list-chatrooms   # 列出所有群聊
  python main.py --export <chat_id> # 导出指定聊天记录
  python main.py --key <key>        # 手动指定密钥
"""

import os
import sys
import argparse
import time

# 将当前目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wechat_reader import (
    find_wechat_data_path,
    get_wxid_from_path,
    get_db_key,
    get_wechat_process_pid,
    diagnose_processes,
    verify_key,
    decrypt_db,
    get_contacts,
    get_chatrooms,
    get_chat_messages,
    get_contact_db_path,
    get_message_db_paths,
    get_msg_dir,
    scan_databases,
)
from exporter import (
    export_messages,
    build_contacts_map,
    get_content,
    format_timestamp,
    get_msg_type_name,
    get_sender_name,
)


def print_banner():
    print("""
╔══════════════════════════════════════════╗
║     WeChat Message Reader v1.0           ║
║     微信本地消息读取与导出工具             ║
╚══════════════════════════════════════════╝
""")


def ensure_wechat_running():
    """确保微信正在运行"""
    print("[*] 正在检测微信进程...")
    pid = get_wechat_process_pid(verbose=True)
    if not pid:
        print("\n[!] 未检测到微信进程")
        print("[*] 请确认以下条件:")
        print("    1. 微信 PC 版已登录运行 (不是网页版)")
        print("    2. 以管理员权限运行此工具 (右键 run.bat → 以管理员身份运行)")
        print("\n[*] 也可以运行诊断命令查看所有进程:")
        print("    python main.py --diagnose")
        return False
    print(f"\n[+] 检测到微信进程 PID: {pid}")
    return True


def cmd_diagnose(args):
    """诊断模式: 列出所有进程, 帮助排查问题"""
    print_banner()
    print("=" * 55)
    print("  诊断模式 - 列出系统中的所有进程")
    print("  请查找名称中包含 'wechat' 或 '微信' 的进程")
    print("=" * 55)
    print()

    all_procs = diagnose_processes()
    wechat_procs = []
    other_procs = []

    for p in all_procs:
        name_lower = p['name'].lower()
        is_wechat = False
        for kw in ['wechat', '微信']:
            if kw.lower() in name_lower:
                is_wechat = True
                break
        if is_wechat:
            wechat_procs.append(p)
        else:
            other_procs.append(p)

    if wechat_procs:
        print(f"[+] 找到 {len(wechat_procs)} 个微信相关进程:")
        for p in wechat_procs:
            print(f"    PID: {p['pid']:>8s}  名称: {p['name']}")
    else:
        print("[!] 未找到任何微信相关进程!")
        print()
        print("[*] 可能的原因:")
        print("    1. 微信 PC 版没有运行")
        print("    2. 微信的进程名不包含 'wechat' (可能被改名)")
        print("    3. 权限不足, 无法读取进程列表")
        print()
        print("[*] 以下是系统中所有进程名称 (仅显示前 50 个):")
        print()
        for i, p in enumerate(other_procs[:50], 1):
            print(f"    {i:3d}. PID: {p['pid']:>8s}  {p['name']}")
        if len(other_procs) > 50:
            print(f"    ... 还有 {len(other_procs) - 50} 个进程")
        print()
        print("[*] 请查找其中是否有微信相关进程, 反馈给我以添加支持")

    print()
    print("[*] 数据目录检查:")
    data_path = find_wechat_data_path(args.data_path)
    print(f"    WeChat Files 目录: {data_path or '未找到'}")
    base = os.path.expandvars(r'%USERPROFILE%\Documents\WeChat Files')
    print(f"    检查路径: {base}")
    print(f"    路径存在: {os.path.exists(base)}")
    if os.path.exists(base):
        print(f"    目录内容: {os.listdir(base)}")


def cmd_list_db(args):
    """列出所有数据库文件"""
    data_path = find_wechat_data_path(args.data_path)
    if not data_path:
        print("[!] 未找到微信数据目录")
        return

    print(f"[*] 微信数据目录: {data_path}")
    dbs = scan_databases(data_path)
    print(f"\n找到 {len(dbs)} 个数据库文件:\n")
    for name, path in sorted(dbs.items()):
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"  {name}  ({size_mb:.1f} MB)")


def cmd_list_chatrooms(args):
    """列出所有群聊"""
    data_path = find_wechat_data_path(args.data_path)
    if not data_path:
        print("[!] 未找到微信数据目录")
        return

    print("[*] 正在获取密钥并解密联系人数据库...")
    key = args.key if args.key else get_db_key(data_path)
    if not key:
        print("[!] 未能获取密钥, 请使用 --key 手动指定")
        return

    contact_db = get_contact_db_path(data_path)
    if not contact_db:
        print("[!] 未找到联系人数据库")
        return

    plain_db = os.path.join(data_path, 'contact_plain.db')
    if not decrypt_db(contact_db, key, plain_db):
        print("[!] 数据库解密失败")
        return

    print("[*] 正在读取群聊列表...")
    chatrooms = get_chatrooms(plain_db)
    print(f"\n找到 {len(chatrooms)} 个群聊:\n")
    for i, cr in enumerate(chatrooms, 1):
        name = cr.get('nickname') or cr.get('remark') or cr.get('username', '')
        print(f"  {i:3d}. {name}")
        print(f"       ID: {cr.get('username', '')}")
        print()

    os.remove(plain_db)


def cmd_export(args):
    """导出指定聊天记录"""
    data_path = find_wechat_data_path(args.data_path)
    if not data_path:
        print("[!] 未找到微信数据目录")
        return

    print("[*] 正在获取密钥...")
    key = args.key if args.key else get_db_key(data_path)
    if not key:
        print("[!] 未能获取密钥, 请使用 --key 手动指定")
        return

    # 获取联系人信息
    print("[*] 正在解密联系人数据库...")
    contact_db = get_contact_db_path(data_path)
    contacts_map = {}
    if contact_db:
        plain_contact = os.path.join(data_path, 'contact_plain.db')
        if decrypt_db(contact_db, key, plain_contact):
            contacts = get_contacts(plain_contact)
            contacts_map = build_contacts_map(contacts)
            print(f"[+] 读取到 {len(contacts)} 个联系人")
            os.remove(plain_contact)

    # 解密消息数据库
    all_messages = []
    db_paths = get_message_db_paths(data_path)

    for db_path in db_paths:
        db_name = os.path.basename(db_path)
        print(f"[*] 正在解密 {db_name}...")
        plain_db = os.path.join(data_path, f'{db_name}_plain.db')
        if not decrypt_db(db_path, key, plain_db):
            print(f"[!] {db_name} 解密失败, 跳过")
            continue

        print(f"[*] 正在读取 {db_name} 中的消息...")
        messages = get_chat_messages(plain_db, args.chat_id, args.limit)
        all_messages.extend(messages)
        print(f"[+] 从 {db_name} 读取到 {len(messages)} 条消息")

        os.remove(plain_db)

    if not all_messages:
        print("[!] 未读取到任何消息")
        return

    # 按时间排序
    all_messages.sort(key=lambda m: m.get('CreateTime', 0) or m.get('createtime', 0))

    # 导出
    output_dir = args.output or os.path.join(data_path, 'exports')
    os.makedirs(output_dir, exist_ok=True)

    chat_id = args.chat_id or 'all'
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    fmt = args.format or 'html'

    # 确定输出文件名
    if args.chat_id:
        chat_name = contacts_map.get(args.chat_id, {}).get('nickname', '') or args.chat_id
        filename = f"chat_{chat_name}_{timestamp}.{fmt}"
    else:
        filename = f"all_messages_{timestamp}.{fmt}"

    output_path = os.path.join(output_dir, filename)

    title = f"聊天记录 - {chat_id}" if args.chat_id else "全部聊天记录"
    export_messages(all_messages, output_path, fmt=fmt,
                    contacts_map=contacts_map, title=title)

    print(f"\n[+] 导出完成! 共 {len(all_messages)} 条消息")
    print(f"[+] 文件位置: {output_path}")


def cmd_interactive(args):
    """交互式模式"""
    print_banner()

    # 检查微信是否运行
    if not ensure_wechat_running():
        return

    # 查找数据目录
    data_path = find_wechat_data_path(args.data_path)
    if not data_path:
        print("[!] 未找到微信数据目录, 请确认微信已登录")
        return

    wxid = get_wxid_from_path(data_path)
    print(f"[+] 微信账号: {wxid}")
    print(f"[+] 数据目录: {data_path}\n")

    # 获取密钥
    key = args.key
    if not key:
        print("[*] 正在自动提取数据库密钥...")
        key = get_db_key(data_path)
        if not key:
            print("\n[!] 自动提取密钥失败!")
            print("[*] 请手动输入密钥 (32位十六进制字符串):")
            key = input("密钥: ").strip()
            if not key:
                print("[!] 未输入密钥, 退出")
                return

    # 验证密钥
    test_db = get_contact_db_path(data_path)
    if not test_db:
        db_paths = get_message_db_paths(data_path)
        if db_paths:
            test_db = db_paths[0]
    if not test_db:
        print("[!] 未找到数据库文件")
        return

    if test_db and os.path.exists(test_db):
        print("[*] 正在验证密钥...")
        if verify_key(test_db, key):
            print("[+] 密钥验证成功!\n")
        else:
            print("[!] 密钥验证失败, 请检查密钥是否正确")
            return

    # 解密联系人
    print("[*] 正在解密联系人数据库...")
    contact_db = get_contact_db_path(data_path)
    contacts_map = {}
    contacts = []
    if contact_db:
        plain_contact = os.path.join(data_path, 'contact_plain.db')
        if decrypt_db(contact_db, key, plain_contact):
            contacts = get_contacts(plain_contact)
            contacts_map = build_contacts_map(contacts)
            os.remove(plain_contact)

    # 显示群聊列表
    chatrooms = [c for c in contacts if '@chatroom' in c.get('username', '')]
    if chatrooms:
        print(f"\n群聊列表 (共 {len(chatrooms)} 个):")
        print("-" * 50)
        for i, cr in enumerate(chatrooms, 1):
            name = cr.get('nickname') or cr.get('remark') or cr.get('username', '')
            print(f"  [{i:2d}] {name}")
        print(f"  [0]  导出全部聊天记录")
        print("-" * 50)

        try:
            choice = input("\n请选择要导出的群聊 (输入编号): ").strip()
            choice = int(choice)
        except (ValueError, EOFError):
            print("[!] 无效输入")
            return

        if choice == 0:
            chat_id = None
            chat_name = "全部"
        elif 1 <= choice <= len(chatrooms):
            cr = chatrooms[choice - 1]
            chat_id = cr['username']
            chat_name = cr.get('nickname') or cr.get('remark') or chat_id
        else:
            print("[!] 无效选择")
            return
    else:
        print("\n[!] 未找到群聊, 将导出全部聊天记录")
        chat_id = None
        chat_name = "全部"

    # 选择导出格式
    print("\n导出格式:")
    print("  [1] HTML (推荐, 可在浏览器中查看)")
    print("  [2] CSV")
    print("  [3] TXT")
    fmt_choice = input("请选择格式 (默认1): ").strip() or '1'
    fmt_map = {'1': 'html', '2': 'csv', '3': 'txt'}
    fmt = fmt_map.get(fmt_choice, 'html')

    # 解密消息数据库并导出
    all_messages = []
    db_paths = get_message_db_paths(data_path)

    for db_path in db_paths:
        db_name = os.path.basename(db_path)
        print(f"[*] 正在解密 {db_name}...")
        plain_db = os.path.join(data_path, f'{db_name}_plain.db')
        if not decrypt_db(db_path, key, plain_db):
            continue

        messages = get_chat_messages(plain_db, chat_id)
        all_messages.extend(messages)
        os.remove(plain_db)

    if not all_messages:
        print("[!] 未读取到任何消息")
        return

    # 按时间排序
    all_messages.sort(key=lambda m: m.get('CreateTime', 0) or m.get('createtime', 0))

    # 导出
    output_dir = os.path.join(data_path, 'exports')
    os.makedirs(output_dir, exist_ok=True)
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    filename = f"wechat_{chat_name}_{timestamp}.{fmt}"
    output_path = os.path.join(output_dir, filename)

    print(f"\n[*] 正在导出 {len(all_messages)} 条消息...")
    export_messages(all_messages, output_path, fmt=fmt,
                    contacts_map=contacts_map, title=f"微信聊天记录 - {chat_name}")

    print(f"\n{'=' * 50}")
    print(f"  导出完成!")
    print(f"  文件: {output_path}")
    print(f"  消息数: {len(all_messages)}")
    print(f"{'=' * 50}")

    # 尝试自动打开文件
    if fmt == 'html':
        try:
            os.startfile(output_path)
            print("  (已自动在浏览器中打开)")
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(
        description='微信本地消息读取与导出工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                          # 交互式模式
  python main.py --list-db                # 列出所有数据库文件
  python main.py --list-chatrooms         # 列出所有群聊
  python main.py --export <chat_id>        # 导出指定群聊记录
  python main.py --export chat_id --key <32位密钥>  # 手动指定密钥
  python main.py --export chat_id --format csv      # 导出为CSV格式
        """
    )

    parser.add_argument('--list-db', action='store_true', help='列出所有数据库文件')
    parser.add_argument('--list-chatrooms', action='store_true', help='列出所有群聊')
    parser.add_argument('--diagnose', action='store_true', help='诊断: 列出所有进程, 帮助排查检测问题')
    parser.add_argument('--export', type=str, metavar='CHAT_ID', help='导出指定聊天记录')
    parser.add_argument('--data-path', type=str, help='手动指定微信数据目录 (如 D:\\wechat\\xwechat_files)')
    parser.add_argument('--key', type=str, help='手动指定数据库密钥 (32位十六进制)')
    parser.add_argument('--format', type=str, choices=['csv', 'txt', 'html'],
                        default='html', help='导出格式 (默认: html)')
    parser.add_argument('--output', type=str, help='输出目录')
    parser.add_argument('--limit', type=int, default=100000, help='最大消息数 (默认: 100000)')

    args = parser.parse_args()

    if args.diagnose:
        cmd_diagnose(args)
    elif args.list_db:
        cmd_list_db(args)
    elif args.list_chatrooms:
        cmd_list_chatrooms(args)
    elif args.export:
        cmd_export(args)
    else:
        cmd_interactive(args)


if __name__ == '__main__':
    main()