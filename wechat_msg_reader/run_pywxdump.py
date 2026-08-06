import subprocess, sys, json, os

print("=" * 60)
print("  PyWxDump 微信密钥提取")
print("=" * 60)

# 1. 检查管理员权限
import ctypes
is_admin = ctypes.windll.shell32.IsUserAnAdmin()
print(f"\n管理员权限: {'是' if is_admin else '否 - 需要以管理员身份运行！'}")

# 2. 运行 wxdump info
print("\n正在提取密钥...")
result = subprocess.run(
    [sys.executable, "-c", "from pywxdump import *; from pywxdump.wx_core.get_info import *; print(get_info())"],
    capture_output=True, text=True, timeout=120
)

print("\n输出:")
print(result.stdout)
if result.stderr:
    print("错误:", result.stderr[:500])

# 3. 尝试使用 wxdump 命令行
print("\n" + "=" * 60)
print("尝试 wxdump 命令行...")
# 找到 wxdump.exe 的位置
import shutil
wxdump_path = shutil.which('wxdump')
print(f"wxdump 路径: {wxdump_path}")

if wxdump_path:
    result2 = subprocess.run(
        [wxdump_path, 'info'],
        capture_output=True, text=True, timeout=120
    )
    print(result2.stdout)
    if result2.stderr:
        print("错误:", result2.stderr[:500])