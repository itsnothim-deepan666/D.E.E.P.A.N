import sqlite3

conn = sqlite3.connect("files.db")
cursor = conn.cursor()

directories = cursor.execute("select name, path from directories").fetchall()
#print(directories)
if "Downloads" in [d[0] for d in directories]:
    print("Downloads directory exists in DB")
    for i in directories:
        if i[0] == "Downloads":
            print (i)
            print("Downloads path:", i[0])