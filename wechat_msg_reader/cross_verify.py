"""用已知密钥交叉验证所有数据库"""
import sqlite3, os, shutil, hashlib, hmac, struct

try:
    import sqlcipher3
except ImportError:
    print("需要 sqlcipher3")
    exit(1)

known_key = '4c64d04ecd632d43eaf1cccecd944c98388da266521f19ce855e07126f7d09e7'
PAGE_SZ = 4096

def verify_key(enc_key, page1):
    salt = page1[:16]
    ms = bytes(b ^ 0x3a for b in salt)
    mk = hashlib.pbkdf2_hmac("sha512", enc_key, ms, 2, dklen=32)
    hd = page1[16:PAGE_SZ-80+16]
    ss = page1[PAGE_SZ-64:PAGE_SZ]
    h = hmac.new(mk, hd, hashlib.sha512)
    h.update(struct.pack('<I', 1))
    return h.digest() == ss

DB_DIR = r"D:\wechat\xwechat_files\LING827323180_96c1\db_storage"
dbs = []
for root, dirs, files in os.walk(DB_DIR):
    for f in files:
        if f.endswith('.db') and '-wal' not in f and '-shm' not in f:
            path = os.path.join(root, f)
            if os.path.getsize(path) < PAGE_SZ: continue
            with open(path, 'rb') as fh:
                p1 = fh.read(PAGE_SZ)
            dbs.append((os.path.relpath(path, DB_DIR), path, p1[:16].hex(), p1))

print(f"交叉验证 {len(dbs)} 个数据库...")

# 先在文件层面验证
known_ek = bytes.fromhex(known_key)
for rel, path, salt, p1 in dbs:
    if verify_key(known_ek, p1):
        print(f"  [OK] {rel}: HMAC 验证通过！")
    else:
        print(f"  [MISS] {rel}: HMAC 不匹配")

# 尝试用已知密钥解密
print("\n尝试解密验证通过的数据库...")
for rel, path, salt, p1 in dbs:
    if verify_key(known_ek, p1):
        try:
            tmp = path + '.test'
            shutil.copy2(path, tmp)
            db = sqlcipher3.connect(tmp)
            c = db.cursor()
            c.execute(f"PRAGMA key=\"x'{known_key}'\"")
            c.execute("PRAGMA cipher_page_size=4096")
            c.execute("PRAGMA kdf_iter=256000")
            c.execute("PRAGMA cipher_compatibility=4")
            c.execute("SELECT count(*) FROM sqlite_master")
            count = c.fetchone()[0]
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in c.fetchall()]
            print(f"  [OK] {rel}: {count} tables - {tables[:10]}")
            db.close()
            os.remove(tmp)
        except Exception as e:
            print(f"  [FAIL] {rel}: {str(e)[:100]}")
            try:
                db.close()
            except:
                pass
            if os.path.exists(tmp):
                os.remove(tmp)

print("\n完成！")