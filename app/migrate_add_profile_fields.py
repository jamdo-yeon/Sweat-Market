# scripts/migrate_add_profile_fields.py
import os, sqlite3, sys
from urllib.parse import urlparse

def _sqlite_path_from_url(url: str) -> str:
    # supports sqlite:///./file.db or sqlite:////abs/path.db
    if url.startswith("sqlite:///"):
        path = url[len("sqlite:///"):]
        if path.startswith("./"):
            path = os.path.abspath(path)
        return path
    if url.startswith("sqlite:////"):
        return url[len("sqlite:////")-1:]  # keep leading '/'
    # fallback: treat as plain path
    return url

DB_URL = os.getenv("DATABASE_URL", "sqlite:///./sweatmarket.db")
DB_PATH = _sqlite_path_from_url(DB_URL)

print(f"[migrate] DATABASE_URL={DB_URL}")
print(f"[migrate] DB_PATH={DB_PATH}")

if not os.path.exists(DB_PATH):
    print(f"[migrate] ERROR: DB file not found at {DB_PATH}", file=sys.stderr)
    sys.exit(1)

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

def has_column(table: str, col: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    return col in cols

def add_column_if_missing(table: str, col_stmt: str):
    # col_stmt example: "is_active INTEGER NOT NULL DEFAULT 1"
    col_name = col_stmt.split()[0]
    if has_column(table, col_name):
        print(f"[migrate] {table}.{col_name} already exists - skip")
        return
    sql = f"ALTER TABLE {table} ADD COLUMN {col_stmt}"
    print(f"[migrate] {sql}")
    cur.execute(sql)

try:
    # core auth fields we saw missing on your machine
    add_column_if_missing("users", "is_active INTEGER NOT NULL DEFAULT 1")
    add_column_if_missing("users", "email_confirmed_at TIMESTAMP NULL")
    add_column_if_missing("users", "created_at TIMESTAMP NULL")

    # new profile fields
    add_column_if_missing("users", "nickname TEXT")
    add_column_if_missing("users", "birth_date DATE")
    add_column_if_missing("users", "gender TEXT")
    add_column_if_missing("users", "avatar_url TEXT")

    conn.commit()
    print("[migrate] Done.")
except Exception as e:
    conn.rollback()
    print(f"[migrate] ERROR: {e}", file=sys.stderr)
    raise
finally:
    conn.close()