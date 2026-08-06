"""尝试解密 RMFH ChatPackage 备份文件"""
import os, struct, base64, hashlib
from Crypto.Cipher import AES

BACKUP_DIR = r'D:\wechat\xwechat_files\Backup\LING827323180\ebc21d5d56a0a15e534c88e8f0132376\files\2\f844dccf27218b0011d9ef9b3c38d002abeb6245391f83b42b1a78cfd98e33f3\ChatPackage'

# 从 pkg_info.dat 和 roam_device_info.dat 提取的候选密钥
# 1. pkg_info.dat 中的 key
pkg_key = 'ie3ZFhrQdnFhMapeB9hR3hsJFXaSamThSeX3oaxbtZmXvR'

# 2. roam_device_info.dat 中的两个 key
roam_key1 = '28m2HSCMiBIU4CScrqWjIrCihaprQcJZLnNNoX6K/4Q='
roam_key2 = 'wmZ1ZpLZdWH7bbYDRY0Bp/kVoZlTJoPpeUmwiXZaoLc='

# 3. 尝试解析 pkg_info.dat 的完整 protobuf
with open(r'D:\wechat\xwechat_files\Backup\LING827323180\ebc21d5d56a0a15e534c88e8f0132376\files\2\pkg_info.dat', 'rb') as f:
    pkg_data = f.read()

print(f"pkg_info.dat: {len(pkg_data)} bytes")
print(f"hex: {pkg_data.hex()}")

# 手动解析 protobuf
# field 1 (0x08): varint 02
# field 2 (0x10): varint 03
# field 3 (0x1a): string "WXGBACKUPPACKAGEPREFIX_聊天 1"
# field 4 (0x22): embedded message
#   field 21 (0xab 0x1f): varint
#   field 2 (0x12): string "AAYAALncmWL8jLwyAdkg-pIPwHiGpvlLbtpecZz2z9g@ilink.im.sdk"
#   field 3 (0x1a): bytes
#   field 4 (0x22): string "P2205702"
#   field 5 (0x2a): string "source_device_id"
# field 5 (0x32): string "44157551999@chatroom..."
# field 8 (0x42): bytes "3991228554354543780ie3ZFhrQdnFhMapeB9hR3hsJFXaSamThSeX3oaxbtZmXvR"
# field 11 (0x0b): bytes

# 读取 ChatPackage 文件
chat_files = sorted(os.listdir(BACKUP_DIR))
print(f"\nChatPackage 文件: {len(chat_files)} 个")
print(f"第一个: {chat_files[0]}")

with open(os.path.join(BACKUP_DIR, chat_files[0]), 'rb') as f:
    data = f.read()

print(f"\n文件大小: {len(data)} bytes")
print(f"魔数: {data[:4]}")
print(f"头部 128 bytes hex:")
for i in range(0, 128, 16):
    print(f"  {i:04x}: {data[i:i+16].hex()}")

# RMFH 头部结构分析
print("\nRMFH 头部结构:")
print(f"  0x00 魔数: {data[0:4]}")
print(f"  0x04 时间戳?: {data[4:8].hex()}")
print(f"  0x08 版本: {data[8:10].hex()}")
print(f"  0x0A 标志: {data[10:12].hex()}")
print(f"  0x0C 填充: {data[12:16].hex()}")
print(f"  0x10 长度?: {data[16:20].hex()} = {struct.unpack('<I', data[16:20])[0]}")
print(f"  0x14 Nonce: {data[20:32].hex()}")

# 尝试解密
# 密钥候选
keys = []
try:
    keys.append(('pkg_key', base64.b64decode(pkg_key + '=')))
except:
    keys.append(('pkg_key_raw', pkg_key.encode()))
try:
    keys.append(('roam_key1', base64.b64decode(roam_key1)))
    keys.append(('roam_key2', base64.b64decode(roam_key2)))
except Exception as e:
    print(f"Base64 decode error: {e}")

# 也尝试 roam_device_info.dat 的完整数据
with open(r'D:\wechat\xwechat_files\Backup\LING827323180\roam_device_info.dat', 'rb') as f:
    roam_data = f.read()

# 提取 roam_device_info 中的 key
# 查找 "_wxroam:" 后面的 Base64 数据
idx = roam_data.find(b'_wxroam:')
if idx >= 0:
    roam_str = roam_data[idx+8:]  # Skip "_wxroam:"
    print(f"\nroam_device_info _wxroam 数据: {roam_str[:100]}")

# 提取 pkg_info 中的加密key
# field 8 bytes 包含 "3991228554354543780ie3ZFhrQdnFhMapeB9hR3hsJFXaSamThSeX3oaxbtZmXvR"
# 尝试作为原始密钥
raw_pkg_key = b'3991228554354543780ie3ZFhrQdnFhMapeB9hR3hsJFXaSamThSeX3oaxbtZmXvR'
keys.append(('raw_pkg_key', raw_pkg_key))

# 也尝试 MD5 和 SHA256 派生
keys.append(('md5_pkg', hashlib.md5(raw_pkg_key).digest()))
keys.append(('sha256_pkg', hashlib.sha256(raw_pkg_key).digest()))

# 提取 11 字节 nonce
nonce = data[20:31]  # 11 bytes
print(f"\nNonce (11 bytes): {nonce.hex()}")

# 加密数据
enc_data = data[128:]  # 128-byte header
print(f"加密数据起始: {enc_data[:32].hex()}")

# 尝试 AES-256-GCM
print("\n=== 尝试 AES-256-GCM ===")
for name, key in keys:
    if len(key) not in [16, 24, 32]:
        print(f"  {name}: key length {len(key)} - 跳过")
        continue
    try:
        # 尝试 11-byte nonce
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        plain = cipher.decrypt(enc_data[:64])
        # 检查是否看起来像有效数据
        # protobuf 编码的消息通常以 0x08, 0x12, 0x1a 等开头
        if plain[:4] and plain[0] in [0x08, 0x12, 0x1a, 0x22, 0x0a, 0x32, 0x3a, 0x42, 0x4a]:
            print(f"  [OK?] {name}: {plain[:64].hex()}")
            print(f"    text: {plain[:64]}")
        else:
            print(f"  [FAIL] {name}: {plain[:32].hex()}")
    except Exception as e:
        print(f"  [ERROR] {name}: {e}")

# 尝试 AES-256-CBC
print("\n=== 尝试 AES-256-CBC ===")
for name, key in keys:
    if len(key) not in [16, 24, 32]:
        continue
    try:
        # 使用 16-byte IV (用零填充 nonce 到 16 bytes)
        iv = nonce + b'\x00' * 5
        cipher = AES.new(key, AES.MODE_CBC, iv=iv)
        plain = cipher.decrypt(enc_data[:32])
        if plain[:4] and plain[0] in [0x08, 0x12, 0x1a, 0x22, 0x0a]:
            print(f"  [OK?] {name}: {plain[:32].hex()}")
        else:
            print(f"  [FAIL] {name}: {plain[:16].hex()}")
    except Exception as e:
        print(f"  [ERROR] {name}: {e}")

# 尝试 AES-256-CTR
print("\n=== 尝试 AES-256-CTR ===")
for name, key in keys:
    if len(key) not in [16, 24, 32]:
        continue
    try:
        # CTR mode with 8-byte nonce
        cipher = AES.new(key, AES.MODE_CTR, nonce=b'', initial_value=int.from_bytes(nonce[:8], 'big'))
        plain = cipher.decrypt(enc_data[:32])
        if plain[:4] and plain[0] in [0x08, 0x12, 0x1a, 0x22, 0x0a]:
            print(f"  [OK?] {name}: {plain[:32].hex()}")
        else:
            print(f"  [FAIL] {name}: {plain[:16].hex()}")
    except Exception as e:
        print(f"  [ERROR] {name}: {e}")