"""尝试用 message_0.db 的密钥解密 message_1.db，使用不同的 SQLCipher 参数"""
import sqlite3, os, struct, hashlib, hmac, shutil

# 加载 sqlcipher
try:
    import sqlcipher3
    print("sqlcipher3 已加载")
except ImportError:
    print("需要安装 sqlcipher3")
    exit(1)

# 已知 key
known_key = '4c64d04ecd632d43eaf1cccecd944c98388da266521f19ce855e07126f7d09e7'

# 解密 message_0.db 验证
m0_path = r'D:\wechat\xwechat_files\LING827323180_96c1\db_storage\message\message_0.db'
m1_path = r'D:\wechat\xwechat_files\LING827323180_96c1\db_storage\message\message_1.db'

# 读取第一页
with open(m1_path, 'rb') as f:
    page1 = f.read(4096)
salt1 = page1[:16].hex()
print(f"message_1.db salt: {salt1}")

# 尝试不同的参数组合
configs = [
    # (kdf_iter, page_size, cipher_compat, name)
    (256000, 4096, 4, "default"),
    (256000, 4096, 3, "compat=3"),
    (64000, 4096, 4, "iter=64000"),
    (64000, 4096, 3, "iter=64000,compat=3"),
    (4000, 4096, 4, "iter=4000"),
    (4000, 4096, 3, "iter=4000,compat=3"),
    (256000, 1024, 4, "page_size=1024"),
    (256000, 1024, 3, "page_size=1024,compat=3"),
    (256000, 8192, 4, "page_size=8192"),
    (256000, 8192, 3, "page_size=8192,compat=3"),
    (1, 4096, 4, "iter=1"),
    (2, 4096, 4, "iter=2"),
    (50000, 4096, 4, "iter=50000"),
    (100000, 4096, 4, "iter=100000"),
]

for kdf_iter, page_size, compat, name in configs:
    try:
        # 复制数据库
        tmp_path = m1_path + '.test'
        shutil.copy2(m1_path, tmp_path)
        
        db = sqlcipher3.connect(tmp_path)
        c = db.cursor()
        
        if compat == 4:
            c.execute(f"PRAGMA key=\"x'{known_key}'\"")
        else:
            c.execute(f"PRAGMA key=\"x'{known_key}'\"")
        
        c.execute(f"PRAGMA cipher_page_size={page_size}")
        c.execute(f"PRAGMA kdf_iter={kdf_iter}")
        c.execute(f"PRAGMA cipher_compatibility={compat}")
        
        try:
            c.execute("SELECT count(*) FROM sqlite_master")
            count = c.fetchone()[0]
            print(f"  [OK] {name}: {count} tables")
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in c.fetchall()]
            print(f"    Tables: {tables[:10]}")
        except Exception as e:
            print(f"  [FAIL] {name}: {str(e)[:80]}")
        
        db.close()
        os.remove(tmp_path)
    except Exception as e:
        print(f"  [ERROR] {name}: {str(e)[:80]}")

# 也尝试用空 key
print("\n尝试空 key:")
try:
    shutil.copy2(m1_path, m1_path + '.test')
    db = sqlcipher3.connect(m1_path + '.test')
    c = db.cursor()
    c.execute("PRAGMA key=''")
    c.execute("PRAGMA cipher_page_size=4096")
    c.execute("PRAGMA kdf_iter=256000")
    c.execute("PRAGMA cipher_compatibility=4")
    try:
        c.execute("SELECT count(*) FROM sqlite_master")
        print(f"  [OK] empty key: {c.fetchone()[0]} tables")
    except Exception as e:
        print(f"  [FAIL] empty key: {str(e)[:80]}")
    db.close()
    os.remove(m1_path + '.test')
except Exception as e:
    print(f"  [ERROR] empty key: {str(e)[:80]}")