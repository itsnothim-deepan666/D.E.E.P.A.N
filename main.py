# main.py
from db import init_db
from crawler import crawl_and_index

if __name__ == "__main__":
    init_db()
    crawl_and_index("C:\\")      # Windows
    # crawl_and_index("/")       # Linux