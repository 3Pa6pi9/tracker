from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import psycopg2
import psycopg2.extras
import uvicorn
import logging
import os
import asyncio
import httpx
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Global Geopolitical Intelligence Command Center", version="3.2 - Final API Bypass")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ENVIRONMENT VARIABLES ---
DATABASE_URL = os.getenv("DATABASE_URL", "")
CRON_SECRET = os.getenv("CRON_SECRET", "my-secure-password-99")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

CRITICAL_WORDS = ["war", "strike", "attack", "missile", "assassination", "conflict", "explosion", "invasion", "military action", "airstrike", "casualty", "nuclear", "killing", "bombing"]
ELEVATED_WORDS = ["sanctions", "protest", "tension", "warning", "ban", "dispute", "standoff", "threat", "cyberattack", "unrest", "crisis", "drill", "deployment"]
RED_KEYWORDS = ["israel", "gaza", "palestine", "hamas", "hezbollah", "lebanon", "syria", "yemen", "houthi", "iran", "ukraine", "russia", "strike", "war", "missile", "military"]
GENERAL_KEYWORDS = ["diplomacy", "sanctions", "treaty", "summit", "nato", "un resolution", "kenya", "rwanda", "south africa", "eu", "macron", "biden"]

GEO_MAPPING = {
    "israel": (31.0461, 34.8516), "gaza": (31.4167, 34.3333), "palestine": (31.9522, 35.2332), 
    "lebanon": (33.8547, 35.8623), "syria": (34.8021, 38.9968), "iran": (32.4279, 53.6880), 
    "yemen": (15.5527, 48.5164), "ukraine": (48.3794, 31.1656), "russia": (61.5240, 105.3188), 
    "usa": (37.0902, -95.7129), "uk": (55.3781, -3.4360), "kenya": (-1.2921, 36.8219)
}

DIRECT_FEEDS = [
    {"url": "https://www.aljazeera.com/xml/rss/all.xml", "source": "Al Jazeera", "category": "RED", "region": "Middle East"},
    {"url": "https://www.middleeasteye.net/rss", "source": "Middle East Eye", "category": "RED", "region": "Middle East"},
    {"url": "http://feeds.bbci.co.uk/news/world/rss.xml", "source": "BBC World", "category": "ALL", "region": "Global"}
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

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

def get_db_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL is missing. Please add it to Render Environment Variables.")
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)

def classify_threat(title):
    t_lower = title.lower()
    heat = sum(1 for kw in RED_KEYWORDS + GENERAL_KEYWORDS if kw in t_lower)
    heat += sum(2 for cw in CRITICAL_WORDS if cw in t_lower)
    if heat >= 3: return "CRITICAL"
    if heat >= 1: return "ELEVATED"
    return "INFORMATIONAL"

def extract_geo(title):
    t_lower = title.lower()
    for loc, coords in GEO_MAPPING.items():
        if loc in t_lower: return coords[0], coords[1]
    return "N/A", "N/A"

def save_items_bulk(items):
    if not items: return 0
    conn = get_db_connection()
    c = conn.cursor()
    added = 0
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for item in items:
        try:
            c.execute('''
                INSERT INTO news (title, link, source, category, handle, region, published_date, fetched_at, keyword, threat_level, lat, lng)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (link) DO NOTHING
            ''', (
                item['title'], item['link'], item['source'], item['category'],
                item.get('handle', 'N/A'), item.get('region', 'Global'),
                item['published_date'], now_iso, item.get('keyword', 'N/A'),
                item.get('threat_level', 'INFORMATIONAL'), str(item.get('lat', 'N/A')), str(item.get('lng', 'N/A'))
            ))
            if c.rowcount > 0: added += 1
        except Exception as e:
            logger.error(f"DB Insert Error: {e}")
    conn.commit()
    conn.close()
    return added

async def fetch_feed_max_speed(client, url, source, category):
    items = []
    try:
        # BYPASS CLOUDFLARE: Let httpx handle the URL encoding natively
        response = await client.get(
            "https://api.rss2json.com/v1/api.json", 
            params={"rss_url": url}, 
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok":
                for entry in data.get("items", [])[:15]:
                    title = entry.get('title', '')
                    link = entry.get('link', '')
                    pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if title and link:
                        lat, lng = extract_geo(title)
                        items.append({
                            'title': title, 'link': link, 'source': source, 
                            'category': category, 'published_date': pub_date,
                            'threat_level': classify_threat(title), 'lat': lat, 'lng': lng
                        })
    except Exception as e:
        logger.error(f"Feed error {source}: {e}")
    return items

async def broadcast_latest_data():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM news ORDER BY published_date DESC LIMIT 50")
        latest = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) FROM news")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM news WHERE threat_level = 'CRITICAL'")
        criticals = cur.fetchone()[0]
        conn.close()

        await manager.broadcast({
            "type": "update",
            "items": latest,
            "stats": {"total": total, "critical": criticals}
        })
    except Exception as e:
        await manager.broadcast({"type": "log", "msg": f"DATABASE ERROR: {str(e)}", "alert": True})

async def execute_sweep(is_manual=False):
    msg = "MANUAL OVERRIDE: INITIATING IMMEDIATE SWEEP..." if is_manual else "EXECUTING MAX-YIELD ASYNC SWEEP ACROSS GLOBAL FEEDS..."
    await manager.broadcast({"type": "log", "msg": msg, "alert": is_manual})
    
    try:
        tasks = []
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
            for feed in DIRECT_FEEDS:
                tasks.append(fetch_feed_max_speed(client, feed["url"], feed["source"], feed["category"]))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            all_results = [item for sublist in results if isinstance(sublist, list) for item in sublist]

        added = await asyncio.to_thread(save_items_bulk, all_results)
        await manager.broadcast({"type": "log", "msg": f"SWEEP COMPLETE. INTERCEPTED {added} NEW INTELLIGENCE PACKETS.", "alert": False})
        
        await broadcast_latest_data()
        return added
    except Exception as e:
        await manager.broadcast({"type": "log", "msg": f"SWEEP FAILED: {str(e)}", "alert": True})
        return 0

async def continuous_scraper_loop():
    while True:
        await execute_sweep(is_manual=False)
        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(continuous_scraper_loop())

@app.get("/")
def read_root():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    root_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(root_path):
        return FileResponse(root_path)
    raise HTTPException(status_code=404, detail="index.html not found in the root folder.")

@app.get("/api/trigger/sweep")
async def trigger_sweep_endpoint(secret: str = Query(None)):
    if secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")
    added = await execute_sweep(is_manual=True)
    return {"status": "success", "added": added}

# --- DEDICATED REST ENDPOINT FOR FRONTEND FILTERS ---
@app.get("/api/news")
def get_news(source: str = Query(None), date: str = Query(None)):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        query = "SELECT * FROM news WHERE 1=1"
        params = []
        
        if source:
            query += " AND source = %s"
            params.append(source)
        if date:
            query += " AND DATE(published_date) = %s"
            params.append(date)
            
        query += " ORDER BY published_date DESC LIMIT 100"
        cur.execute(query, params)
        data = [dict(r) for r in cur.fetchall()]
        conn.close()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/news")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    await broadcast_latest_data()
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
