"""RMFH 备份解密 - 尝试多种密钥和算法组合"""
import os, struct, base64, hashlib
from Crypto.Cipher import AES

BACKUP_DIR = r'D:\wechat\xwechat_files\Backup\LING827323180\ebc21d5d56a0a15e534c88e8f0132376\files\2\f844dccf27218b0011d9ef9b3c38d002abeb6245391f83b42b1a78cfd98e33f3\ChatPackage'
chat_files = sorted(os.listdir(BACKUP_DIR))
test_file = os.path.join(BACKUP_DIR, chat_files[0])

with open(test_file, 'rb') as f:
    data = f.read()

# 候选密钥
known_db_key = bytes.fromhex('4c64d04ecd632d43eaf1cccecd944c98388da266521f19ce855e07126f7d09e7')

# pkg_info.dat key - 64 bytes raw string
pkg_key_str = '3991228554354543780ie3ZFhrQdnFhMapeB9hR3hsJFXaSamThSeX3oaxbtZmXvR'
pkg_key_bytes = pkg_key_str.encode()  # 64 bytes raw

# roam keys
roam_k1 = base64.b64decode('28m2HSCMiBIU4CScrqWjIrCihaprQcJZLnNNoX6K/4Q=')  # 32 bytes
roam_k2 = base64.b64decode('wmZ1ZpLZdWH7bbYDRY0Bp/kVoZlTJoPpeUmwiXZaoLc=')  # 32 bytes

# ilink key
ilink_key = b'AAYAALncmWL8jLwyAdkg-pIPwHiGpvlLbtpecZz2z9g@ilink.im.sdk'

# Nonce/IV (12 bytes at 0x14)
nonce12 = data[20:32]  # 12 bytes
nonce11 = data[20:31]  # 11 bytes
nonce8 = data[20:28]   # 8 bytes

print(f"Nonce 12: {nonce12.hex()}")
print(f"Nonce 11: {nonce11.hex()}")
print(f"Nonce 8:  {nonce8.hex()}")

# 加密数据
enc = data[128:]

# Keys to try
keys = [
    ('known_db_key', known_db_key),
    ('pkg_key_b64', pkg_key_bytes),
    ('roam_k1', roam_k1),
    ('roam_k2', roam_k2),
    ('sha256(pkg_key_str)', hashlib.sha256(pkg_key_str.encode()).digest()),
    ('md5(pkg_key_str)', hashlib.md5(pkg_key_str.encode()).digest()),
    ('sha256(ilink_key)', hashlib.sha256(ilink_key).digest()),
    ('md5(ilink_key)', hashlib.md5(ilink_key).digest()),
    # PBKDF2 derived
    ('pbkdf2(pkg_key_str)', hashlib.pbkdf2_hmac('sha256', pkg_key_str.encode(), b'wxbackup', 1000, 32)),
    ('pbkdf2(ilink)', hashlib.pbkdf2_hmac('sha256', ilink_key, b'wxbackup', 1000, 32)),
    ('pbkdf2(pkg_key_str, 10000)', hashlib.pbkdf2_hmac('sha256', pkg_key_str.encode(), b'wxbackup', 10000, 32)),
    # 直接使用 pkg_key_str hex
    ('pkg_key_str_hex', bytes.fromhex(pkg_key_str) if len(pkg_key_str) == 64 else None),
]

# 尝试 AES-256-GCM (12-byte nonce)
print("\n=== AES-256-GCM (12-byte nonce) ===")
for name, key in keys:
    if key is None or len(key) not in [16, 24, 32]:
        continue
    try:
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce12)
        plain = cipher.decrypt(enc[:128])
        # Check if plaintext looks like valid protobuf
        if len(plain) > 0 and plain[0] in [0x08, 0x12, 0x1a, 0x22, 0x0a, 0x32]:
            # More validation: check if first 4 bytes look like valid protobuf length
            if plain[0] in [0x08, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38]:
                pass  # varint, likely valid
            elif plain[0] in [0x12, 0x1a, 0x22, 0x2a, 0x32, 0x3a, 0x42, 0x4a]:
                length = plain[1]
                if length < 200:
                    chunk = plain[2:2+length]
                    try:
                        text = chunk.decode('utf-8', errors='replace')
                        if any(c.isalpha() for c in text):
                            print(f"  [MATCH!] {name}: {text[:80]}")
                            # Try to decode more
                            plain2 = cipher.decrypt(enc[:1024])
                            print(f"    Full: {plain2[:200].hex()}")
                            continue
                    except:
                        pass
            print(f"  [MAYBE] {name}: {plain[:64].hex()}")
        else:
            print(f"  [FAIL] {name}: {plain[:16].hex()}")
    except Exception as e:
        print(f"  [ERR] {name}: {e}")

# 尝试 AES-256-GCM (11-byte nonce)
print("\n=== AES-256-GCM (11-byte nonce) ===")
for name, key in keys:
    if key is None or len(key) not in [16, 24, 32]:
        continue
    try:
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce11)
        plain = cipher.decrypt(enc[:128])
        if len(plain) > 0 and plain[0] in [0x08, 0x12, 0x1a, 0x22, 0x0a, 0x32]:
            print(f"  [MAYBE] {name}: {plain[:64].hex()}")
    except Exception as e:
        pass

# 尝试 AES-256-CBC
print("\n=== AES-256-CBC (16-byte IV) ===")
for name, key in keys:
    if key is None or len(key) not in [16, 24, 32]:
        continue
    # 用 nonce 作为 IV 前缀
    iv = nonce11 + b'\x00' * 5  # 16 bytes
    try:
        cipher = AES.new(key, AES.MODE_CBC, iv=iv)
        plain = cipher.decrypt(enc[:128])
        if len(plain) > 0 and plain[0] in [0x08, 0x12, 0x1a, 0x22, 0x0a, 0x32]:
            print(f"  [MAYBE] {name}: {plain[:64].hex()}")
    except Exception as e:
        pass

# 尝试 AES-256-CTR
print("\n=== AES-256-CTR ===")
for name, key in keys:
    if key is None or len(key) not in [16, 24, 32]:
        continue
    try:
        cipher = AES.new(key, AES.MODE_CTR, nonce=nonce8[:4], initial_value=int.from_bytes(nonce8[4:], 'big'))
        plain = cipher.decrypt(enc[:128])
        if len(plain) > 0 and plain[0] in [0x08, 0x12, 0x1a, 0x22, 0x0a, 0x32]:
            print(f"  [MAYBE] {name}: {plain[:64].hex()}")
    except Exception as e:
        pass

# 尝试 XOR 解密（有些微信备份使用简单的 XOR）
print("\n=== XOR with key ===")
for name, key in keys:
    if key is None or len(key) < 4:
        continue
    plain = bytes(a ^ key[i % len(key)] for i, a in enumerate(enc[:128]))
    if len(plain) > 0 and plain[0] in [0x08, 0x12, 0x1a, 0x22, 0x0a, 0x32]:
        print(f"  [MAYBE] {name}: {plain[:64].hex()}")

print("\nDone.")