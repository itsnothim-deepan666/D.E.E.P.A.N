# db.py
import sqlite3

def init_db(db_path="files.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS files (
        path TEXT PRIMARY KEY,
        name TEXT,
        extension TEXT,
        size INTEGER,
        modified REAL
    )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_name ON files(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext ON files(extension)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_modified ON files(modified)")

    conn.commit()
    conn.close()