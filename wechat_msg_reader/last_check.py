"""
最后尝试：从 message_1.db 的备份和 WAL 文件中查找密钥线索
思路：WCDB 的 material 文件是 checkpoint 的备份，可能包含未加密的元数据
"""
import os, struct, hashlib, hmac, re

msg_dir = r'D:\wechat\xwechat_files\LING827323180_96c1\db_storage\message'

# 读取 message_1.db 的 salt
with open(os.path.join(msg_dir, 'message_1.db'), 'rb') as f:
    page1_m1 = f.read(4096)
salt_m1 = page1_m1[:16].hex()
print(f"message_1.db salt: {salt_m1}")

# 读取 message_0.db 的 salt
with open(os.path.join(msg_dir, 'message_0.db'), 'rb') as f:
    page1_m0 = f.read(4096)
salt_m0 = page1_m0[:16].hex()
print(f"message_0.db salt: {salt_m0}")

# 尝试：也许 message_1.db 是 message_0.db 的备份，密钥相同？
# 前面已经验证过，密钥不同

# 读取 WAL 文件
wal_path = os.path.join(msg_dir, 'message_1.db-wal')
if os.path.exists(wal_path):
    with open(wal_path, 'rb') as f:
        wal_data = f.read()
    print(f"\nmessage_1.db-wal: {len(wal_data)} bytes")
    # WAL header: magic + version + page_size + ...
    wal_magic = wal_data[:4]
    print(f"WAL magic: {wal_magic.hex()}")
    # 搜索 x' 模式
    hex_matches = re.findall(b"x'([0-9a-fA-F]{32,})", wal_data)
    print(f"WAL 中的 x' 模式: {len(hex_matches)}")
    for m in hex_matches[:5]:
        print(f"  {m.decode()[:80]}")

# 检查 message_1.kvdb 内容
kvdb_path = os.path.join(msg_dir, 'message_1.kvdb')
if os.path.exists(kvdb_path):
    with open(kvdb_path, 'rb') as f:
        kvdb_data = f.read()
    print(f"\nmessage_1.kvdb: {len(kvdb_data)} bytes")
    # 搜索可能的密钥模式
    hex_matches = re.findall(b"x'([0-9a-fA-F]{32,})", kvdb_data)
    print(f"kvdb 中的 x' 模式: {len(hex_matches)}")
    for m in hex_matches[:5]:
        print(f"  {m.decode()[:80]}")

# 也检查 message_1.kvdb-wal
kvdb_wal = os.path.join(msg_dir, 'message_1.kvdb-wal')
if os.path.exists(kvdb_wal):
    with open(kvdb_wal, 'rb') as f:
        kw_data = f.read()
    print(f"\nmessage_1.kvdb-wal: {len(kw_data)} bytes")
    hex_matches = re.findall(b"x'([0-9a-fA-F]{32,})", kw_data)
    print(f"kvdb-wal 中的 x' 模式: {len(hex_matches)}")
    for m in hex_matches[:5]:
        print(f"  {m.decode()[:80]}")

# 最后，检查 all_users 下的所有配置
print("\n检查 all_users 配置...")
all_users = r'D:\wechat\xwechat_files\all_users'
for root, dirs, files in os.walk(all_users):
    for fname in files:
        path = os.path.join(root, fname)
        size = os.path.getsize(path)
        if size < 100 * 1024:  # 只检查小文件
            with open(path, 'rb') as f:
                data = f.read()
            hex_matches = re.findall(b"x'([0-9a-fA-F]{64,})", data)
            if hex_matches:
                print(f"  {os.path.relpath(path, all_users)}: {len(hex_matches)} x' matches")
                for m in hex_matches[:3]:
                    print(f"    {m.decode()[:80]}")