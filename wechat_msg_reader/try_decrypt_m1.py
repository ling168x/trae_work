"""尝试用 message_0.db 的密码解密 message_1.db"""
import sqlcipher3
import os

key = '4c64d04ecd632d43eaf1cccecd944c98388da266521f19ce855e07126f7d09e7'
db_path = r'D:\wechat\xwechat_files\LING827323180_96c1\db_storage\message\message_1.db'

# 检查文件
print(f"message_1.db exists: {os.path.exists(db_path)}")
print(f"size: {os.path.getsize(db_path)} bytes")

# 尝试多种参数组合
params = [
    {"page_size": 4096, "kdf_iter": 256000, "compat": 4},
    {"page_size": 4096, "kdf_iter": 64000, "compat": 4},
    {"page_size": 4096, "kdf_iter": 256000, "compat": 3},
    {"page_size": 4096, "kdf_iter": 64000, "compat": 3},
    {"page_size": 1024, "kdf_iter": 256000, "compat": 4},
    {"page_size": 1024, "kdf_iter": 64000, "compat": 4},
    {"page_size": 1024, "kdf_iter": 4000, "compat": 3},
]

for i, params in enumerate(params):
    try:
        conn = sqlcipher3.connect(db_path)
        c = conn.cursor()
        c.execute(f"PRAGMA key = \"x'{key}'\"")
        c.execute(f"PRAGMA cipher_page_size = {params['page_size']}")
        c.execute(f"PRAGMA kdf_iter = {params['kdf_iter']}")
        c.execute(f"PRAGMA cipher_compatibility = {params['compat']}")
        
        c.execute("SELECT COUNT(*) FROM sqlite_master")
        cnt = c.fetchone()[0]
        print(f"  [{i}] page={params['page_size']}, iter={params['kdf_iter']}, compat={params['compat']}: {cnt} tables")
        conn.close()
    except Exception as e:
        print(f"  [{i}] page={params['page_size']}, iter={params['kdf_iter']}, compat={params['compat']}: ERROR - {str(e)[:80]}")

# 也用纯文本尝试
print("\n尝试纯文本密码...")
try:
    conn = sqlcipher3.connect(db_path)
    c = conn.cursor()
    c.execute("PRAGMA key = \"x'679584d4fe24d0cca062865147fd153a'\"")
    c.execute("PRAGMA cipher_page_size = 4096")
    c.execute("PRAGMA kdf_iter = 256000")
    c.execute("PRAGMA cipher_compatibility = 4")
    c.execute("SELECT COUNT(*) FROM sqlite_master")
    cnt = c.fetchone()[0]
    print(f"  salt as key: {cnt} tables")
    conn.close()
except Exception as e:
    print(f"  salt as key: ERROR - {str(e)[:80]}")