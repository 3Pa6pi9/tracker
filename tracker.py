import feedparser
import requests
import urllib.parse
import sqlite3
import schedule
import time
from datetime import datetime

KEYWORD = "Geopolitics"
X_BEARER_TOKEN = "YOUR_BEARER_TOKEN_HERE" 

def setup_db():
    conn = sqlite3.connect('tracker_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS content_tracker (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            link TEXT UNIQUE NOT NULL,
            published_at TEXT,
            fetched_at TEXT
        )
    ''')
    conn.commit()
    return conn

def save_to_db(conn, items):
    cursor = conn.cursor()
    new_count = 0
    for item in items:
        try:
            cursor.execute('''
                INSERT INTO content_tracker (source, title, link, published_at, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(link) DO NOTHING
            ''', (item['source'], item['title'], item['link'], item['published_at'], datetime.now().isoformat()))
            if cursor.rowcount > 0:
                new_count += 1
        except Exception:
            pass
    conn.commit()
    return new_count

def fetch_google_news(keyword, limit=10):
    try:
        encoded_keyword = urllib.parse.quote(keyword)
        rss_url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        return [{"source": "Google News", "title": entry.title, "link": entry.link, "published_at": entry.get('published', datetime.now().isoformat())} for entry in feed.entries[:limit]]
    except Exception:
        return []

def fetch_x_free_fallback(keyword, limit=10):
    try:
        query = f"site:x.com OR site:twitter.com {keyword}"
        encoded_query = urllib.parse.quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        return [{"source": "X (Twitter)", "title": entry.title.replace(" - X", "").replace(" on X", ""), "link": entry.link, "published_at": entry.get('published', datetime.now().isoformat())} for entry in feed.entries[:limit]]
    except Exception:
        return []

def fetch_hacker_news(keyword, limit=10):
    try:
        encoded_keyword = urllib.parse.quote(keyword)
        rss_url = f"https://hnrss.org/newest?q={encoded_keyword}"
        feed = feedparser.parse(rss_url)
        return [{"source": "Hacker News", "title": entry.title, "link": entry.link, "published_at": entry.get('published', datetime.now().isoformat())} for entry in feed.entries[:limit]]
    except Exception:
        return []

def fetch_reddit(keyword, limit=10):
    try:
        encoded_keyword = urllib.parse.quote(keyword)
        rss_url = f"https://www.reddit.com/search.rss?q={encoded_keyword}&sort=new"
        feed = feedparser.parse(rss_url, agent="IntelTrackerBot/2.0")
        return [{"source": "Reddit", "title": entry.title, "link": entry.link, "published_at": entry.get('published', datetime.now().isoformat())} for entry in feed.entries[:limit]]
    except Exception:
        return []

def fetch_and_store_job():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running automated background sync for '{KEYWORD}'...")
    conn = setup_db()
    save_to_db(conn, fetch_google_news(KEYWORD, limit=15))
    save_to_db(conn, fetch_x_free_fallback(KEYWORD, limit=15))
    save_to_db(conn, fetch_hacker_news(KEYWORD, limit=10))
    save_to_db(conn, fetch_reddit(KEYWORD, limit=10))
    conn.close()
    print("Background sync complete.")

def main():
    fetch_and_store_job()
    schedule.every(30).minutes.do(fetch_and_store_job)
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()