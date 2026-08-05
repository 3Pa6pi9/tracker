from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
import sqlite3
import uvicorn
import os
import feedparser
import urllib.parse
from datetime import datetime

app = FastAPI()

if not os.path.exists("templates"):
    os.makedirs("templates")

templates = Jinja2Templates(directory="templates")

def get_db_connection():
    conn = sqlite3.connect('tracker_data.db')
    conn.row_factory = sqlite3.Row
    return conn

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
    conn.close()

setup_db()

def save_to_db(items):
    conn = get_db_connection()
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
    conn.close()

def fetch_google_news(keyword, limit=5):
    try:
        encoded = urllib.parse.quote(keyword)
        feed = feedparser.parse(f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en")
        return [{"source": "Google News", "title": e.title, "link": e.link, "published_at": e.get('published', datetime.now().isoformat())} for e in feed.entries[:limit]]
    except Exception:
        return []

def fetch_x_free_fallback(keyword, limit=5):
    try:
        encoded = urllib.parse.quote(f"site:x.com OR site:twitter.com {keyword}")
        feed = feedparser.parse(f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en")
        return [{"source": "X (Twitter)", "title": e.title.replace(" - X", "").replace(" on X", ""), "link": e.link, "published_at": e.get('published', datetime.now().isoformat())} for e in feed.entries[:limit]]
    except Exception:
        return []

def fetch_hacker_news(keyword, limit=5):
    try:
        feed = feedparser.parse(f"https://hnrss.org/newest?q={urllib.parse.quote(keyword)}")
        return [{"source": "Hacker News", "title": e.title, "link": e.link, "published_at": e.get('published', datetime.now().isoformat())} for e in feed.entries[:limit]]
    except Exception:
        return []

def fetch_reddit(keyword, limit=5):
    try:
        feed = feedparser.parse(f"https://www.reddit.com/search.rss?q={urllib.parse.quote(keyword)}&sort=new", agent="IntelEngine/2.0")
        return [{"source": "Reddit", "title": e.title, "link": e.link, "published_at": e.get('published', datetime.now().isoformat())} for e in feed.entries[:limit]]
    except Exception:
        return []

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/stats")
async def get_stats():
    try:
        conn = get_db_connection()
        total = conn.execute("SELECT COUNT(*) FROM content_tracker").fetchone()[0]
        sources = conn.execute("SELECT source, COUNT(*) as count FROM content_tracker GROUP BY source").fetchall()
        conn.close()
        return {
            "total_items": total,
            "sources": {row["source"]: row["count"] for row in sources}
        }
    except Exception:
        return {"total_items": 0, "sources": {}}

@app.get("/api/news")
async def get_news(q: str = None):
    try:
        conn = get_db_connection()
        if q:
            search_query = f"%{q}%"
            items = conn.execute(
                'SELECT * FROM content_tracker WHERE title LIKE ? ORDER BY fetched_at DESC LIMIT 150', 
                (search_query,)
            ).fetchall()
            
            if not items:
                live_items = []
                live_items.extend(fetch_google_news(q, limit=6))
                live_items.extend(fetch_x_free_fallback(q, limit=6))
                live_items.extend(fetch_hacker_news(q, limit=6))
                live_items.extend(fetch_reddit(q, limit=6))
                
                if live_items:
                    save_to_db(live_items)
                    items = conn.execute(
                        'SELECT * FROM content_tracker WHERE title LIKE ? ORDER BY fetched_at DESC LIMIT 150', 
                        (search_query,)
                    ).fetchall()
        else:
            items = conn.execute(
                'SELECT * FROM content_tracker ORDER BY fetched_at DESC LIMIT 60'
            ).fetchall()
        
        conn.close()
        return [dict(ix) for ix in items]
    except Exception:
        return []

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)