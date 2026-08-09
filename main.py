from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
import psycopg2
import psycopg2.extras
import uvicorn
import logging
import csv
import io
import os
import asyncio
import feedparser
import urllib.parse
import httpx
import time
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Global Geopolitical Intelligence Command Center", version="30.0 - Serverless REST")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ENVIRONMENT VARIABLES ---
DATABASE_URL = os.getenv("DATABASE_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID_RED = os.getenv("TELEGRAM_CHAT_ID_RED", "")
TELEGRAM_CHAT_ID_GENERAL = os.getenv("TELEGRAM_CHAT_ID_GENERAL", "")
CRON_SECRET = os.getenv("CRON_SECRET", "my-secure-password-99")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

CRITICAL_WORDS = ["war", "strike", "attack", "missile", "assassination", "conflict", "explosion", "invasion", "military action", "airstrike", "casualty", "nuclear", "killing", "bombing"]
ELEVATED_WORDS = ["sanctions", "protest", "tension", "warning", "ban", "dispute", "standoff", "threat", "cyberattack", "unrest", "crisis", "drill", "deployment"]
RED_KEYWORDS = ["muslim brotherhood", "cair", "migration crisis", "refugee", "border security", "illegal immigration", "sudan", "somalia", "iran", "ukraine", "russia", "demonstration", "protest", "parliament", "counter-terrorism", "terror", "israel", "gaza", "palestine", "hamas", "hezbollah", "lebanon", "syria", "yemen", "houthi", "saudi", "qatar", "uae", "turkey", "egypt", "iraq", "strike", "war", "military", "troops", "defense", "missile", "security", "conflict", "unrest", "attack", "border", "ceasefire", "peace", "hostage", "forces", "army", "netanyahu", "erdogan", "salman", "zayed", "araghchi", "red sea", "drone", "sanctions", "crisis", "airstrike", "casualty", "retaliation", "idf", "mfa"]
GENERAL_KEYWORDS = ["bilateral", "state visit", "diplomatic", "diplomacy", "strategic dialogue", "ambassador", "foreign ministry", "trade agreement", "foreign investment", "economic partnership", "trade deal", "sanctions", "memorandum of understanding", "mou", "security partnership", "defense pact", "military agreement", "joint military exercise", "security cooperation", "defense treaty", "treaty", "summit", "multilateral", "un resolution", "convention", "global governance", "geopolitical", "resource diplomacy", "foreign influence", "strategic alliance", "kenya", "rwanda", "south africa", "nigeria", "ethiopia", "france", "germany", "spain", "poland", "uk", "britain", "eu", "european union", "african union", "macron", "meloni", "ruto", "kagame", "ramaphosa", "sanchez", "tusk", "scholz", "cooperation", "talks", "envoy", "minister", "president", "prime minister", "foreign policy", "aid", "development", "agreement", "pact"]

GEO_MAPPING = {
    "israel": (31.0461, 34.8516), "gaza": (31.4167, 34.3333), "palestine": (31.9522, 35.2332), 
    "lebanon": (33.8547, 35.8623), "syria": (34.8021, 38.9968), "iran": (32.4279, 53.6880), 
    "yemen": (15.5527, 48.5164), "houthi": (15.3483, 44.2065), "red sea": (22.2539, 38.0258), 
    "ukraine": (48.3794, 31.1656), "russia": (61.5240, 105.3188), "sudan": (12.8628, 30.2176), 
    "somalia": (5.1521, 46.1996), "china": (35.8617, 104.1954), "taiwan": (23.6978, 120.9605), 
    "us": (37.0902, -95.7129), "usa": (37.0902, -95.7129), "washington": (38.8951, -77.0364), 
    "uk": (55.3781, -3.4360), "britain": (55.3781, -3.4360), "london": (51.5072, -0.1276), 
    "france": (46.2276, 2.2137), "germany": (51.1657, 10.4515), "kenya": (-1.2921, 36.8219), 
    "rwanda": (-1.9403, 29.8739), "ethiopia": (9.1450, 40.4897), "nigeria": (9.0820, 8.6753), 
    "saudi": (23.8859, 45.0792), "uae": (23.4241, 53.8478), "qatar": (25.3548, 51.1839), 
    "turkey": (38.9637, 35.2433), "egypt": (26.8206, 30.8025), "iraq": (33.2232, 43.6793)
}

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

RED_TARGETS = [{"handle": h, "region": "Middle East"} for h in ["@KingSalman", "@MohamedBinZayed", "@HHShkMohd", "@TamimBinHamad", "@RTErdogan", "@netanyahu", "@FaisalbinFarhan", "@KSAMOFA", "@ABZayed", "@araghchi", "@IRIMFA_EN", "@MFATurkiye"]]
GENERAL_TARGETS = [{"handle": h, "region": "Africa"} for h in ["@WilliamsRuto", "@PaulKagame", "@CyrilRamaphosa", "@officialABAT", "@AlsisiOfficial", "@MFAEthiopia"]] + [{"handle": h, "region": "Europe"} for h in ["@EmmanuelMacron", "@GiorgiaMeloni", "@sanchezcastejon", "@donaldtusk", "@bundeskanzler", "@FCDOGovUK"]]

def get_db_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL is not set in environment variables.")
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)

def classify_threat_by_heat(title):
    t_lower = title.lower()
    heat_score = sum(1 for kw in RED_KEYWORDS + GENERAL_KEYWORDS if kw in t_lower)
    heat_score += sum(1 for ew in ELEVATED_WORDS if ew in t_lower)
    heat_score += sum(2 for cw in CRITICAL_WORDS if cw in t_lower)
    if heat_score >= 3:
        return "CRITICAL"
    elif heat_score >= 1:
        return "ELEVATED"
    return "INFORMATIONAL"

def extract_geo_coordinates(title):
    t_lower = title.lower()
    for location, coords in GEO_MAPPING.items():
        if location in t_lower:
            return coords[0], coords[1]
    return "N/A", "N/A"

async def dispatch_telegram_alert(item):
    if not TELEGRAM_BOT_TOKEN:
        return
    chat_id = TELEGRAM_CHAT_ID_RED if item['category'] == 'RED' else TELEGRAM_CHAT_ID_GENERAL
    if item['category'] == 'ALL':
        chat_id = TELEGRAM_CHAT_ID_GENERAL
    if not chat_id:
        return 

    msg = f"🔴 *CRITICAL THREAT INTERCEPTED*\n\n*Source:* {item['source']}\n*Location:* {item.get('region', 'Global')}\n\n*Headline:* {item['title']}\n\n[ACCESS FULL INTEL]({item['link']})"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, data={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": True})
        except Exception:
            pass

def save_items_bulk(items):
    if not items:
        return 0, []
    conn = get_db_connection()
    c = conn.cursor()
    added = 0
    new_criticals = []
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
            if c.rowcount > 0:
                added += 1
                if item.get('threat_level') == 'CRITICAL':
                    new_criticals.append(item)
        except Exception:
            pass
    conn.commit()
    conn.close()
    return added, new_criticals

async def fetch_feed_max_speed(client, semaphore, url, source_label, category, handle="N/A", region="Global", keyword_badge="N/A", filter_keywords=None, limit=20):
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
                    pub_date = time.strftime("%Y-%m-%d %H:%M:%S", entry.published_parsed) if hasattr(entry, 'published_parsed') and entry.published_parsed else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
                    lat, lng = extract_geo_coordinates(title)
                    items.append({
                        'title': title.replace(" - X", "").replace(" on X", "").strip(), 
                        'link': link, 
                        'source': source_label, 
                        'category': category, 
                        'handle': handle, 
                        'region': region, 
                        'published_date': pub_date, 
                        'keyword': actual_badge, 
                        'threat_level': classify_threat_by_heat(title), 
                        'lat': lat, 
                        'lng': lng
                    })
        except Exception:
            pass
    return items

async def run_fast_sweep():
    logger.info("Executing Serverless Concurrency Sweep...")
    tasks = []
    semaphore = asyncio.Semaphore(15)
    limits = httpx.Limits(max_keepalive_connections=15, max_connections=30)
    
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, limits=limits) as client:
        for feed in DIRECT_FEEDS:
            kw_filter = RED_KEYWORDS if feed["category"] == "RED" else GENERAL_KEYWORDS if feed["category"] == "GENERAL" else None
            tasks.append(fetch_feed_max_speed(client, semaphore, feed["url"], feed["source"], feed["category"], region=feed["region"], filter_keywords=kw_filter, keyword_badge=f"Feed: {feed['source']}"))
        
        for category, target_list, kw_list in [("RED", RED_TARGETS, RED_KEYWORDS), ("GENERAL", GENERAL_TARGETS, GENERAL_KEYWORDS)]:
            for target in target_list:
                h = target["handle"]
                r = target["region"]
                encoded_h = urllib.parse.quote(h)
                tasks.append(fetch_feed_max_speed(client, semaphore, f"https://news.google.com/rss/search?q={encoded_h}&hl=en-US&gl=US&ceid=US:en", "Google News", category, handle=h, region=r, filter_keywords=kw_list))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_results = []
        for res in results:
            if isinstance(res, list):
                all_results.extend(res)

        total_new, new_criticals = await asyncio.to_thread(save_items_bulk, all_results)
        for crit in new_criticals:
            asyncio.create_task(dispatch_telegram_alert(crit))
        return total_new

# --- ROUTES ---

@app.get("/")
def read_root():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    root_path = os.path.join(BASE_DIR, "index.html")
    template_path = os.path.join(BASE_DIR, "templates", "index.html")
    if os.path.exists(root_path):
        return FileResponse(root_path)
    elif os.path.exists(template_path):
        return FileResponse(template_path)
    raise HTTPException(status_code=404, detail="index.html not found on server")

@app.get("/api/ping")
def ping():
    return {"status": "awake"}

@app.get("/api/trigger/sweep")
async def trigger_sweep(secret: str = Query(None)):
    if secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")
    total_added = await run_fast_sweep()
    return {"status": "success", "new_records": total_added}

@app.post("/api/webhook/telegram")
async def telegram_webhook(request: Request):
    data = await request.json()
    message = data.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    
    if not text or not TELEGRAM_BOT_TOKEN:
        return {"status": "ignored"}
    
    send_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        if text.startswith("/sync"):
            await client.post(send_url, data={"chat_id": chat_id, "text": "⚡ *Initiating Serverless Sweep...*", "parse_mode": "Markdown"})
            asyncio.create_task(run_fast_sweep())
        elif text.startswith("/stats"):
            try:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM news")
                total = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM news WHERE threat_level = 'CRITICAL'")
                criticals = c.fetchone()[0]
                conn.close()
                stat_msg = f"📊 *LIVE TELEMETRY STATS*\n\n*Total Indexed Intel:* {total}\n*🔴 Critical Threats:* {criticals}"
                await client.post(send_url, data={"chat_id": chat_id, "text": stat_msg, "parse_mode": "Markdown"})
            except Exception as e:
                await client.post(send_url, data={"chat_id": chat_id, "text": f"⚠️ Database Error: {str(e)}"})
    return {"status": "processed"}

@app.get("/api/news")
async def get_news(
    category: str = Query("ALL"), 
    source: str = Query("All"), 
    region: str = Query("All"), 
    handle: str = Query("All"), 
    q: str = Query(None), 
    page: int = Query(1), 
    limit: int = Query(30)
):
    try:
        offset = (page - 1) * limit
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM news WHERE 1=1"
        params = []
        
        if category.upper() != "ALL":
            query += " AND category = %s"
            params.append(category.upper())
        if source != "All":
            query += " AND source = %s"
            params.append(source)
        if region != "All":
            query += " AND region = %s"
            params.append(region)
        if handle != "All":
            query += " AND handle = %s"
            params.append(handle)
        if q:
            query += " AND (title ILIKE %s OR handle ILIKE %s OR source ILIKE %s)"
            params.extend([f"%{q}%"] * 3)
            
        query += " ORDER BY published_date DESC, id DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        return []

@app.get("/api/stats")
def get_stats():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM news")
        total_intel = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM news WHERE threat_level = 'CRITICAL'")
        critical_threats = cursor.fetchone()[0]
        conn.close()
        return {"total_intel": total_intel, "critical_threats": critical_threats, "channels_monitored": 54}
    except Exception as e:
        return {"total_intel": 0, "critical_threats": 0, "channels_monitored": 54, "error": str(e)}

@app.get("/api/export")
def export_csv(category: str = Query("ALL")):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if category.upper() == "ALL":
            cursor.execute("SELECT source, category, region, handle, keyword, threat_level, title, link, published_date FROM news ORDER BY published_date DESC")
        else:
            cursor.execute("SELECT source, category, region, handle, keyword, threat_level, title, link, published_date FROM news WHERE category = %s ORDER BY published_date DESC", (category.upper(),))
        rows = cursor.fetchall()
        conn.close()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Source", "Category", "Region", "Handle", "Keyword", "Threat Level", "Title", "Link", "Date"])
        for row in rows:
            writer.writerow([row["source"], row["category"], row["region"], row["handle"], row.get("keyword", "N/A"), row.get("threat_level", "INFORMATIONAL"), row["title"], row["link"], row["published_date"]])
        output.seek(0)
        response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename=intel_export_{datetime.now().strftime('%Y%m%d')}.csv"
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)