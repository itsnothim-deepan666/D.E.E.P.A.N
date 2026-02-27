# crawler.py
import os
import sqlite3
import time

BATCH_SIZE = 1000


def crawl_and_index(root_path, db_path="files.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    batch = []
    total = 0
    start_time = time.time()

    for root, dirs, files in os.walk(root_path):
        for file in files:
            full_path = os.path.join(root, file)

            try:
                stat = os.stat(full_path)
            except (PermissionError, FileNotFoundError):
                continue

            name, ext = os.path.splitext(file)

            batch.append((
                full_path,
                name,
                ext.lower(),
                stat.st_size,
                stat.st_mtime
            ))

            if len(batch) >= BATCH_SIZE:
                cursor.executemany("""
                INSERT OR REPLACE INTO files
                (path, name, extension, size, modified)
                VALUES (?, ?, ?, ?, ?)
                """, batch)
                conn.commit()
                total += len(batch)
                batch.clear()

    # Insert remaining
    if batch:
        cursor.executemany("""
        INSERT OR REPLACE INTO files
        (path, name, extension, size, modified)
        VALUES (?, ?, ?, ?, ?)
        """, batch)
        conn.commit()
        total += len(batch)

    conn.close()

    print(f"Indexed {total} files in {time.time() - start_time:.2f}s")
