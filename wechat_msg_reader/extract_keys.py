"""PyWxDump 密钥提取脚本 — 基于 SharpWxDump 的 Python 版本
功能：从微信进程中提取所有数据库的加密密钥
要求：必须以管理员身份运行！微信必须已登录并运行！
"""

import sys, os, json, ctypes, subprocess

def main():
    print("=" * 60)
    print("  PyWxDump 微信密钥提取工具 (v3.1)")
    print("  基于 SharpWxDump 的 Python 版本")
    print("=" * 60)

    # 1. 检查管理员权限
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("\n[错误] 请以管理员身份运行此脚本！")
        print("  方法1: 右键点击 run_extract.bat → 以管理员身份运行")
        print("  方法2: 以管理员身份打开 PowerShell 或 CMD，然后执行:")
        print("         cd d:\\traework\\wechat_msg_reader")
        print("         python extract_keys.py")
        input("\n按任意键退出...")
        sys.exit(1)

    print("\n管理员权限: 已确认")

    # 2. 检查微信是否运行
    import psutil
    wechat_procs = []
    for proc in psutil.process_iter(['pid', 'name']):
        name = proc.info['name'].lower()
        if name in ['wechat.exe', 'weixin.exe']:
            wechat_procs.append(proc)
    
    if not wechat_procs:
        print("\n[错误] 未检测到微信运行！请先登录微信。")
        input("\n按任意键退出...")
        sys.exit(1)
    
    print(f"检测到 {len(wechat_procs)} 个微信进程:")
    for p in wechat_procs:
        print(f"  PID: {p.info['pid']}, 名称: {p.info['name']}")

    # 3. 使用 wxdump 命令行提取密钥
    print("\n正在提取密钥...")
    print("(这可能需要 10-30 秒，请耐心等待)\n")
    
    # 找到 wxdump.exe
    wxdump = os.path.join(os.path.dirname(sys.executable), 'Scripts', 'wxdump.exe')
    if not os.path.exists(wxdump):
        wxdump = 'wxdump'
    
    result = subprocess.run(
        [wxdump, 'info'],
        capture_output=True, text=True, timeout=120
    )
    
    print("=" * 60)
    print(result.stdout)
    if result.stderr:
        print("[stderr]:", result.stderr[:500])
    print("=" * 60)

    # 4. 解析密钥
    key = None
    wx_path = None
    import re
    
    for line in result.stdout.split('\n'):
        line = line.strip()
        if '密钥' in line or 'key' in line.lower() or 'KEY' in line:
            match = re.search(r'[0-9a-fA-F]{64}', line)
            if match:
                key = match.group()
                print(f"\n找到密钥: {key[:16]}...{key[-16:]}")
        if '路径' in line or 'path' in line.lower() or 'xwechat_files' in line:
            match = re.search(r'[A-Z]:\\[^\s]*xwechat_files[^\s]*', line)
            if match:
                wx_path = match.group()
                print(f"找到微信路径: {wx_path}")

    # 5. 保存结果
    config = {
        'key': key,
        'wx_path': wx_path,
        'db_dir': r'D:\wechat\xwechat_files\LING827323180_96c1\db_storage',
        'raw_output': result.stdout
    }
    
    config_path = r'd:\traework\wechat_msg_reader\extracted_keys.json'
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"\n配置已保存到: {config_path}")
    
    if key:
        print(f"\n[成功] 密钥提取成功！")
        print(f"  下一步: 运行 decrypt_all.py 解密所有数据库并导出聊天记录")
    else:
        print(f"\n[警告] 未能自动提取密钥。")
        print(f"  请查看上方完整输出，手动复制密钥到 extracted_keys.json")
        print(f"  或者尝试其他方案:")
        print(f"  1. 关闭杀毒软件后重试")
        print(f"  2. 更新 PyWxDump: pip install -U pywxdump")
        print(f"  3. 访问 https://github.com/xaoyaoo/PyWxDump 获取最新版本")

    input("\n按任意键退出...")

if __name__ == '__main__':
    main()