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

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Global Geopolitical Intelligence Command Center", version="18.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "tracker_data.db"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# --- THREAT CLASSIFIER WEIGHTS ---
CRITICAL_WORDS = ["war", "strike", "attack", "missile", "assassination", "conflict", "explosion", "invasion", "military action", "airstrike", "casualty", "nuclear", "killing", "bombing"]
ELEVATED_WORDS = ["sanctions", "protest", "tension", "warning", "ban", "dispute", "standoff", "threat", "cyberattack", "unrest", "crisis", "drill", "deployment"]

# --- COMPREHENSIVE KEYWORD MATRICES ---
RED_KEYWORDS = [
    "muslim brotherhood", "cair", "migration crisis", "refugee", "border security",
    "illegal immigration", "sudan", "somalia", "iran", "ukraine", "russia",
    "demonstration", "protest", "parliament", "counter-terrorism", "terror",
    "israel", "gaza", "palestine", "hamas", "hezbollah", "lebanon", "syria",
    "yemen", "houthi", "saudi", "qatar", "uae", "turkey", "egypt", "iraq",
    "strike", "war", "military", "troops", "defense", "missile", "security",
    "conflict", "unrest", "attack", "border", "ceasefire", "peace", "hostage",
    "forces", "army", "netanyahu", "erdogan", "salman", "zayed", "araghchi",
    "red sea", "drone", "sanctions", "crisis", "airstrike", "casualty", "retaliation",
    "african countries", "western countries", "middle east", "idf", "mfa"
]

GENERAL_KEYWORDS = [
    "bilateral", "state visit", "diplomatic", "diplomacy", "strategic dialogue",
    "ambassador", "foreign ministry", "trade agreement", "foreign investment",
    "economic partnership", "trade deal", "sanctions", "memorandum of understanding",
    "mou", "security partnership", "defense pact", "military agreement",
    "joint military exercise", "security cooperation", "defense treaty",
    "treaty", "summit", "multilateral", "un resolution", "convention",
    "global governance", "geopolitical", "resource diplomacy", "foreign influence",
    "strategic alliance", "kenya", "rwanda", "south africa", "nigeria", "ethiopia",
    "france", "germany", "spain", "poland", "uk", "britain", "eu", "european union",
    "african union", "macron", "meloni", "ruto", "kagame", "ramaphosa", "sanchez",
    "tusk", "scholz", "merz", "cooperation", "talks", "envoy", "minister", "president",
    "prime minister", "foreign policy", "aid", "development", "agreement", "pact"
]

GLOBAL_SEARCH_TOPICS = [
    "Geopolitics", "Bilateral Relations", "Trade Sanctions", 
    "Foreign Policy", "POTUS", "White House", "US President",
    "Pentagon", "Kremlin", "NATO", "Middle East Crisis", "Red Sea Security"
]

DIRECT_FEEDS = [
    {"url": "https://www.aljazeera.com/xml/rss/all.xml", "source": "Al Jazeera", "category": "RED", "region": "Middle East"},
    {"url": "https://www.middleeasteye.net/rss", "source": "Middle East Eye", "category": "RED", "region": "Middle East"},
    {"url": "https://www.arabnews.com/cat/1/rss.xml", "source": "Arab News", "category": "RED", "region": "Middle East"},
    {"url": "https://www.timesofisrael.com/feed/", "source": "Times of Israel", "category": "RED", "region": "Middle East"},
    {"url": "https://news.google.com/rss/search?q=Middle+East+conflict+OR+Gaza+OR+Iran&hl=en-US&gl=US&ceid=US:en", "source": "Google News", "category": "RED", "region": "Middle East"},
    {"url": "https://www.africanews.com/feed/", "source": "Africanews", "category": "GENERAL", "region": "Africa"},
    {"url": "https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf", "source": "AllAfrica", "category": "GENERAL", "region": "Africa"},
    {"url": "https://rss.dw.com/rdf/rss-en-world", "source": "DW News", "category": "GENERAL", "region": "Europe"},
    {"url": "https://news.google.com/rss/search?q=Africa+diplomacy+OR+EU+foreign+policy&hl=en-US&gl=US&ceid=US:en", "source": "Google News", "category": "GENERAL", "region": "Global"},
    {"url": "http://feeds.bbci.co.uk/news/world/rss.xml", "source": "BBC World", "category": "ALL", "region": "Global"}
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

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, timeout=10)
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
            keyword TEXT,
            threat_level TEXT DEFAULT 'INFORMATIONAL'
        )
    ''')
    c.execute("PRAGMA table_info(news)")
    cols = [col[1] for col in c.fetchall()]
    if "keyword" not in cols:
        try: c.execute("ALTER TABLE news ADD COLUMN keyword TEXT DEFAULT 'N/A'")
        except Exception: pass
    if "threat_level" not in cols:
        try: c.execute("ALTER TABLE news ADD COLUMN threat_level TEXT DEFAULT 'INFORMATIONAL'")
        except Exception: pass
        
    c.execute('CREATE INDEX IF NOT EXISTS idx_cat_src_reg ON news (category, source, region, published_date);')
    conn.commit()
    conn.close()

# --- NEW KEYWORD DENSITY HEAT SCORE CLASSIFIER ---
def classify_threat_by_heat(title):
    t_lower = title.lower()
    heat_score = 0
    
    # +1 Point for every base regional/category keyword hit
    all_base_kws = set([k.lower() for k in RED_KEYWORDS + GENERAL_KEYWORDS])
    for kw in all_base_kws:
        if kw in t_lower:
            heat_score += 1
            
    # +1 Point for tension/elevated words
    for ew in ELEVATED_WORDS:
        if ew.lower() in t_lower:
            heat_score += 1

    # +2 Points for combat/fatal words
    for cw in CRITICAL_WORDS:
        if cw.lower() in t_lower:
            heat_score += 2
            
    # Matrix Evaluation
    if heat_score >= 3:
        return "CRITICAL"
    elif heat_score >= 1:
        return "ELEVATED"
    else:
        return "INFORMATIONAL"

def save_items_bulk(items):
    if not items: return 0
    conn = get_db_connection()
    c = conn.cursor()
    added = 0
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for item in items:
        try:
            c.execute('''
                INSERT INTO news (title, link, source, category, handle, region, published_date, fetched_at, keyword, threat_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(link) DO NOTHING
            ''', (
                item['title'], item['link'], item['source'], item['category'],
                item.get('handle', 'N/A'), item.get('region', 'Global'),
                item['published_date'], now_iso, item.get('keyword', 'N/A'),
                item.get('threat_level', 'INFORMATIONAL')
            ))
            if c.rowcount > 0:
                added += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return added

async def fetch_feed_max_speed(client, semaphore, url, source_label, category, handle="N/A", region="Global", keyword_badge="N/A", filter_keywords=None, limit=40):
    items = []
    async with semaphore:
        try:
            response = await client.get(url, timeout=4.0, follow_redirects=True)
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
                    actual_badge = keyword_badge
                    text_lower = title.lower()

                    if filter_keywords:
                        matched_kw = next((kw for kw in filter_keywords if kw in text_lower), None)
                        
                        handle_clean = handle.replace("@", "").lower() if handle != "N/A" else ""
                        if not matched_kw and handle_clean and handle_clean in text_lower:
                            matched_kw = handle
                            
                        if not matched_kw:
                            continue
                            
                        actual_badge = f"Matched: '{matched_kw}'"
                    
                    items.append({
                        'title': title.replace(" - X", "").replace(" on X", "").strip(),
                        'link': link,
                        'source': source_label,
                        'category': category,
                        'handle': handle,
                        'region': region,
                        'published_date': pub_date,
                        'keyword': actual_badge,
                        'threat_level': classify_threat_by_heat(title)
                    })
        except Exception:
            pass
    return items

async def run_live_web_search_async(q_text: str, category: str = "ALL"):
    encoded = urllib.parse.quote(q_text)
    semaphore = asyncio.Semaphore(60)
    limits = httpx.Limits(max_keepalive_connections=60, max_connections=120)
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, limits=limits) as client:
        tasks = [
            fetch_feed_max_speed(client, semaphore, f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en", "Google News", category, keyword_badge=f"Live Search: {q_text}"),
            fetch_feed_max_speed(client, semaphore, f"https://www.reddit.com/search.rss?q={encoded}&sort=new", "Reddit", category, keyword_badge=f"Live Search: {q_text}"),
            fetch_feed_max_speed(client, semaphore, f"https://news.google.com/rss/search?q={encoded}+site:twitter.com+OR+site:x.com&hl=en-US&gl=US&ceid=US:en", "X (Twitter)", category, keyword_badge=f"Live Search: {q_text}")
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_new = []
        for res in results:
            if isinstance(res, list): all_new.extend(res)
        if all_new:
            await asyncio.to_thread(save_items_bulk, all_new)

async def run_fast_sweep():
    logger.info("Executing Maximum Yield Concurrency Sweep...")
    tasks = []
    semaphore = asyncio.Semaphore(60)
    limits = httpx.Limits(max_keepalive_connections=60, max_connections=120)
    
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, limits=limits) as client:
        for feed in DIRECT_FEEDS:
            kw_filter = RED_KEYWORDS if feed["category"] == "RED" else GENERAL_KEYWORDS if feed["category"] == "GENERAL" else None
            tasks.append(fetch_feed_max_speed(client, semaphore, feed["url"], feed["source"], feed["category"], region=feed["region"], filter_keywords=kw_filter, keyword_badge=f"Feed: {feed['source']}"))

        for topic in GLOBAL_SEARCH_TOPICS:
            encoded = urllib.parse.quote(topic)
            tasks.append(fetch_feed_max_speed(client, semaphore, f"https://www.reddit.com/search.rss?q={encoded}&sort=new", "Reddit", "ALL", region="Global", keyword_badge=f"Topic: {topic}"))
            tasks.append(fetch_feed_max_speed(client, semaphore, f"https://hnrss.org/newest?q={encoded}", "Hacker News", "ALL", region="Global", keyword_badge=f"Topic: {topic}"))
            tasks.append(fetch_feed_max_speed(client, semaphore, f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en", "Google News", "ALL", region="Global", keyword_badge=f"Topic: {topic}"))

        for category, target_list, kw_list in [("RED", RED_TARGETS, RED_KEYWORDS), ("GENERAL", GENERAL_TARGETS, GENERAL_KEYWORDS)]:
            for target in target_list:
                h = target["handle"]
                r = target["region"]
                encoded_h = urllib.parse.quote(h)
                tasks.append(fetch_feed_max_speed(client, semaphore, f"https://news.google.com/rss/search?q={encoded_h}&hl=en-US&gl=US&ceid=US:en", "Google News", category, handle=h, region=r, filter_keywords=kw_list))
                tasks.append(fetch_feed_max_speed(client, semaphore, f"https://news.google.com/rss/search?q={encoded_h}+site:twitter.com+OR+site:x.com&hl=en-US&gl=US&ceid=US:en", "X (Twitter)", category, handle=h, region=r, filter_keywords=kw_list))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_results = []
        for res in results:
            if isinstance(res, list): all_results.extend(res)

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
        await asyncio.sleep(900)
        await async_sweep_controller(silent=True)

@app.on_event("startup")
async def startup_event():
    init_db()
    asyncio.create_task(background_loop())
    asyncio.create_task(async_sweep_controller(silent=True))

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
    time_filter: str = Query("all"),
    start_date: str = Query(None),
    end_date: str = Query(None),
    q: str = Query(None),
    page: int = Query(1), limit: int = Query(30)
):
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

    if start_date or end_date:
        if start_date:
            query += " AND datetime(published_date) >= datetime(?)"
            params.append(f"{start_date} 00:00:00")
        if end_date:
            query += " AND datetime(published_date) <= datetime(?)"
            params.append(f"{end_date} 23:59:59")
    else:
        if time_filter == "1h":
            query += " AND datetime(published_date) >= datetime('now', '-1 hour')"
        elif time_filter == "4h":
            query += " AND datetime(published_date) >= datetime('now', '-4 hours')"
        elif time_filter == "8h":
            query += " AND datetime(published_date) >= datetime('now', '-8 hours')"
        elif time_filter == "12h":
            query += " AND datetime(published_date) >= datetime('now', '-12 hours')"
        elif time_filter == "1d":
            query += " AND datetime(published_date) >= datetime('now', '-1 day')"
        elif time_filter == "3d":
            query += " AND datetime(published_date) >= datetime('now', '-3 days')"
        elif time_filter == "7d":
            query += " AND datetime(published_date) >= datetime('now', '-7 days')"
        elif time_filter == "14d":
            query += " AND datetime(published_date) >= datetime('now', '-14 days')"
        elif time_filter == "30d":
            query += " AND datetime(published_date) >= datetime('now', '-30 days')"
        elif time_filter == "90d":
            query += " AND datetime(published_date) >= datetime('now', '-90 days')"

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
    
    cursor.execute("SELECT COUNT(*) FROM news")
    total_intel = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM news WHERE threat_level = 'CRITICAL'")
    critical_threats = cursor.fetchone()[0]

    conn.close()
    
    stats = {"dates": [], "ALL": [], "RED": [], "GENERAL": [], "total_intel": total_intel, "critical_threats": critical_threats}
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
        cursor.execute("SELECT source, category, region, handle, keyword, threat_level, title, link, published_date FROM news ORDER BY published_date DESC")
    else:
        cursor.execute("SELECT source, category, region, handle, keyword, threat_level, title, link, published_date FROM news WHERE category = ? ORDER BY published_date DESC", (category.upper(),))
    rows = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Source", "Category", "Region", "Handle", "Keyword Trigger", "Threat Level", "Intel Title", "Source URL", "Timestamp"])
    for row in rows: writer.writerow([row["source"], row["category"], row["region"], row["handle"], row.get("keyword", "N/A"), row.get("threat_level", "INFORMATIONAL"), row["title"], row["link"], row["published_date"]])
    output.seek(0)
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=intel_export_{category}_{datetime.now().strftime('%Y%m%d')}.csv"
    return response

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)