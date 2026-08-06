import sqlite3, shutil, os
import sqlcipher3
KEY = '4c64d04ecd632d43eaf1cccecd944c98388da266521f19ce855e07126f7d09e7'
DB_PATH = r'D:\wechat\xwechat_files\LING827323180_96c1\db_storage\message\message_0.db'
tmp = DB_PATH + '.check_name'
shutil.copy2(DB_PATH, tmp)
db = sqlcipher3.connect(tmp)
c = db.cursor()
c.execute(f"PRAGMA key=\"x'{KEY}'\"")
c.execute('PRAGMA cipher_page_size=4096')
c.execute('PRAGMA kdf_iter=256000')
c.execute('PRAGMA cipher_compatibility=4')

# 检查前5个聊天
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%' LIMIT 5")
tables = [r[0][4:] for r in c.fetchall()]

# 检查 Name2Id 列
c.execute("PRAGMA table_info('Name2Id')")
for r in c.fetchall():
    print(f"Name2Id col: {r}")

for h in tables:
    c.execute("SELECT * FROM Name2Id WHERE hash=?", (h,))
    r = c.fetchone()
    if r:
        print(f'  {h[:16]}... -> {r[0]}')
    else:
        # 尝试反向查
        c.execute("SELECT * FROM Name2Id WHERE username LIKE ?", (f'%{h[:8]}%',))
        r = c.fetchone()
        if r:
            print(f'  {h[:16]}... -> (reverse) {r[0]}')
        else:
            print(f'  {h[:16]}... -> NOT FOUND')

# 检查总行数
c.execute("SELECT count(*) FROM Name2Id")
print(f'Total Name2Id: {c.fetchone()[0]}')

# 检查 Name2Id 前5行
c.execute("SELECT * FROM Name2Id LIMIT 5")
for r in c.fetchall():
    print(f'  Name2Id: {r}')

db.close()
os.remove(tmp)