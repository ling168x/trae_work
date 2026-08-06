"""调试 Name2Id 和消息内容"""
import sqlite3, os, shutil

try:
    import sqlcipher3
except:
    print("需要 sqlcipher3")
    exit(1)

KEY = '4c64d04ecd632d43eaf1cccecd944c98388da266521f19ce855e07126f7d09e7'
DB_PATH = r'D:\wechat\xwechat_files\LING827323180_96c1\db_storage\message\message_0.db'

tmp = DB_PATH + '.debug'
shutil.copy2(DB_PATH, tmp)
db = sqlcipher3.connect(tmp)
c = db.cursor()
c.execute(f"PRAGMA key=\"x'{KEY}'\"")
c.execute("PRAGMA cipher_page_size=4096")
c.execute("PRAGMA kdf_iter=256000")
c.execute("PRAGMA cipher_compatibility=4")

# 1. 检查 Name2Id 表结构
print("=== Name2Id 表结构 ===")
c.execute("PRAGMA table_info('Name2Id')")
for row in c.fetchall():
    print(f"  {row}")

# 2. 查看 Name2Id 数据
print("\n=== Name2Id 数据 (前20行) ===")
c.execute("SELECT * FROM Name2Id LIMIT 20")
for row in c.fetchall():
    print(f"  {row}")

# 3. 查看一个 Msg 表的结构
print("\n=== Msg 表结构 ===")
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%' LIMIT 1")
tbl = c.fetchone()[0]
print(f"表: {tbl}")
c.execute(f"PRAGMA table_info('{tbl}')")
for row in c.fetchall():
    print(f"  {row}")

# 4. 查看 Msg 表数据
print(f"\n=== {tbl} 数据 (前5行) ===")
c.execute(f"SELECT * FROM '{tbl}' LIMIT 5")
for row in c.fetchall():
    print(f"  {row}")

# 5. 查看 message_content 列的具体内容
print(f"\n=== {tbl} message_content 详细 ===")
c.execute(f"SELECT local_id, create_time, real_sender_id, message_content, local_type FROM '{tbl}' LIMIT 5")
for row in c.fetchall():
    local_id, create_time, real_sender_id, content, msg_type = row
    print(f"  local_id={local_id}, time={create_time}, sender={real_sender_id}, type={msg_type}")
    if content:
        print(f"    content type: {type(content).__name__}")
        if isinstance(content, bytes):
            print(f"    content hex: {content.hex()}")
            print(f"    content utf8: {content.decode('utf-8', errors='replace')[:200]}")
        else:
            print(f"    content: {content[:200]}")

# 6. 检查是否有单独的 content 表
print("\n=== 检查其他表 ===")
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print(f"所有表: {tables}")

# 7. 检查 message_fts.db 是否已解密
fts_path = r'D:\wechat\xwechat_files\LING827323180_96c1\db_storage\message\message_fts.db'
# We can't decrypt it, but let's check if we can use the same key

db.close()
os.remove(tmp)