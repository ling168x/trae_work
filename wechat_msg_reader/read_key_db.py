"""查看 key_info.db - 未加密的 SQLite"""
import sqlite3

db_path = r'D:\wechat\xwechat_files\all_users\login\LING827323180\key_info.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 查看所有表
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print(f"表: {tables}")

for t in tables:
    c.execute(f"SELECT * FROM '{t}'")
    rows = c.fetchall()
    print(f"\n=== {t} ({len(rows)} rows) ===")
    # 获取列名
    c.execute(f"PRAGMA table_info('{t}')")
    cols = [r[1] for r in c.fetchall()]
    print(f"列: {cols}")
    for row in rows[:10]:
        print(f"  {row}")

conn.close()