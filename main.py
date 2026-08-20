from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
import psycopg2
import psycopg2.extras
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
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Global Geopolitical Intelligence Command Center", version="25.0 - Smart Thumbnails & Language Filters")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SUPABASE CONNECTION 
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres.afdzhavjcejvmnrwyaid:5wNGFgK3H5q3CwUZ@aws-0-eu-west-2.pooler.supabase.com:6543/postgres"
)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

# ==============================================================================
# EXPANDED MULTILINGUAL LEXICONS
# ==============================================================================
MULTILINGUAL_LEXICON = {
    "English": {
        "critical": ["war", "strike", "attack", "missile", "assassination", "conflict", "explosion", "invasion", "airstrike", "casualty", "nuclear", "bombing", "artillery", "hostage", "idf", "offensive", "drone strike", "troops", "frontline", "combat"],
        "elevated": ["sanctions", "protest", "tension", "warning", "ban", "dispute", "standoff", "threat", "cyberattack", "unrest", "crisis", "drill", "deployment", "counter-terrorism", "border security", "migration crisis", "ceasefire", "embargo", "coup"],
        "general": ["bilateral", "state visit", "diplomatic", "diplomacy", "ambassador", "trade agreement", "foreign investment", "summit", "nato", "un resolution", "african union", "european union", "treaty", "foreign policy", "pact"]
    },
    "Arabic": {
        "critical": ["حرب", "غارة", "هجوم", "صاروخ", "اغتيال", "نزاع", "انفجار", "غزو", "ضربة جوية", "قصف", "قتلى", "نووي", "شهداء", "مواجهات مسلحة", "مسيرة", "جيش", "اشتباكات", "استهداف", "طيران"],
        "elevated": ["عقوبات", "احتجاج", "توتر", "تحذير", "حظر", "خلاف", "تهديد", "هجوم سيبراني", "اضطرابات", "أزمة", "انتشار عسكري", "مظاهرات", "وقف إطلاق النار", "حشود"],
        "general": ["دبلوماسية", "قمة", "زيارة رسمية", "اتفاقية تجارية", "استثمار أجنبي", "معاهدة", "مجلس الأمن", "جامعة الدول العربية", "الاتحاد الأفريقي", "مباحثات"]
    },
    "Amharic": {
        "critical": ["ጦርነት", "ጥቃት", "ሚሳይል", "ግድያ", "ግጭት", "ፍንዳታ", "ወረራ", "የአየር ድብደባ", "የሰው ጉዳት", "የኑክሌር", "ቦምብ", "የድሮን ጥቃት", "የታጠቀ ቡድን", "ተኩስ", "ግድያዎች", "የጦር ሰራዊት"],
        "elevated": ["ማዕቀብ", "ተቃውሞ", "ውጥረት", "ማስጠንቀቂያ", "እገዳ", "አለመግባባት", "ስጋት", "የሳይበር ጥቃት", "ቀውስ", "ወታደራዊ ዝግጅት", "ድንበር ጥበቃ", "የተኩስ አቁም", "አደጋ"],
        "general": ["ዲፕሎማሲ", "የሁለትዮሽ", "የውጭ ጉዳይ", "የንግድ ስምምነት", "የአፍሪካ ህብረት", "ስምምነት", "የሰላም ንግግር", "ጉባኤ", "ውይይት", "ሽርክና"]
    },
    "French": {
        "critical": ["guerre", "frappe", "attaque", "missile", "assassinat", "conflit", "explosion", "invasion", "frappe aérienne", "victimes", "nucléaire", "bombardement", "offensive", "otage"],
        "elevated": ["sanctions", "manifestation", "tension", "avertissement", "interdiction", "différend", "menace", "cyberattaque", "émeutes", "crise", "déploiement", "coup d'état", "cessez-le-feu"],
        "general": ["diplomatie", "visite d'état", "ambassadeur", "accord commercial", "sommet", "union africaine", "union européenne", "traité", "politique étrangère"]
    }
}

# ==============================================================================
# HIERARCHICAL REPOSITORIES & SUBREDDITS
# ==============================================================================
MASTER_CATALOG = [
    # --- CONFLICT DESKS & REDDIT TRACKERS ---
    {"name": "r/UkrainianConflict", "continent": "Europe", "country": "Ukraine", "category": "RED", "feed_type": "SOCIAL", "url": "https://www.reddit.com/r/UkrainianConflict/new.rss"},
    {"name": "r/Geopolitics", "continent": "Global", "country": "Global", "category": "ALL", "feed_type": "SOCIAL", "url": "https://www.reddit.com/r/geopolitics/new.rss"},
    {"name": "r/WorldNews", "continent": "Global", "country": "Global", "category": "ALL", "feed_type": "SOCIAL", "url": "https://www.reddit.com/r/worldnews/new.rss"},

    # --- ARABIC NATIVE OUTLETS ---
    {"name": "BBC Arabic", "continent": "Middle East", "country": "Regional", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://feeds.bbci.co.uk/arabic/rss.xml"},
    {"name": "Al Jazeera Arabic", "continent": "Middle East", "country": "Qatar", "category": "RED", "feed_type": "PUBLISHER", "url": "https://news.google.com/rss/search?q=site:aljazeera.net&hl=ar&gl=QA&ceid=QA:ar"},
    {"name": "Sky News Arabia", "continent": "Middle East", "country": "UAE", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://www.skynewsarabia.com/rss"},
    {"name": "Arab News", "continent": "Middle East", "country": "Saudi Arabia", "category": "RED", "feed_type": "PUBLISHER", "url": "https://www.arabnews.com/cat/1/rss.xml"},
    {"name": "Saba Net Yemen", "continent": "Middle East", "country": "Yemen", "category": "RED", "feed_type": "PUBLISHER", "url": "https://news.google.com/rss/search?q=site:sabanew.net&hl=ar&gl=YE&ceid=YE:ar"},
    {"name": "SUNA Sudan", "continent": "Africa", "country": "Sudan", "category": "RED", "feed_type": "PUBLISHER", "url": "https://news.google.com/rss/search?q=site:suna-sd.net&hl=ar&gl=SD&ceid=SD:ar"},

    # --- AMHARIC / HORN OF AFRICA NATIVE OUTLETS ---
    {"name": "BBC News Amharic", "continent": "Africa", "country": "Ethiopia", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://feeds.bbci.co.uk/amharic/rss.xml"},
    {"name": "VOA Amharic", "continent": "Africa", "country": "Ethiopia", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://amharic.voanews.com/api/z$_mye_i_m"},
    {"name": "Deutsche Welle Amharic", "continent": "Africa", "country": "Ethiopia", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://rss.dw.com/rdf/rss-amh-news"},
    {"name": "Fana Broadcasting", "continent": "Africa", "country": "Ethiopia", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://news.google.com/rss/search?q=site:fanabc.com/archives&hl=am&gl=ET&ceid=ET:am"},
    {"name": "The Reporter Ethiopia", "continent": "Africa", "country": "Ethiopia", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://news.google.com/rss/search?q=site:thereporterethiopia.com&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Addis Fortune", "continent": "Africa", "country": "Ethiopia", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://news.google.com/rss/search?q=site:addisfortune.news&hl=en-US&gl=US&ceid=US:en"},

    # --- GLOBAL & US MAJORS ---
    {"name": "The New York Times", "continent": "North America", "country": "United States", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"},
    {"name": "The Washington Post", "continent": "North America", "country": "United States", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://feeds.washingtonpost.com/rss/world"},
    {"name": "The Wall Street Journal", "continent": "North America", "country": "United States", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml"},
    {"name": "Reuters", "continent": "Global", "country": "Global", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://news.google.com/rss/search?q=site:reuters.com+when:24h&hl=en-US&gl=US&ceid=US:en"},
    {"name": "CNN", "continent": "North America", "country": "United States", "category": "ALL", "feed_type": "PUBLISHER", "url": "http://rss.cnn.com/rss/edition_world.rss"},
    {"name": "Fox News", "continent": "North America", "country": "United States", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://moxie.foxnews.com/google-publisher/world.xml"},
    {"name": "BBC World", "continent": "Europe", "country": "United Kingdom", "category": "ALL", "feed_type": "PUBLISHER", "url": "http://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "The Guardian", "continent": "Europe", "country": "United Kingdom", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://www.theguardian.com/world/rss"},
    {"name": "France 24", "continent": "Europe", "country": "France", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://www.france24.com/fr/rss"},
    {"name": "Deutsche Welle", "continent": "Europe", "country": "Germany", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://rss.dw.com/rdf/rss-en-world"},
    {"name": "Africanews", "continent": "Africa", "country": "Pan-Africa", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://www.africanews.com/feed/"},
    {"name": "Sudan Tribune", "continent": "Africa", "country": "Sudan", "category": "RED", "feed_type": "PUBLISHER", "url": "https://sudantribune.com/feed/"},
    {"name": "Hiiraan Online", "continent": "Africa", "country": "Somalia", "category": "RED", "feed_type": "PUBLISHER", "url": "https://news.google.com/rss/search?q=site:hiiraan.com&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Al Jazeera (English)", "continent": "Middle East", "country": "Qatar", "category": "RED", "feed_type": "PUBLISHER", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"name": "Times of Israel", "continent": "Middle East", "country": "Israel", "category": "RED", "feed_type": "PUBLISHER", "url": "https://www.timesofisrael.com/feed/"}
]

SOCIAL_CATALOG = [
    {"handle": "@netanyahu", "continent": "Middle East", "country": "Israel", "category": "RED"},
    {"handle": "@KingSalman", "continent": "Middle East", "country": "Saudi Arabia", "category": "RED"},
    {"handle": "@MohamedBinZayed", "continent": "Middle East", "country": "UAE", "category": "RED"},
    {"handle": "@MFAEthiopia", "continent": "Africa", "country": "Ethiopia", "category": "GENERAL"},
    {"handle": "@WilliamsRuto", "continent": "Africa", "country": "Kenya", "category": "GENERAL"},
    {"handle": "@StateDept", "continent": "North America", "country": "United States", "category": "ALL"},
    {"handle": "@POTUS", "continent": "North America", "country": "United States", "category": "ALL"},
    {"handle": "@BBCBreaking", "continent": "Europe", "country": "United Kingdom", "category": "ALL"},
    {"handle": "@ReutersWorld", "continent": "Global", "country": "Global", "category": "ALL"},
    {"handle": "@AJBreaking", "continent": "Middle East", "country": "Qatar", "category": "RED"}
]

OPTIONAL_FEEDS = {
    "middle_east_eye": {
        "name": "Middle East Eye",
        "continent": "Middle East",
        "country": "Regional",
        "category": "RED",
        "feed_type": "PUBLISHER",
        "url": "https://www.middleeasteye.net/rss"
    }
}

# ==============================================================================
# DATABASE LAYER (WITH THUMBNAIL SUPPORT)
# ==============================================================================
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)
    conn.autocommit = True
    return conn

def init_db():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS news (
                id SERIAL PRIMARY KEY,
                title TEXT,
                link TEXT UNIQUE,
                source TEXT,
                category TEXT,
                handle TEXT DEFAULT 'N/A',
                continent TEXT DEFAULT 'Global',
                country TEXT DEFAULT 'Global',
                region TEXT DEFAULT 'Global',
                language TEXT DEFAULT 'English',
                thumbnail TEXT DEFAULT '',
                feed_type TEXT DEFAULT 'PUBLISHER',
                published_date TIMESTAMP,
                fetched_at TIMESTAMP,
                keyword TEXT DEFAULT '',
                threat_level TEXT DEFAULT 'INFORMATIONAL'
            )
        ''')
        
        c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='news'")
        existing_cols = [row[0] for row in c.fetchall()]
        if "thumbnail" not in existing_cols:
            c.execute("ALTER TABLE news ADD COLUMN thumbnail TEXT DEFAULT ''")
            
        c.execute('CREATE INDEX IF NOT EXISTS idx_cat_src_cont_lang ON news (category, source, feed_type, language, published_date);')
        conn.close()
    except Exception as e:
        logger.error(f"Database init error: {e}")

# ==============================================================================
# UNICODE SCRIPT DETECTOR & MEDIA EXTRACTOR
# ==============================================================================
def detect_script_language(text: str) -> str:
    if re.search(r'[\u0600-\u06FF]', text): return "Arabic"
    if re.search(r'[\u1200-\u137F]', text): return "Amharic"
    return "English"

def extract_thumbnail(entry_obj):
    """Deep search for media enclosures, OpenGraph tags, and embedded image strings"""
    if isinstance(entry_obj, dict):
        if entry_obj.get("thumbnail") and isinstance(entry_obj["thumbnail"], str):
            return entry_obj["thumbnail"]
        if entry_obj.get("enclosure") and isinstance(entry_obj["enclosure"], dict):
            if entry_obj["enclosure"].get("link"): return entry_obj["enclosure"]["link"]
        desc = entry_obj.get("description", "") or entry_obj.get("content", "")
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', str(desc), re.IGNORECASE)
        if img_match: return img_match.group(1)
    else:
        if hasattr(entry_obj, 'media_content') and entry_obj.media_content:
            for m in entry_obj.media_content:
                if isinstance(m, dict) and 'url' in m: return m['url']
        if hasattr(entry_obj, 'media_thumbnail') and entry_obj.media_thumbnail:
            for m in entry_obj.media_thumbnail:
                if isinstance(m, dict) and 'url' in m: return m['url']
        if hasattr(entry_obj, 'enclosures') and entry_obj.enclosures:
            for enc in entry_obj.enclosures:
                if hasattr(enc, 'href'): return enc.href
                if isinstance(enc, dict) and 'href' in enc: return enc['href']
        summary = getattr(entry_obj, 'summary', '') or getattr(entry_obj, 'description', '')
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', str(summary), re.IGNORECASE)
        if img_match: return img_match.group(1)
    return ""

def analyze_multilingual_threat(title: str):
    t_lower = title.lower()
    matched_keyword = ""
    heat_score = 0
    detected_lang = detect_script_language(title)

    for lang, dicts in MULTILINGUAL_LEXICON.items():
        for kw in dicts["critical"]:
            if re.search(r'\b' + re.escape(kw.lower()) + r'\b', t_lower):
                heat_score += 3
                if not matched_keyword:
                    matched_keyword = kw
                    detected_lang = lang

        for kw in dicts["elevated"]:
            if re.search(r'\b' + re.escape(kw.lower()) + r'\b', t_lower):
                heat_score += 1.5
                if not matched_keyword:
                    matched_keyword = kw
                    detected_lang = lang

        for kw in dicts["general"]:
            if re.search(r'\b' + re.escape(kw.lower()) + r'\b', t_lower):
                heat_score += 1
                if not matched_keyword:
                    matched_keyword = kw
                    detected_lang = lang

    if heat_score >= 3.0: level = "CRITICAL"
    elif heat_score >= 1.0: level = "ELEVATED"
    else: level = "INFORMATIONAL"

    return level, (f"Matched: '{matched_keyword}'" if matched_keyword else ""), detected_lang

def save_items_bulk(items):
    if not items: return 0
    conn = get_db_connection()
    c = conn.cursor()
    added = 0
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for item in items:
        try:
            c.execute('''
                INSERT INTO news (title, link, source, category, handle, continent, country, region, language, thumbnail, feed_type, published_date, fetched_at, keyword, threat_level)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(link) DO NOTHING
            ''', (
                item['title'], item['link'], item['source'], item['category'],
                item.get('handle', 'N/A'), item.get('continent', 'Global'),
                item.get('country', 'Global'), item.get('country', 'Global'),
                item.get('language', 'English'), item.get('thumbnail', ''),
                item.get('feed_type', 'PUBLISHER'),
                item['published_date'], now_iso, item.get('keyword', ''),
                item.get('threat_level', 'INFORMATIONAL')
            ))
            if c.rowcount > 0: added += 1
        except Exception:
            pass
    conn.close()
    return added

# ==============================================================================
# HIGH SPEED HARVESTERS
# ==============================================================================
async def fetch_publisher_feed(client, semaphore, publisher, limit=40):
    items = []
    async with semaphore:
        url = publisher["url"]
        name = publisher["name"]
        continent = publisher["continent"]
        country = publisher["country"]
        category = publisher["category"]
        feed_type = publisher.get("feed_type", "PUBLISHER")

        try:
            response = await client.get(url, timeout=9.0, follow_redirects=True)
            if response.status_code == 200:
                feed = await asyncio.to_thread(feedparser.parse, response.content)
                for entry in feed.entries[:limit]:
                    title = getattr(entry, 'title', '').strip()
                    link = getattr(entry, 'link', '').strip()
                    thumb = extract_thumbnail(entry)
                    
                    try:
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            pub_date = time.strftime("%Y-%m-%d %H:%M:%S", entry.published_parsed)
                        else:
                            pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    if title and link:
                        threat, kw_badge, lang = analyze_multilingual_threat(title)
                        items.append({
                            'title': title, 'link': link, 'source': name, 'handle': 'N/A',
                            'continent': continent, 'country': country, 'category': category,
                            'feed_type': feed_type,
                            'published_date': pub_date, 'keyword': kw_badge,
                            'threat_level': threat, 'language': lang, 'thumbnail': thumb
                        })
            else:
                api_url = "https://api.rss2json.com/v1/api.json"
                r = await client.get(api_url, params={"rss_url": url}, timeout=10.0)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("status") == "ok":
                        for entry in data.get("items", [])[:limit]:
                            title = entry.get("title", "").strip()
                            link = entry.get("link", "").strip()
                            pub_date = entry.get("pubDate", "") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            thumb = extract_thumbnail(entry)
                            if title and link:
                                threat, kw_badge, lang = analyze_multilingual_threat(title)
                                items.append({
                                    'title': title, 'link': link, 'source': name, 'handle': 'N/A',
                                    'continent': continent, 'country': country, 'category': category,
                                    'feed_type': feed_type,
                                    'published_date': pub_date, 'keyword': kw_badge,
                                    'threat_level': threat, 'language': lang, 'thumbnail': thumb
                                })
        except Exception:
            pass
    return items

async def fetch_social_target(client, semaphore, target, limit=20):
    items = []
    async with semaphore:
        handle = target["handle"]
        continent = target["continent"]
        country = target["country"]
        category = target["category"]
        
        encoded_h = urllib.parse.quote(handle)
        url = f"https://news.google.com/rss/search?q={encoded_h}+site:twitter.com+OR+site:x.com&hl=en-US&gl=US&ceid=US:en"

        try:
            response = await client.get(url, timeout=8.0, follow_redirects=True)
            if response.status_code == 200:
                feed = await asyncio.to_thread(feedparser.parse, response.content)
                for entry in feed.entries[:limit]:
                    raw_title = getattr(entry, 'title', '').strip()
                    clean_title = raw_title.replace(" - X", "").replace(" on X", "").replace(" / X", "").strip()
                    link = getattr(entry, 'link', '').strip()
                    thumb = extract_thumbnail(entry)
                    
                    try:
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            pub_date = time.strftime("%Y-%m-%d %H:%M:%S", entry.published_parsed)
                        else:
                            pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    if clean_title and link:
                        threat, kw_badge, lang = analyze_multilingual_threat(clean_title)
                        items.append({
                            'title': clean_title, 'link': link, 'source': 'X (Twitter)',
                            'handle': handle, 'continent': continent, 'country': country,
                            'category': category, 'feed_type': 'SOCIAL',
                            'published_date': pub_date, 'keyword': kw_badge or f"Account: {handle}",
                            'threat_level': threat, 'language': lang, 'thumbnail': thumb
                        })
        except Exception:
            pass
    return items

# ==============================================================================
# WEBSOCKET & SWEEP CONTROLLER
# ==============================================================================
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
is_syncing = False

async def run_fast_sweep(include_mee: bool = False):
    semaphore = asyncio.Semaphore(50)
    limits = httpx.Limits(max_keepalive_connections=60, max_connections=120)
    
    feed_roster = list(MASTER_CATALOG)
    if include_mee:
        feed_roster.append(OPTIONAL_FEEDS["middle_east_eye"])

    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, limits=limits) as client:
        tasks = [fetch_publisher_feed(client, semaphore, pub) for pub in feed_roster]
        tasks += [fetch_social_target(client, semaphore, sock) for sock in SOCIAL_CATALOG]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_results = [item for sublist in results if isinstance(sublist, list) for item in sublist]
        return await asyncio.to_thread(save_items_bulk, all_results)

async def async_sweep_controller(silent=False, include_mee=False):
    global is_syncing
    if is_syncing: return
    is_syncing = True

    event_start = "sync_started_silent" if silent else "sync_started"
    await manager.broadcast(json.dumps({"event": event_start}))

    try:
        total_added = await run_fast_sweep(include_mee=include_mee)
        timestamp = datetime.now().strftime("%I:%M %p")
        if total_added > 0:
            await manager.broadcast(json.dumps({"event": "new_intel", "count": total_added, "silent": silent, "time": timestamp}))
        else:
            await manager.broadcast(json.dumps({"event": "sync_finished_no_data", "silent": silent, "time": timestamp}))
    except Exception as e:
        logger.error(f"Sweep failure: {e}")
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

# ==============================================================================
# REST API ENDPOINTS
# ==============================================================================
@app.get("/", response_class=FileResponse)
def read_root():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    root_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(root_path): return FileResponse(root_path)
    raise HTTPException(status_code=404, detail="index.html not found")

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
async def trigger_manual_sync(background_tasks: BackgroundTasks, include_mee: bool = Query(False)):
    global is_syncing
    if is_syncing: return {"status": "Sync in progress"}
    background_tasks.add_task(async_sweep_controller, False, include_mee)
    return {"status": "Sweep triggered"}

@app.get("/api/news")
async def get_news(
    category: str = Query("ALL"),
    publisher: str = Query("All"),
    handle: str = Query("All"),
    language: str = Query("All"),
    time_filter: str = Query("all"),
    start_date: str = Query(None),
    end_date: str = Query(None),
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
        query += " AND category = %s"
        params.append(category.upper())
    if publisher != "All":
        query += " AND source = %s"
        params.append(publisher)
    if handle != "All":
        query += " AND handle = %s"
        params.append(handle)
    if language != "All":
        query += " AND language = %s"
        params.append(language)

    if start_date or end_date:
        if start_date:
            query += " AND published_date >= %s::timestamp"
            params.append(f"{start_date} 00:00:00")
        if end_date:
            query += " AND published_date <= %s::timestamp"
            params.append(f"{end_date} 23:59:59")
    else:
        time_mappings = {
            "1h": "1 hour", "4h": "4 hours", "8h": "8 hours", "12h": "12 hours",
            "1d": "1 day", "3d": "3 days", "7d": "7 days", "14d": "14 days", 
            "30d": "30 days", "90d": "90 days"
        }
        if time_filter in time_mappings:
            query += f" AND published_date >= NOW() - INTERVAL '{time_mappings[time_filter]}'"

    if q:
        query += " AND (title ILIKE %s OR source ILIKE %s OR handle ILIKE %s OR keyword ILIKE %s)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])
        
    query += " ORDER BY published_date DESC, id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        r = dict(row)
        if isinstance(r.get('published_date'), datetime):
            r['published_date'] = r['published_date'].strftime("%Y-%m-%d %H:%M:%S")
            
        if not r.get('language') or r.get('language') == 'English':
            r['language'] = detect_script_language(r.get('title', ''))
            
        results.append(r)
    
    return results

@app.get("/api/meta/catalog")
def get_catalog_metadata():
    handles_set = set()
    for item in SOCIAL_CATALOG:
        handles_set.add(item["handle"])

    return {
        "handles": sorted(list(handles_set)),
        "languages": list(MULTILINGUAL_LEXICON.keys())
    }

@app.get("/api/stats")
def get_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DATE(published_date) as date, category, COUNT(*) as count 
        FROM news 
        WHERE published_date IS NOT NULL 
        GROUP BY DATE(published_date), category
        ORDER BY DATE(published_date) ASC
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
        d = str(row["date"])
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
def export_csv(
    category: str = Query("ALL"),
    publisher: str = Query("All"),
    handle: str = Query("All"),
    language: str = Query("All")
):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT feed_type, source, handle, category, continent, country, language, keyword, threat_level, title, link, published_date FROM news WHERE 1=1"
    params = []
    if category.upper() != "ALL":
        query += " AND category = %s"
        params.append(category.upper())
    if publisher != "All":
        query += " AND source = %s"
        params.append(publisher)
    if handle != "All":
        query += " AND handle = %s"
        params.append(handle)
    if language != "All":
        query += " AND language = %s"
        params.append(language)
        
    query += " ORDER BY published_date DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Stream Type", "Source", "Handle", "Category", "Continent", "Country", "Language", "Keyword Trigger", "Threat Level", "Title", "URL", "Timestamp"])
    for row in rows: 
        writer.writerow([row["feed_type"], row["source"], row["handle"], row["category"], row["continent"], row["country"], row["language"], row.get("keyword", ""), row.get("threat_level", "INFORMATIONAL"), row["title"], row["link"], row["published_date"]])
    
    output.seek(0)
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=intel_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return response

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
