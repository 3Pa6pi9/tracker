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
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Global Geopolitical Intelligence Command Center", version="5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "tracker_data.db"

# --- HANDLE & MATRIX CONFIGURATIONS ---
RED_TARGETS = [
    {"handle": "@KingSalman", "region": "Middle East"},
    {"handle": "@MohamedBinZayed", "region": "Middle East"},
    {"handle": "@HHShkMohd", "region": "Middle East"},
    {"handle": "@TamimBinHamad", "region": "Middle East"},
    {"handle": "@RTErdogan", "region": "Middle East"},
    {"handle": "@netanyahu", "region": "Middle East"},
    {"handle": "@FaisalbinFarhan", "region": "Middle East"},
    {"handle": "@KSAMOFA", "region": "Middle East"},
    {"handle": "@KSAmofaEN", "region": "Middle East"},
    {"handle": "@ABZayed", "region": "Middle East"},
    {"handle": "@mofauae", "region": "Middle East"},
    {"handle": "@OFMUAE", "region": "Middle East"},
    {"handle": "@MBA_AlThani_", "region": "Middle East"},
    {"handle": "@MofaQatar_EN", "region": "Middle East"},
    {"handle": "@IsraelMFA", "region": "Middle East"},
    {"handle": "@araghchi", "region": "Middle East"},
    {"handle": "@IRIMFA_EN", "region": "Middle East"},
    {"handle": "@MFATurkiye", "region": "Middle East"}
]

RED_KEYWORDS = [
    "Muslim Brotherhood", "CAIR", "Migration Crisis", "Refugee Policies", "Border Security",
    "Illegal Immigration", "Sudan", "Somalia", "Iran", "Ukraine", "Russia",
    "Political Demonstrations", "Public Protests", "Parliament Debates", "Counter-Terrorism",
    "African countries", "Western countries"
]

GREEN_TARGETS = [
    # Africa
    {"handle": "@WilliamsRuto", "region": "Africa"},
    {"handle": "@PaulKagame", "region": "Africa"},
    {"handle": "@CyrilRamaphosa", "region": "Africa"},
    {"handle": "@officialABAT", "region": "Africa"},
    {"handle": "@AlsisiOfficial", "region": "Africa"},
    {"handle": "@MFAEthiopia", "region": "Africa"},
    {"handle": "@MusaliaMudavadi", "region": "Africa"},
    {"handle": "@ForeignOfficeKE", "region": "Africa"},
    {"handle": "@RonaldLamola", "region": "Africa"},
    {"handle": "@DIRCO_ZA", "region": "Africa"},
    {"handle": "@NigeriaMFA", "region": "Africa"},
    {"handle": "@MFAEgOfficial", "region": "Africa"},
    {"handle": "@MfaEgypt", "region": "Africa"},
    {"handle": "@UrugwiroVillage", "region": "Africa"},
    {"handle": "@NGRPresident", "region": "Africa"},
    # Europe
    {"handle": "@EmmanuelMacron", "region": "Europe"},
    {"handle": "@GiorgiaMeloni", "region": "Europe"},
    {"handle": "@sanchezcastejon", "region": "Europe"},
    {"handle": "@donaldtusk", "region": "Europe"},
    {"handle": "@_FriedrichMerz", "region": "Europe"},
    {"handle": "@bundeskanzler", "region": "Europe"},
    {"handle": "@AussenMinDE", "region": "Europe"},
    {"handle": "@AuswaertigesAmt", "region": "Europe"},
    {"handle": "@GermanyDiplo", "region": "Europe"},
    {"handle": "@Ed_Miliband", "region": "Europe"},
    {"handle": "@FCDOGovUK", "region": "Europe"}
]

GREEN_KEYWORDS = [
    "bilateral relations", "state visit", "diplomatic ties", "strategic dialogue",
    "ambassador meeting", "foreign ministry", "trade agreement", "foreign investment",
    "economic partnership", "trade deal", "sanctions", "memorandum of understanding",
    "MoU", "security partnership", "defense pact", "military agreement",
    "joint military exercise", "security cooperation", "defense treaty",
    "treaty signed", "international summit", "multilateral agreement",
    "UN resolution", "international convention", "global governance",
    "geopolitical shift", "resource diplomacy", "foreign influence", "strategic alliance"
]

GLOBAL_SEARCH_TOPICS = [
    "Geopolitics", "Bilateral Relations", "Trade Sanctions", 
    "Migration Crisis", "Foreign Policy", "Defense Treaty"
]

# --- WEBSOCKET CONNECTION MANAGER ---
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
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
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
            fetched_at TEXT
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_cat_src_reg ON news (category, source, region, published_date);')
    conn.commit()
    conn.close()

# --- SCRAPING ROUTINES ---
def save_items(items):
    conn = get_db_connection()
    c = conn.cursor()
    added = 0
    now_iso = datetime.now().isoformat()
    for item in items:
        try:
            c.execute('''
                INSERT INTO news (title, link, source, category, handle, region, published_date, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(link) DO NOTHING
            ''', (
                item['title'], item['link'], item['source'], item['category'],
                item.get('handle', 'N/A'), item.get('region', 'Global'),
                item['published_date'], now_iso
            ))
            if c.rowcount > 0:
                added += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return added

def fetch_feed_items(query, source_label, category, handle="N/A", region="Global", limit=8):
    encoded = urllib.parse.quote(query)
    items = []
    
    if source_label == "Google News":
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    elif source_label == "X (Twitter)":
        url = f"https://news.google.com/rss/search?q=site:x.com+OR+site:twitter.com+{encoded}&hl=en-US&gl=US&ceid=US:en"
    elif source_label == "Hacker News":
        url = f"https://hnrss.org/newest?q={encoded}"
    elif source_label == "Reddit":
        url = f"https://www.reddit.com/search.rss?q={encoded}&sort=new"
    else:
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"

    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:limit]:
            title = getattr(entry, 'title', '')
            link = getattr(entry, 'link', '')
            pub_date = getattr(entry, 'published', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            if title and link:
                items.append({
                    'title': title.replace(" - X", "").replace(" on X", ""),
                    'link': link,
                    'source': source_label,
                    'category': category,
                    'handle': handle,
                    'region': region,
                    'published_date': pub_date
                })
    except Exception as e:
        logger.error(f"Error fetching {source_label} for query '{query}': {e}")
    return items

def run_full_intel_sweep():
    logger.info("Executing comprehensive multi-source intelligence sweep...")
    total_new = 0
    
    # 1. Scraping Global / ALL Streams
    for topic in GLOBAL_SEARCH_TOPICS:
        total_new += save_items(fetch_feed_items(topic, "Google News", "ALL", region="Global"))
        total_new += save_items(fetch_feed_items(topic, "Reddit", "ALL", region="Global"))
        total_new += save_items(fetch_feed_items(topic, "Hacker News", "ALL", region="Global"))

    # 2. Scraping RED Zone Targets (X & Google Fallbacks)
    for target in RED_TARGETS:
        h = target["handle"]
        r = target["region"]
        query = f'"{h}"'
        total_new += save_items(fetch_feed_items(query, "X (Twitter)", "RED", handle=h, region=r))
        total_new += save_items(fetch_feed_items(query, "Google News", "RED", handle=h, region=r))

    # 3. Scraping GREEN Zone Targets (X & Google Fallbacks)
    for target in GREEN_TARGETS:
        h = target["handle"]
        r = target["region"]
        query = f'"{h}"'
        total_new += save_items(fetch_feed_items(query, "X (Twitter)", "GREEN", handle=h, region=r))
        total_new += save_items(fetch_feed_items(query, "Google News", "GREEN", handle=h, region=r))

    logger.info(f"Sweep completed. {total_new} new items indexed.")
    return total_new

async def async_sweep_task():
    added = await asyncio.to_thread(run_full_intel_sweep)
    if added > 0:
        await manager.broadcast(json.dumps({"event": "new_intel"}))

async def background_loop():
    while True:
        await asyncio.sleep(1200) # 20 minutes interval
        await async_sweep_task()

@app.on_event("startup")
async def startup_event():
    init_db()
    asyncio.create_task(background_loop())
    asyncio.create_task(async_sweep_task())

# --- REST ENDPOINTS ---
@app.get("/", response_class=FileResponse)
def read_root():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    root_path = os.path.join(BASE_DIR, "index.html")
    template_path = os.path.join(BASE_DIR, "templates", "index.html")
    if os.path.exists(root_path): return FileResponse(root_path)
    elif os.path.exists(template_path): return FileResponse(template_path)
    raise HTTPException(status_code=404, detail="index.html not found on server")

@app.websocket("/ws/news")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/api/sync")
async def trigger_manual_sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(async_sweep_task)
    return {"status": "Sync process initiated in background."}

@app.get("/api/news")
def get_news(
    category: str = Query("ALL"),
    source: str = Query("All"),
    region: str = Query("All"),
    handle: str = Query("All"),
    q: str = Query(None),
    page: int = Query(1),
    limit: int = Query(30)
):
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
        
    if q:
        query += " AND (title LIKE ? OR handle LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
        
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
    
    stats = {"dates": [], "ALL": [], "RED": [], "GREEN": []}
    temp_dict = {}
    for row in rows:
        d = row["date"]
        c = row["category"]
        if d not in temp_dict: temp_dict[d] = {"ALL": 0, "RED": 0, "GREEN": 0}
        if c in temp_dict[d]: temp_dict[d][c] = row["count"]
        
    for d in sorted(temp_dict.keys()):
        stats["dates"].append(d)
        stats["ALL"].append(temp_dict[d]["ALL"])
        stats["RED"].append(temp_dict[d]["RED"])
        stats["GREEN"].append(temp_dict[d]["GREEN"])
    return stats

@app.get("/api/export")
def export_csv(category: str = Query("ALL")):
    conn = get_db_connection()
    cursor = conn.cursor()
    if category.upper() == "ALL":
        cursor.execute("SELECT source, category, region, handle, title, link, published_date FROM news ORDER BY published_date DESC")
    else:
        cursor.execute("SELECT source, category, region, handle, title, link, published_date FROM news WHERE category = ? ORDER BY published_date DESC", (category.upper(),))
    rows = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Source", "Category", "Region", "Handle", "Intel Title", "Source URL", "Timestamp"])
    for row in rows: writer.writerow([row["source"], row["category"], row["region"], row["handle"], row["title"], row["link"], row["published_date"]])
    output.seek(0)
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=intel_export_{category}_{datetime.now().strftime('%Y%m%d')}.csv"
    return response

@app.delete("/api/cleanup/uae")
def trigger_uae_cleanup():
    uae_handles = ["@MohamedBinZayed", "@HHShkMohd", "@ABZayed", "@mofauae", "@OFMUAE"]
    conn = get_db_connection()
    cursor = conn.cursor()
    placeholders = ', '.join(['?'] * len(uae_handles))
    cursor.execute(f"DELETE FROM news WHERE handle IN ({placeholders}) OR title LIKE '%UAE%'", uae_handles)
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"Successfully purged {deleted_count} UAE records from database."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)