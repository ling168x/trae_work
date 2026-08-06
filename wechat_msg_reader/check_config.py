"""检查 WCDB metadata 和配置寻找密钥线索"""
import os, struct, json, re

# 1. 检查 WCDB 的 material 文件
msg_dir = r'D:\wechat\xwechat_files\LING827323180_96c1\db_storage\message'
for f in os.listdir(msg_dir):
    if f.endswith('.material') or 'material' in f.lower():
        path = os.path.join(msg_dir, f)
        size = os.path.getsize(path)
        print(f"=== {f} ({size} bytes) ===")
        with open(path, 'rb') as fh:
            data = fh.read(500)
        print(f"hex: {data.hex()}")
        print()

# 2. 检查 kvdb 文件内容
for f in os.listdir(msg_dir):
    if f.endswith('.kvdb') and not f.endswith('-wal') and not f.endswith('-shm'):
        path = os.path.join(msg_dir, f)
        size = os.path.getsize(path)
        print(f"=== {f} ({size} bytes) ===")
        with open(path, 'rb') as fh:
            data = fh.read()
        print(f"hex: {data[:200].hex()}")
        # 尝试找可读文本
        try:
            text = data.decode('utf-8', errors='replace')
            readable = re.findall(r'[\w@./:\\-]{8,}', text)
            print(f"可读: {readable[:20]}")
        except:
            pass
        print()

# 3. 检查 all_users 目录
all_users = r'D:\wechat\xwechat_files\all_users'
if os.path.exists(all_users):
    for root, dirs, files in os.walk(all_users):
        for f in files:
            path = os.path.join(root, f)
            size = os.path.getsize(path)
            print(f"=== all_users/{os.path.relpath(path, all_users)} ({size} bytes) ===")
            with open(path, 'rb') as fh:
                data = fh.read(500)
            print(f"hex: {data.hex()}")
            try:
                text = data.decode('utf-8', errors='replace')
                readable = re.findall(r'[\w@./:\\-]{8,}', text)
                print(f"可读: {readable[:20]}")
            except:
                pass
            print()

# 4. 检查 xwechat_files 根目录
root_dir = r'D:\wechat\xwechat_files'
for f in os.listdir(root_dir):
    path = os.path.join(root_dir, f)
    if os.path.isfile(path):
        size = os.path.getsize(path)
        print(f"=== {f} ({size} bytes) ===")
        with open(path, 'rb') as fh:
            data = fh.read(500)
        print(f"hex: {data.hex()}")
        try:
            text = data.decode('utf-8', errors='replace')
            print(f"text: {text[:200]}")
        except:
            pass
        print()