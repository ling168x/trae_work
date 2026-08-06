"""使用 PyWxDump API 提取密钥 - 管理员权限版本"""
import sys, os, json, ctypes

# 检查管理员权限
if not ctypes.windll.shell32.IsUserAnAdmin():
    print("[错误] 请以管理员身份运行此脚本！")
    print("  方法: 右键 run_extract.bat → 以管理员身份运行")
    print("  或: 管理员 PowerShell 中运行 python extract_keys_api.py")
    sys.exit(1)

print("=" * 60)
print("  PyWxDump 微信密钥提取 (API 模式)")
print("=" * 60)

# 使用 PyWxDump API
from pywxdump import wx_core

print("\n[1] 获取微信进程信息...")
try:
    wx_info = wx_core.get_wechat_info()
    print(f"结果: {json.dumps(wx_info, indent=2, ensure_ascii=False)}")
except Exception as e:
    print(f"错误: {e}")
    print("\n尝试手动获取...")

# 尝试手动获取进程
from pywxdump.wx_core import get_wechat_process
try:
    procs = get_wechat_process()
    print(f"找到 {len(procs)} 个微信进程:")
    for p in procs:
        print(f"  PID: {p.pid}, 名称: {p.name()}")
except Exception as e:
    print(f"获取进程失败: {e}")

print("\n[2] 尝试获取密钥...")
try:
    # 尝试使用 bias_addr 获取偏移
    from pywxdump.wx_core import bias_addr
    result = bias_addr.get_bias()
    print(f"偏移结果: {result}")
except Exception as e:
    print(f"偏移获取失败: {e}")

print("\n完成。")