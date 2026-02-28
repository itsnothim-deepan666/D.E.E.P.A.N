# crawler.py
import os
import sqlite3
import time

BATCH_SIZE = 1000


def crawl_and_index(root_path, db_path="files.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    file_batch = []
    dir_batch = []
    total_files = 0
    total_dirs = 0
    start_time = time.time()

    for root, dirs, files in os.walk(root_path):
        for d in dirs:
            dir_path = os.path.join(root, d)
            try:
                stat = os.stat(dir_path)
            except (PermissionError, FileNotFoundError):
                continue

            dir_batch.append((
                dir_path,
                d,
                root,
                stat.st_mtime
            ))

            if len(dir_batch) >= BATCH_SIZE:
                cursor.executemany("""
                INSERT OR REPLACE INTO directories
                (path, name, parent, modified)
                VALUES (?, ?, ?, ?)
                """, dir_batch)
                conn.commit()
                total_dirs += len(dir_batch)
                dir_batch.clear()

        for file in files:
            full_path = os.path.join(root, file)

            try:
                stat = os.stat(full_path)
            except (PermissionError, FileNotFoundError):
                continue

            name, ext = os.path.splitext(file)

            file_batch.append((
                full_path,
                name,
                ext.lower(),
                stat.st_size,
                stat.st_mtime
            ))

            if len(file_batch) >= BATCH_SIZE:
                cursor.executemany("""
                INSERT OR REPLACE INTO files
                (path, name, extension, size, modified)
                VALUES (?, ?, ?, ?, ?)
                """, file_batch)
                conn.commit()
                total_files += len(file_batch)
                file_batch.clear()

    # Insert remaining files
    if file_batch:
        cursor.executemany("""
        INSERT OR REPLACE INTO files
        (path, name, extension, size, modified)
        VALUES (?, ?, ?, ?, ?)
        """, file_batch)
        conn.commit()
        total_files += len(file_batch)

    # Insert remaining directories
    if dir_batch:
        cursor.executemany("""
        INSERT OR REPLACE INTO directories
        (path, name, parent, modified)
        VALUES (?, ?, ?, ?)
        """, dir_batch)
        conn.commit()
        total_dirs += len(dir_batch)

    conn.close()

    print(f"Indexed {total_files} files and {total_dirs} directories in {time.time() - start_time:.2f}s")
