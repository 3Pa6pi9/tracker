from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
import sqlite3
import uvicorn
import logging
import csv
import io
import json
import os
import asyncio
import feedparser
import urllib.parse
import httpx
import time
from datetime import datetime

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Global Geopolitical Intelligence Command Center", version="12.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "tracker_data.db"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# --- MEDIA OUTLETS & TARGETS ---
DIRECT_FEEDS = [
    {"url": "https://www.aljazeera.com/xml/rss/all.xml", "source": "Al Jazeera", "category": "RED", "region": "Middle East", "keyword": "Feed: Al Jazeera"},
    {"url": "https://www.middleeasteye.net/rss", "source": "Middle East Eye", "category": "RED", "region": "Middle East", "keyword": "Feed: Middle East Eye"},
    {"url": "https://www.arabnews.com/cat/1/rss.xml", "source": "Arab News", "category": "RED", "region": "Middle East", "keyword": "Feed: Arab News"},
    {"url": "https://www.timesofisrael.com/feed/", "source": "Times of Israel", "category": "RED", "region": "Middle East", "keyword": "Feed: Times of Israel"},
    {"url": "https://www.africanews.com/feed/", "source": "Africanews", "category": "GENERAL", "region": "Africa", "keyword": "Feed: Africanews"},
    {"url": "https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf", "source": "AllAfrica", "category": "GENERAL", "region": "Africa", "keyword": "Feed: AllAfrica"},
    {"url": "https://rss.dw.com/rdf/rss-en-world", "source": "DW News", "category": "GENERAL", "region": "Europe", "keyword": "Feed: DW News"},
    {"url": "http://feeds.bbci.co.uk/news/world/rss.xml", "source": "BBC World", "category": "ALL", "region": "Global", "keyword": "Feed: BBC World"},
    {"url": "https://news.google.com/rss/search?q=geopolitics+OR+diplomacy+OR+sanctions&hl=en-US&gl=US&ceid=US:en", "source": "Google News", "category": "ALL", "region": "Global", "keyword": "Topic: Geopolitics/Diplomacy"}
]

RED_TARGETS = [{"handle": h, "region": "Middle East"} for h in [
    "@KingSalman", "@MohamedBinZayed", "@HHShkMohd", "@TamimBinHamad", "@RTErdogan", "@netanyahu", 
    "@FaisalbinFarhan", "@KSAMOFA", "@KSAmofaEN", "@ABZayed", "@mofauae", "@OFMUAE", "@MBA_AlThani_", 
    "@MofaQatar_EN", "@IsraelMFA", "@araghchi", "@IRIMFA_EN", "@MFATurkiye"
]]

GENERAL_TARGETS = [{"handle": h, "region": "Africa"} for h in [
    "@WilliamsRuto", "@PaulKagame", "@CyrilRamaphosa", "@officialABAT", "@AlsisiOfficial", "@MFAEthiopia", 
    "@MusaliaMudavadi", "@ForeignOfficeKE", "@RonaldLamola", "@DIRCO_ZA", "@NigeriaMFA", "@MFAEgOfficial", 
    "@MfaEgypt", "@UrugwiroVillage", "@NGRPresident"
]] + [{"handle": h, "region": "Europe"} for h in [
    "@EmmanuelMacron", "@GiorgiaMeloni", "@sanchezcastejon", "@donaldtusk", "@_FriedrichMerz", "@bundeskanzler", 
    "@AussenMinDE", "@AuswaertigesAmt", "@GermanyDiplo", "@Ed_Miliband", "@FCDOGovUK"
]]

GLOBAL_SEARCH_TOPICS = [
    "Geopolitics", "Bilateral Relations", "Trade Sanctions", 
    "Foreign Policy", "POTUS", "White House", "US President",
    "Pentagon", "Kremlin", "NATO"
]

# --- WEBSOCKET MANAGER ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections.copy():
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

# --- DATABASE ENGINE (WAL OPTIMIZATION) ---
def get_db_connection():
    conn = sqlite3.connect(DB_NAME, timeout=15)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            link TEXT UNIQUE,
            source TEXT,
            category TEXT,
            handle TEXT,
            region TEXT,
            published_date TEXT,
            fetched_at TEXT,
            keyword TEXT
        )
    ''')
    c.execute("PRAGMA table_info(news)")
    cols = [col[1] for col in c.fetchall()]
    if "keyword" not in cols:
        try: c.execute("ALTER TABLE news ADD COLUMN keyword TEXT DEFAULT 'N/A'")
        except Exception: pass
    c.execute('CREATE INDEX IF NOT EXISTS idx_cat_src_reg ON news (category, source, region, published_date);')
    conn.commit()
    conn.close()

def save_items_bulk(items):
    if not items: return 0
    conn = get_db_connection()
    c = conn.cursor()
    added = 0
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for item in items:
        try:
            c.execute('''
                INSERT INTO news (title, link, source, category, handle, region, published_date, fetched_at, keyword)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(link) DO NOTHING
            ''', (
                item['title'], item['link'], item['source'], item['category'],
                item.get('handle', 'N/A'), item.get('region', 'Global'),
                item['published_date'], now_iso, item.get('keyword', 'N/A')
            ))
            if c.rowcount > 0:
                added += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return added

# --- ASYNC HIGH-SPEED SCRAPER ---
async def fetch_feed_async(client, url, source_label, category, handle="N/A", region="Global", keyword="N/A", limit=10):
    items = []
    try:
        response = await client.get(url, timeout=10.0, follow_redirects=True)
        response.raise_for_status()
        
        feed = await asyncio.to_thread(feedparser.parse, response.content)
        
        for entry in feed.entries[:limit]:
            title = getattr(entry, 'title', '')
            link = getattr(entry, 'link', '')
            
            try:
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = time.strftime("%Y-%m-%d %H:%M:%S", entry.published_parsed)
                else:
                    pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if title and link:
                items.append({
                    'title': title.replace(" - X", "").replace(" on X", "").strip(),
                    'link': link,
                    'source': source_label,
                    'category': category,
                    'handle': handle,
                    'region': region,
                    'published_date': pub_date,
                    'keyword': keyword
                })
    except Exception as e:
        logger.debug(f"Failed to fetch {url}: {str(e)}")
    return items

async def run_live_web_search_async(q_text: str, category: str = "ALL"):
    """Performs an on-the-fly live web search for user queries."""
    encoded = urllib.parse.quote(q_text)
    tasks = []
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        # 1. Google News Live Query
        tasks.append(fetch_feed_async(client, f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en", "Google News", category, keyword=f"Live Search: {q_text}"))
        # 2. Reddit Live Query
        tasks.append(fetch_feed_async(client, f"https://www.reddit.com/search.rss?q={encoded}&sort=new", "Reddit", category, keyword=f"Live Search: {q_text}"))
        # 3. X (Twitter) Live Query
        tasks.append(fetch_feed_async(client, f"https://news.google.com/rss/search?q={encoded}+site:twitter.com+OR+site:x.com&hl=en-US&gl=US&ceid=US:en", "X (Twitter)", category, keyword=f"Live Search: {q_text}"))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_new = []
        for res in results:
            if isinstance(res, list): all_new.extend(res)
        
        if all_new:
            await asyncio.to_thread(save_items_bulk, all_new)

async def run_fast_sweep():
    logger.info("Executing Enterprise-Grade Async Sweep...")
    tasks = []
    
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        # Direct Feeds
        for feed in DIRECT_FEEDS:
            tasks.append(fetch_feed_async(client, feed["url"], feed["source"], feed["category"], region=feed["region"], keyword=feed.get("keyword", "Direct Feed")))

        # Global Topics
        for topic in GLOBAL_SEARCH_TOPICS:
            encoded = urllib.parse.quote(topic)
            tasks.append(fetch_feed_async(client, f"https://www.reddit.com/search.rss?q={encoded}&sort=new", "Reddit", "ALL", region="Global", keyword=f"Topic: {topic}"))
            tasks.append(fetch_feed_async(client, f"https://hnrss.org/newest?q={encoded}", "Hacker News", "ALL", region="Global", keyword=f"Topic: {topic}"))

        # Target Handles
        for category, target_list in [("RED", RED_TARGETS), ("GENERAL", GENERAL_TARGETS)]:
            for target in target_list:
                h = target["handle"]
                r = target["region"]
                encoded_h = urllib.parse.quote(h)
                tasks.append(fetch_feed_async(client, f"https://news.google.com/rss/search?q={encoded_h}&hl=en-US&gl=US&ceid=US:en", "Google News", category, handle=h, region=r, keyword=f"Target: {h}"))
                tasks.append(fetch_feed_async(client, f"https://news.google.com/rss/search?q={encoded_h}+site:twitter.com+OR+site:x.com&hl=en-US&gl=US&ceid=US:en", "X (Twitter)", category, handle=h, region=r, keyword=f"Target: {h}"))

        all_results = []
        batch_size = 15
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i+batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            for res in batch_results:
                if isinstance(res, list): all_results.extend(res)
            await asyncio.sleep(0.3)

        total_new = await asyncio.to_thread(save_items_bulk, all_results)
        return total_new

is_syncing = False

async def async_sweep_controller(silent=False):
    global is_syncing
    if is_syncing: return
    is_syncing = True

    event_start = "sync_started_silent" if silent else "sync_started"
    await manager.broadcast(json.dumps({"event": event_start}))

    try:
        total_added = await run_fast_sweep()
        timestamp = datetime.now().strftime("%I:%M %p")

        if total_added > 0:
            await manager.broadcast(json.dumps({"event": "new_intel", "count": total_added, "silent": silent, "time": timestamp}))
        else:
            await manager.broadcast(json.dumps({"event": "sync_finished_no_data", "silent": silent, "time": timestamp}))
    except Exception as e:
        logger.error(f"Sweep failed: {e}")
        await manager.broadcast(json.dumps({"event": "sync_error"}))
    finally:
        is_syncing = False

async def background_loop():
    while True:
        await asyncio.sleep(900) # 15 min Auto-Pilot
        await async_sweep_controller(silent=True)

@app.on_event("startup")
async def startup_event():
    init_db()
    asyncio.create_task(background_loop())
    asyncio.create_task(async_sweep_controller(silent=True))

# --- API ENDPOINTS ---
@app.get("/", response_class=FileResponse)
def read_root():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    root_path = os.path.join(BASE_DIR, "index.html")
    template_path = os.path.join(BASE_DIR, "templates", "index.html")
    if os.path.exists(root_path): return FileResponse(root_path)
    elif os.path.exists(template_path): return FileResponse(template_path)
    raise HTTPException(status_code=404, detail="index.html not found on server")

@app.get("/api/ping")
def ping():
    return {"status": "awake"}

@app.websocket("/ws/news")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/api/sync")
async def trigger_manual_sync(background_tasks: BackgroundTasks, silent: bool = False):
    global is_syncing
    if is_syncing: return {"status": "Sync already in progress."}
    background_tasks.add_task(async_sweep_controller, silent)
    return {"status": "Sync process initiated."}

@app.get("/api/news")
async def get_news(
    category: str = Query("ALL"), source: str = Query("All"),
    region: str = Query("All"), handle: str = Query("All"),
    time_filter: str = Query("all"), q: str = Query(None),
    page: int = Query(1), limit: int = Query(30)
):
    # ON-THE-FLY LIVE SEARCH TRIGGER
    if q and len(q.strip()) > 1:
        await run_live_web_search_async(q.strip(), category)

    offset = (page - 1) * limit
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM news WHERE 1=1"
    params = []
    
    if category.upper() != "ALL":
        query += " AND category = ?"
        params.append(category.upper())
        
    if source != "All":
        query += " AND source = ?"
        params.append(source)

    if region != "All":
        query += " AND region = ?"
        params.append(region)

    if handle != "All":
        query += " AND handle = ?"
        params.append(handle)

    if time_filter == "1d":
        query += " AND datetime(published_date) >= datetime('now', '-1 day')"
    elif time_filter == "7d":
        query += " AND datetime(published_date) >= datetime('now', '-7 days')"
    elif time_filter == "30d":
        query += " AND datetime(published_date) >= datetime('now', '-30 days')"

    if q:
        query += " AND (title LIKE ? OR handle LIKE ? OR source LIKE ? OR keyword LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])
        
    query += " ORDER BY datetime(published_date) DESC, id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/api/meta/filters")
def get_filter_metadata():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT region FROM news WHERE region IS NOT NULL AND region != ''")
    regions = [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT handle FROM news WHERE handle IS NOT NULL AND handle != 'N/A'")
    handles = [h[0] for h in cursor.fetchall()]
    conn.close()
    return {"regions": regions, "handles": handles}

@app.get("/api/stats")
def get_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date(published_date) as date, category, COUNT(*) as count 
        FROM news 
        WHERE published_date IS NOT NULL 
        GROUP BY date(published_date), category
        ORDER BY date(published_date) ASC
        LIMIT 14
    """)
    rows = cursor.fetchall()
    conn.close()
    
    stats = {"dates": [], "ALL": [], "RED": [], "GENERAL": []}
    temp_dict = {}
    for row in rows:
        d = row["date"]
        c = row["category"]
        if d not in temp_dict: temp_dict[d] = {"ALL": 0, "RED": 0, "GENERAL": 0}
        if c in temp_dict[d]: temp_dict[d][c] = row["count"]
        
    for d in sorted(temp_dict.keys()):
        stats["dates"].append(d)
        stats["ALL"].append(temp_dict[d]["ALL"])
        stats["RED"].append(temp_dict[d]["RED"])
        stats["GENERAL"].append(temp_dict[d]["GENERAL"])
    return stats

@app.get("/api/export")
def export_csv(category: str = Query("ALL")):
    conn = get_db_connection()
    cursor = conn.cursor()
    if category.upper() == "ALL":
        cursor.execute("SELECT source, category, region, handle, keyword, title, link, published_date FROM news ORDER BY published_date DESC")
    else:
        cursor.execute("SELECT source, category, region, handle, keyword, title, link, published_date FROM news WHERE category = ? ORDER BY published_date DESC", (category.upper(),))
    rows = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Source", "Category", "Region", "Handle", "Keyword Trigger", "Intel Title", "Source URL", "Timestamp"])
    for row in rows: writer.writerow([row["source"], row["category"], row["region"], row["handle"], row.get("keyword", "N/A"), row["title"], row["link"], row["published_date"]])
    output.seek(0)
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=intel_export_{category}_{datetime.now().strftime('%Y%m%d')}.csv"
    return response

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)