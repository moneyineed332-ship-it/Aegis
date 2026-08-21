import sqlite3
db = sqlite3.connect('data/aegis.db')
tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'").fetchall()]
for t in tables:
    cols = [d[1] for d in db.execute(f"PRAGMA table_info({t})").fetchall()]
    cnt = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"{t}: {cnt} rows | cols={cols}")
db.close()
