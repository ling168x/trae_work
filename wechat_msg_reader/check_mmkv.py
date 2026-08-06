"""尝试从 MMKV 和配置文件查找密钥线索"""
import os, struct, re

base = r'D:\wechat\xwechat_files\LING827323180_96c1\db_storage\MMKV'

# 查看 MMKV 文件
for fname in os.listdir(base):
    if fname.endswith('.mmkv'):
        path = os.path.join(base, fname)
        size = os.path.getsize(path)
        print(f"=== {fname} ({size} bytes) ===")
        with open(path, 'rb') as f:
            data = f.read()
        print(f"hex: {data[:100].hex()}")
        try:
            text = data.decode('utf-8', errors='replace')
            # 找可读内容
            import re
            readable = re.findall(r'[\w@./:\\]+', text)
            print(f"可读: {readable[:20]}")
        except:
            pass
        print()

# 也检查一下 message_1.db 的 WAL 文件
db_path = r'D:\wechat\xwechat_files\LING827323180_96c1\db_storage\message\message_1.db'
# 检查是否有 .db-wal 和 .db-shm
for ext in ['.db-wal', '.db-shm', '.kvdb']:
    path = db_path + ext
    if os.path.exists(path):
        print(f"=== message_1.db{ext} ({os.path.getsize(path)} bytes) ===")
        with open(path, 'rb') as f:
            data = f.read(200)
        print(f"hex: {data.hex()}")
        print()

# 也检查 message_1.db.kvdb
for root, dirs, files in os.walk(r'D:\wechat\xwechat_files\LING827323180_96c1\db_storage\message'):
    for f in files:
        if 'message_1' in f and f != 'message_1.db':
            path = os.path.join(root, f)
            print(f"=== {f} ({os.path.getsize(path)} bytes) ===")
            with open(path, 'rb') as fh:
                data = fh.read(200)
            print(f"hex: {data.hex()}")
            print()