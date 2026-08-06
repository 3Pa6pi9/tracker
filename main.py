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

app = FastAPI(title="Geopolitical Intelligence API", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "tracker_data.db"

# --- CONFIGURATION ARRAYS ---
RED_HANDLES = [
    "@KingSalman", "@MohamedBinZayed", "@HHShkMohd", "@TamimBinHamad", 
    "@RTErdogan", "@netanyahu", "@FaisalbinFarhan", "@KSAMOFA", 
    "@KSAmofaEN", "@ABZayed", "@mofauae", "@OFMUAE", "@MBA_AlThani_", 
    "@MofaQatar_EN", "@IsraelMFA", "@araghchi", "@IRIMFA_EN", "@MFATurkiye"
]

RED_KEYWORDS = [
    "Muslim Brotherhood", "CAIR", "Migration", "Refugee", "Border", 
    "Illegal Immigration", "Sudan", "Somalia", "Iran", "Ukraine", 
    "Russia", "Demonstration", "Protest", "Parliament", "Terrorism", 
    "Africa", "Western"
]

GREEN_HANDLES = [
    "@WilliamsRuto", "@PaulKagame", "@CyrilRamaphosa", "@officialABAT", "@AlsisiOfficial",
    "@MFAEthiopia", "@MusaliaMudavadi", "@ForeignOfficeKE", "@RonaldLamola", "@DIRCO_ZA", 
    "@NigeriaMFA", "@MFAEgOfficial", "@MfaEgypt", "@EmmanuelMacron", "@GiorgiaMeloni", 
    "@sanchezcastejon", "@donaldtusk", "@_FriedrichMerz", "@bundeskanzler", "@AussenMinDE", 
    "@AuswaertigesAmt", "@GermanyDiplo", "@Ed_Miliband", "@FCDOGovUK", "@UrugwiroVillage", "@NGRPresident"
]

GREEN_KEYWORDS = [
    "bilateral relations", "state visit", "diplomatic ties", "strategic dialogue", 
    "ambassador meeting", "foreign ministry", "trade agreement", "foreign investment", 
    "economic partnership", "trade deal", "sanctions", "memorandum of understanding", 
    "MoU", "security partnership", "defense pact", "military agreement", 
    "joint military exercise", "security cooperation", "defense treaty", 
    "treaty signed", "international summit", "multilateral agreement", 
    "UN resolution", "international convention", "global governance", 
    "geopolitical shift", "resource diplomacy", "foreign influence", 
    "strategic alliance", "international relations"
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
            published_date TEXT
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_cat_date ON news (category, published_date);')
    conn.commit()
    conn.close()

# --- THE SCRAPING ENGINE ---
def fetch_via_google_news(handle, category, keywords):
    clean_handle = handle.replace('@', '')
    query = f'"{handle}" OR "{clean_handle}"'
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    
    try:
        feed = feedparser.parse(rss_url)
        conn = get_db_connection()
        c = conn.cursor()
        added = 0
        
        for entry in feed.entries:
            title = getattr(entry, 'title', '')
            link = getattr(entry, 'link', '')
            pub_date = getattr(entry, 'published', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            text_lower = title.lower()
            if any(kw.lower() in text_lower for kw in keywords):
                try:
                    c.execute(
                        "INSERT INTO news (title, link, source, category, published_date) VALUES (?, ?, ?, ?, ?)",
                        (title, link, handle, category, pub_date)
                    )
                    added += 1
                except sqlite3.IntegrityError:
                    pass
        conn.commit()
        conn.close()
        return added
    except Exception as e:
        logger.error(f"Failed to fetch for {handle}: {e}")
        return 0

def execute_sweep():
    logger.info("Starting Intel Sweep...")
    total = 0
    for handle in RED_HANDLES:
        total += fetch_via_google_news(handle, "RED", RED_KEYWORDS)
    for handle in GREEN_HANDLES:
        total += fetch_via_google_news(handle, "GREEN", GREEN_KEYWORDS)
    return total

async def async_sweep():
    total_added = await asyncio.to_thread(execute_sweep)
    if total_added > 0:
        logger.info(f"Sweep complete. {total_added} records added. Broadcasting to UI.")
        await manager.broadcast(json.dumps({"event": "new_intel"}))
    else:
        logger.info("Sweep complete. No new records matching strict keywords.")

async def background_scheduler():
    while True:
        await asyncio.sleep(1800) # Wait 30 mins
        await async_sweep()

@app.on_event("startup")
async def startup_event():
    init_db()
    # Start the continuous background loop inside FastAPI
    asyncio.create_task(background_scheduler())
    # Run an initial sweep 5 seconds after boot
    asyncio.create_task(async_sweep())

# --- API ROUTES ---
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
async def manual_sync(background_tasks: BackgroundTasks):
    """Endpoint to manually force a data scrape from the UI."""
    background_tasks.add_task(async_sweep)
    return {"status": "Sync initiated. Check UI in 15 seconds."}

@app.get("/api/news")
def get_news(category: str, search: str = None, page: int = 1, limit: int = 30):
    offset = (page - 1) * limit
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM news WHERE category = ?"
    params = [category.upper()]
    
    if search:
        query += " AND (title LIKE ? OR source LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
        
    query += " ORDER BY datetime(published_date) DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/api/stats")
def get_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT date(published_date) as date, category, COUNT(*) as count 
        FROM news 
        WHERE date(published_date) >= ? 
        GROUP BY date(published_date), category
        ORDER BY date(published_date) ASC
    """, (seven_days_ago,))
    rows = cursor.fetchall()
    conn.close()
    
    stats = {"dates": [], "RED": [], "GREEN": []}
    temp_dict = {}
    for row in rows:
        d = row["date"]
        c = row["category"]
        if d not in temp_dict: temp_dict[d] = {"RED": 0, "GREEN": 0}
        temp_dict[d][c] = row["count"]
        
    for d in sorted(temp_dict.keys()):
        stats["dates"].append(d)
        stats["RED"].append(temp_dict[d]["RED"])
        stats["GREEN"].append(temp_dict[d]["GREEN"])
    return stats

@app.get("/api/export")
def export_csv(category: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT source, title, link, published_date FROM news WHERE category = ? ORDER BY published_date DESC", (category.upper(),))
    rows = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Source Handle", "Intel Title", "Source URL", "Timestamp"])
    for row in rows: writer.writerow([row["source"], row["title"], row["link"], row["published_date"]])
    output.seek(0)
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=intel_export_{category}.csv"
    return response

@app.delete("/api/cleanup/uae")
def trigger_uae_cleanup():
    uae_handles = ["@MohamedBinZayed", "@HHShkMohd", "@ABZayed", "@mofauae", "@OFMUAE"]
    conn = get_db_connection()
    cursor = conn.cursor()
    placeholders = ', '.join(['?'] * len(uae_handles))
    cursor.execute(f"DELETE FROM news WHERE source IN ({placeholders})", uae_handles)
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"Purged {deleted_count} UAE records."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)