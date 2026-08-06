"""检查所有 Msg 表的时间范围"""
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

c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'")
tables = [r[0] for r in c.fetchall()]

# 读取 Name2Id
import hashlib
c.execute("SELECT user_name FROM Name2Id WHERE user_name != ''")
usernames = {hashlib.md5(r[0].encode()).hexdigest(): r[0] for r in c.fetchall()}

for t in tables:
    hash_id = t.replace('Msg_', '')
    username = usernames.get(hash_id, hash_id)
    c.execute(f'SELECT MIN(create_time), MAX(create_time), COUNT(*) FROM "{t}"')
    min_t, max_t, cnt = c.fetchone()
    min_d = datetime.fromtimestamp(int(min_t)/1000).strftime('%Y-%m-%d') if min_t else 'N/A'
    max_d = datetime.fromtimestamp(int(max_t)/1000).strftime('%Y-%m-%d') if max_t else 'N/A'
    print(f'{username}: {cnt} msgs, {min_d} ~ {max_d}')

conn.close()