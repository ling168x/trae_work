"""检查原始 create_time 值"""
import sqlcipher3
from datetime import datetime

key = '4c64d04ecd632d43eaf1cccecd944c98388da266521f19ce855e07126f7d09e7'
db = r'D:\wechat\xwechat_files\LING827323180_96c1\db_storage\message\message_0.db'

conn = sqlcipher3.connect(db)
c = conn.cursor()
c.execute(f"PRAGMA key = \"x'{key}'\"")
c.execute('PRAGMA cipher_page_size = 4096')
c.execute('PRAGMA kdf_iter = 256000')
c.execute('PRAGMA cipher_compatibility = 4')

# 查看原始值
c.execute('SELECT create_time FROM Msg_9fc585fd80bcda3520ddb2592c8765d3 ORDER BY create_time LIMIT 3')
print("前3条原始 create_time:")
for r in c.fetchall():
    ts = r[0]
    print(f"  raw={ts}, type={type(ts)}, as_sec={ts/1000 if ts>1e12 else ts}, date_s={datetime.fromtimestamp(int(ts/1000)) if ts>1e12 else datetime.fromtimestamp(int(ts))}")

c.execute('SELECT create_time FROM Msg_9fc585fd80bcda3520ddb2592c8765d3 ORDER BY create_time DESC LIMIT 3')
print("后3条原始 create_time:")
for r in c.fetchall():
    ts = r[0]
    print(f"  raw={ts}, type={type(ts)}, as_sec={ts/1000 if ts>1e12 else ts}, date_s={datetime.fromtimestamp(int(ts/1000)) if ts>1e12 else datetime.fromtimestamp(int(ts))}")

# 也检查其他表
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%' LIMIT 3")
tables = [r[0] for r in c.fetchall()]
for t in tables:
    c.execute(f'SELECT create_time FROM "{t}" ORDER BY create_time DESC LIMIT 1')
    r = c.fetchone()
    if r:
        ts = r[0]
        print(f"{t}: raw={ts}, type={type(ts)}")

conn.close()