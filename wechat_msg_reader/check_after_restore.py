import os, time, shutil, hashlib
import sqlcipher3

# 1. Check message_0.db
msg0 = r'D:\wechat\xwechat_files\LING827323180_96c1\db_storage\message\message_0.db'
mtime = time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(msg0)))
print(f'message_0.db: {os.path.getsize(msg0)/1024/1024:.1f}MB, modified: {mtime}')

# 2. Check new backup
backup = r'D:\wechat\xwechat_files\Backup\LING827323180\ebc21d5d56a0a15e534c88e8f0132376\files\1'
for root, dirs, files in os.walk(backup):
    level = root.replace(backup, '').count(os.sep)
    indent = '  ' * level
    if level <= 3:
        print(f'{indent}{os.path.basename(root)}/ ({len(files)} files)')
    for f in sorted(files)[:5]:
        path = os.path.join(root, f)
        print(f'{indent}  {f} ({os.path.getsize(path)} bytes)')
    if len(files) > 5:
        print(f'{indent}  ... ({len(files) - 5} more)')
    if level >= 3: break

# 3. Check if message_0.db has more data
KEY = '4c64d04ecd632d43eaf1cccecd944c98388da266521f19ce855e07126f7d09e7'
tmp = msg0 + '.check2'
shutil.copy2(msg0, tmp)
db = sqlcipher3.connect(tmp)
c = db.cursor()
c.execute(f"PRAGMA key=\"x'{KEY}'\"")
c.execute('PRAGMA cipher_page_size=4096')
c.execute('PRAGMA kdf_iter=256000')
c.execute('PRAGMA cipher_compatibility=4')

c.execute('SELECT name FROM sqlite_master WHERE type="table" AND name LIKE "Msg_%"')
tables = [r[0] for r in c.fetchall()]

c.execute('SELECT user_name FROM Name2Id')
names = {r[0] for r in c.fetchall()}

print(f'\nMsg tables: {len(tables)}')
print(f'Name2Id entries: {len(names)}')

total = 0
for tbl in tables:
    c.execute(f'SELECT count(*) FROM "{tbl}"')
    cnt = c.fetchone()[0]
    total += cnt
    h = tbl[4:]
    uname = None
    for n in names:
        if hashlib.md5(n.encode()).hexdigest() == h:
            uname = n
            break
    if uname:
        print(f'  {uname}: {cnt} 条')

print(f'\n总计: {total} 条消息')

db.close()
os.remove(tmp)