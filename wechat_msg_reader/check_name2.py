import sqlite3, shutil, os, hashlib
import sqlcipher3
KEY = '4c64d04ecd632d43eaf1cccecd944c98388da266521f19ce855e07126f7d09e7'
DB_PATH = r'D:\wechat\xwechat_files\LING827323180_96c1\db_storage\message\message_0.db'
tmp = DB_PATH + '.schema_check'
shutil.copy2(DB_PATH, tmp)
db = sqlcipher3.connect(tmp)
c = db.cursor()
c.execute(f"PRAGMA key=\"x'{KEY}'\"")
c.execute('PRAGMA cipher_page_size=4096')
c.execute('PRAGMA kdf_iter=256000')
c.execute('PRAGMA cipher_compatibility=4')

# 检查 Name2Id 实际列
c.execute("PRAGMA table_info('Name2Id')")
cols = c.fetchall()
print(f"Name2Id 列: {cols}")

# 读取所有数据
c.execute("SELECT * FROM Name2Id")
rows = c.fetchall()
print(f"\nName2Id 行数: {len(rows)}")
print(f"前5行:")
for r in rows[:5]:
    print(f"  {r}")

# 获取 Msg 表
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%' LIMIT 10")
tables = [r[0] for r in c.fetchall()]

print(f"\n前10个 Msg 表:")
for tbl in tables:
    h = tbl[4:]
    c.execute(f"SELECT count(*) FROM '{tbl}'")
    cnt = c.fetchone()[0]
    
    # 查找映射
    if len(cols) == 2 and cols[0][1] == 'username':
        # 旧格式: username, hash
        c.execute("SELECT * FROM Name2Id WHERE hash=?", (h,))
        r = c.fetchone()
    elif len(cols) == 2 and cols[0][1] == 'user_name':
        # 新格式: user_name, is_session - 需要计算 MD5
        found = None
        for row in rows:
            if hashlib.md5(row[0].encode()).hexdigest() == h:
                found = row[0]
                break
        r = (found,) if found else None
    else:
        r = None
    
    name = r[0] if r else f"未知({h[:8]})"
    print(f"  {tbl:40s} [{cnt:5d}条] {name}")

db.close()
os.remove(tmp)