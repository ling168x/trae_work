"""搜索 WeChat 进程内存中的备份密钥"""
import os, sys, struct, base64, hashlib

# 候选密钥（从 pkg_info.dat 和 roam_device_info.dat 提取）
candidates = [
    b'3991228554354543780ie3ZFhrQdnFhMapeB9hR3hsJFXaSamThSeX3oaxbtZmXvR',
    b'AAYAALncmWL8jLwyAdkg-pIPwHiGpvlLbtpecZz2z9g@ilink.im.sdk',
    b'28m2HSCMiBIU4CScrqWjIrCihaprQcJZLnNNoX6K/4Q=',
    b'wmZ1ZpLZdWH7bbYDRY0Bp/kVoZlTJoPpeUmwiXZaoLc=',
    b'P2205702',
    b'44157551999@chatroom',
]

# 尝试通过 wechat-cli 获取备份密钥
print("尝试 wechat-cli...")
import subprocess
result = subprocess.run(
    [r'd:\traework\wechat-cli\wechat-cli-v1.6.20-windows-amd64\wechat-cli.exe', 'backup', 'list'],
    capture_output=True, text=True, timeout=30,
    env={**os.environ, 'WECHAT_CLI_DB_ROOT': r'D:\wechat\xwechat_files\LING827323180_96c1'}
)
print("stdout:", result.stdout)
print("stderr:", result.stderr)

# 尝试 backup decrypt
result2 = subprocess.run(
    [r'd:\traework\wechat-cli\wechat-cli-v1.6.20-windows-amd64\wechat-cli.exe', 'backup', 'decrypt', '--help'],
    capture_output=True, text=True, timeout=10,
    env={**os.environ, 'WECHAT_CLI_DB_ROOT': r'D:\wechat\xwechat_files\LING827323180_96c1'}
)
print("backup decrypt help:", result2.stdout)
print("stderr:", result2.stderr)