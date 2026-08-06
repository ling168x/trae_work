"""尝试从 Windows DPAPI 和 WeChat 配置中提取密钥"""
import os, struct, json, re, hashlib, hmac, base64

# 1. 检查 WeChat 的 WCDB 配置文件
# WCDB 可能将密钥配置存储在 .cfg 或配置文件中
wechat_dir = r'D:\wechat\wx\Weixin'
for root, dirs, files in os.walk(wechat_dir):
    for f in files:
        if f.endswith('.ini') or f.endswith('.cfg') or f.endswith('.conf') or 'config' in f.lower() or 'key' in f.lower():
            path = os.path.join(root, f)
            size = os.path.getsize(path)
            if size < 1024 * 1024:
                print(f"=== {os.path.relpath(path, wechat_dir)} ({size} bytes) ===")
                with open(path, 'rb') as fh:
                    data = fh.read(size)
                print(f"hex: {data[:200].hex()}")
                try:
                    text = data.decode('utf-8', errors='replace')
                    print(f"text: {text[:200]}")
                except:
                    pass
                print()

# 2. 检查 WeChat 注册表项
import winreg
print("检查注册表...")
for root_key in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
    for subkey in [r'Software\Tencent\WeChat', r'Software\Tencent\Weixin', r'Software\WOW6432Node\Tencent\WeChat', r'Software\WOW6432Node\Tencent\Weixin']:
        try:
            key = winreg.OpenKey(root_key, subkey)
            print(f"  {subkey}:")
            for i in range(winreg.QueryInfoKey(key)[1]):
                name, value, _ = winreg.EnumValue(key, i)
                print(f"    {name} = {str(value)[:100]}")
            winreg.CloseKey(key)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"    Error: {e}")

# 3. 检查 DPAPI 加密的数据
# 寻找 WeChat 可能存储的 DPAPI blob
print("\n检查 DPAPI 相关文件...")
import glob
dpapi_patterns = [
    r'D:\wechat\**\*.encrypted',
    r'D:\wechat\**\*.dpapi',
    r'D:\wechat\**\passwd*',
    r'D:\wechat\**\key*',
]

for pattern in dpapi_patterns:
    for path in glob.glob(pattern, recursive=True):
        print(f"  {path}")