"""测试解密 message_0.db"""
import sqlcipher3, sqlite3

key = '4c64d04ecd632d43eaf1cccecd944c98388da266521f19ce855e07126f7d09e7'
db = r'D:\wechat\xwechat_files\LING827323180_96c1\db_storage\message\message_0.db'

conn = sqlcipher3.connect(db)
c = conn.cursor()
c.execute(f"PRAGMA key = \"x'{key}'\"")
c.execute('PRAGMA cipher_page_size = 4096')
c.execute('PRAGMA kdf_iter = 256000')
c.execute('PRAGMA cipher_compatibility = 4')

# 列出表
c.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = [r[0] for r in c.fetchall()]
print('Tables:', tables)

# 查看第一个表的结构
for t in tables[:5]:
    c.execute(f'PRAGMA table_info({t})')
    cols = [(r[1], r[2]) for r in c.fetchall()]
    print(f'\n{t}: {cols[:10]}')

# 读取几条消息
if 'message' in tables or 'MSG' in tables:
    msg_table = next((t for t in tables if 'message' in t.lower() or t == 'MSG'), tables[0])
    c.execute(f'SELECT * FROM {msg_table} LIMIT 3')
    rows = c.fetchall()
    c.execute(f'PRAGMA table_info({msg_table})')
    col_names = [r[1] for r in c.fetchall()]
    print(f'\n{msg_table} columns: {col_names}')
    for row in rows:
        print(dict(zip(col_names, row)))

conn.close()
print('\nDecryption successful!')