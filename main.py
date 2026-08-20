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

app = FastAPI(title="Global Geopolitical Intelligence Command Center", version="21.0 - Max Yield & Thumbnail Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SUPABASE CONNECTION (Pooler Port 6543)
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres.afdzhavjcejvmnrwyaid:5wNGFgK3H5q3CwUZ@aws-0-eu-west-2.pooler.supabase.com:6543/postgres"
)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

# ==============================================================================
# MULTILINGUAL THREAT & GEOPOLITICAL LEXICONS
# ==============================================================================
MULTILINGUAL_LEXICON = {
    "English": {
        "critical": ["war", "strike", "attack", "missile", "assassination", "conflict", "explosion", "invasion", "airstrike", "casualty", "nuclear", "bombing", "artillery", "hostage", "idf", "offensive", "drone strike", "troops"],
        "elevated": ["sanctions", "protest", "tension", "warning", "ban", "dispute", "standoff", "threat", "cyberattack", "unrest", "crisis", "drill", "deployment", "counter-terrorism", "border security", "migration crisis", "ceasefire", "embargo", "coup"],
        "general": ["bilateral", "state visit", "diplomatic", "diplomacy", "ambassador", "trade agreement", "foreign investment", "summit", "nato", "un resolution", "african union", "european union", "treaty", "foreign policy", "pact"]
    },
    "Arabic": {
        "critical": ["حرب", "غارة", "هجوم", "صاروخ", "اغتيال", "نزاع", "انفجار", "غزو", "ضربة جوية", "قصف", "قتلى", "نووي", "شهداء", "مواجهات مسلحة", "مسيرة"],
        "elevated": ["عقوبات", "احتجاج", "توتر", "تحذير", "حظر", "خلاف", "تهديد", "هجوم سيبراني", "اضطرابات", "أزمة", "انتشار عسكري", "مظاهرات", "وقف إطلاق النار"],
        "general": ["دبلوماسية", "قمة", "زيارة رسمية", "اتفاقية تجارية", "استثمار أجنبي", "معاهدة", "مجلس الأمن", "جامعة الدول العربية", "الاتحاد الأفريقي"]
    },
    "Amharic": {
        "critical": ["ጦርነት", "ጥቃት", "ሚሳይል", "ግድያ", "ግጭት", "ፍንዳታ", "ወረራ", "የአየር ድብደባ", "የሰው ጉዳት", "የኑክሌር", "ቦምብ", "የድሮን ጥቃት", "የታጠቀ ቡድን"],
        "elevated": ["ማዕቀብ", "ተቃውሞ", "ውጥረት", "ማስጠንቀቂያ", "እገዳ", "አለመግባባት", "ስጋት", "የሳይበር ጥቃት", "ቀውስ", "ወታደራዊ ዝግጅት", "ድንበር ጥበቃ", "የተኩስ አቁም"],
        "general": ["ዲፕሎማሲ", "የሁለትዮሽ", "የውጭ ጉዳይ", "የንግድ ስምምነት", "የአፍሪካ ህብረት", "ስምምነት", "የሰላም ንግግር", "ጉባኤ"]
    },
    "French": {
        "critical": ["guerre", "frappe", "attaque", "missile", "assassinat", "conflit", "explosion", "invasion", "frappe aérienne", "victimes", "nucléaire", "bombardement", "offensive", "otage"],
        "elevated": ["sanctions", "manifestation", "tension", "avertissement", "interdiction", "différend", "menace", "cyberattaque", "émeutes", "crise", "déploiement", "coup d'état", "cessez-le-feu"],
        "general": ["diplomatie", "visite d'état", "ambassadeur", "accord commercial", "sommet", "union africaine", "union européenne", "traité", "politique étrangère"]
    },
    "Somali": {
        "critical": ["dagaal", "weerar", "gantaal", "dil", "colaad", "qarax", "duullaan", "duqeyn", "khasaare", "nukliyeer", "al-shabaab", "qaraxyo"],
        "elevated": ["cunaqabateyn", "dibadbax", "xiisad", "digniin", "xayiraad", "khilaaf", "hanjabaad", "weerar internet", "qalalaase", "xabbad-joojin"],
        "general": ["dibloomaasiyad", "wadahadal", "heshiis ganacsi", "safarka rasmiga ah", "ururka midowga afrika", "shir madaxeed"]
    },
    "Persian": {
        "critical": ["جنگ", "حمله", "موشک", "ترور", "درگیری", "انفجار", "تهاجم", "حمله هوایی", "تلفات", "هسته‌ای", "بمباران", "پهپاد"],
        "elevated": ["تحریم", "اعتراض", "تنش", "هشدار", "ممنوعیت", "مناقشه", "تهدید", "حمله سایبری", "ناآرامی", "بحران", "آتش‌بس"],
        "general": ["دیپلماسی", "مذاکرات", "سفر رسمی", "توافق تجاری", "پیمان", "سیاست خارجی", "سازمان ملل"]
    },
    "Turkish": {
        "critical": ["savaş", "saldırı", "füze", "suikast", "çatışma", "patlama", "işgal", "hava saldırısı", "can kaybı", "nükleer", "bombalama", "siha"],
        "elevated": ["yaptırım", "protesto", "gerilim", "uyarı", "yasak", "anlaşmazlık", "tehdit", "siber saldırı", "kriz", "askeri yığınak", "ateşkes"],
        "general": ["diplomasi", "ikili ilişkiler", "zirve", "ticaret anlaşması", "dış politika", "mutabakat", "büyükelçi"]
    }
}

# ==============================================================================
# HIERARCHICAL PUBLISHER & FEED MATRIX
# ==============================================================================
MASTER_CATALOG = [
    # --- NORTH AMERICA ---
    {"name": "The New York Times", "continent": "North America", "country": "United States", "category": "GENERAL", "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"},
    {"name": "The Washington Post", "continent": "North America", "country": "United States", "category": "GENERAL", "url": "https://feeds.washingtonpost.com/rss/world"},
    {"name": "The Wall Street Journal", "continent": "North America", "country": "United States", "category": "GENERAL", "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml"},
    {"name": "New York Post", "continent": "North America", "country": "United States", "category": "GENERAL", "url": "https://nypost.com/feed/"},
    {"name": "CNN", "continent": "North America", "country": "United States", "category": "ALL", "url": "http://rss.cnn.com/rss/edition_world.rss"},
    {"name": "Fox News", "continent": "North America", "country": "United States", "category": "ALL", "url": "https://moxie.foxnews.com/google-publisher/world.xml"},
    {"name": "ABC News", "continent": "North America", "country": "United States", "category": "ALL", "url": "https://abcnews.go.com/abcnews/internationalheadlines"},
    {"name": "CBS News", "continent": "North America", "country": "United States", "category": "ALL", "url": "https://www.cbsnews.com/latest/rss/world"},
    {"name": "NBC News", "continent": "North America", "country": "United States", "category": "ALL", "url": "https://feeds.nbcnews.com/nbcnews/public/world"},
    {"name": "Politico", "continent": "North America", "country": "United States", "category": "GENERAL", "url": "https://rss.politico.com/politics-news.xml"},
    {"name": "Foreign Policy", "continent": "North America", "country": "United States", "category": "GENERAL", "url": "https://foreignpolicy.com/feed/"},
    {"name": "Newsweek", "continent": "North America", "country": "United States", "category": "ALL", "url": "https://www.newsweek.com/rss"},

    # --- GLOBAL ---
    {"name": "Reuters", "continent": "Global", "country": "Global", "category": "ALL", "url": "https://news.google.com/rss/search?q=site:reuters.com+when:24h&hl=en-US&gl=US&ceid=US:en"},
    {"name": "The Economist", "continent": "Global", "country": "Global", "category": "GENERAL", "url": "https://www.economist.com/international/rss.xml"},

    # --- EUROPE ---
    {"name": "BBC World", "continent": "Europe", "country": "United Kingdom", "category": "ALL", "url": "http://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "The Guardian", "continent": "Europe", "country": "United Kingdom", "category": "ALL", "url": "https://www.theguardian.com/world/rss"},
    {"name": "The Telegraph", "continent": "Europe", "country": "United Kingdom", "category": "ALL", "url": "https://www.telegraph.co.uk/rss.xml"},
    {"name": "The Independent", "continent": "Europe", "country": "United Kingdom", "category": "ALL", "url": "https://www.independent.co.uk/news/world/rss"},
    {"name": "Le Monde", "continent": "Europe", "country": "France", "category": "GENERAL", "url": "https://www.lemonde.fr/international/rss_full.xml"},
    {"name": "Le Figaro", "continent": "Europe", "country": "France", "category": "GENERAL", "url": "https://www.lefigaro.fr/rss/figaro_international.xml"},
    {"name": "France 24", "continent": "Europe", "country": "France", "category": "ALL", "url": "https://www.france24.com/fr/rss"},
    {"name": "Libération", "continent": "Europe", "country": "France", "category": "GENERAL", "url": "https://www.liberation.fr/arc/outboundfeeds/rss-all/collection/accueil-monde/"},
    {"name": "Der Spiegel", "continent": "Europe", "country": "Germany", "category": "GENERAL", "url": "https://www.spiegel.de/international/index.rss"},
    {"name": "Deutsche Welle", "continent": "Europe", "country": "Germany", "category": "ALL", "url": "https://rss.dw.com/rdf/rss-en-world"},
    {"name": "FAZ", "continent": "Europe", "country": "Germany", "category": "GENERAL", "url": "https://www.faz.net/rss/aktuell/politik/ausland/"},
    {"name": "Die Welt", "continent": "Europe", "country": "Germany", "category": "GENERAL", "url": "https://www.welt.de/feeds/section/ausland.rss"},
    {"name": "El País", "continent": "Europe", "country": "Spain", "category": "GENERAL", "url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada"},
    {"name": "El Mundo", "continent": "Europe", "country": "Spain", "category": "GENERAL", "url": "https://e00-elmundo.uecdn.es/elmundo/rss/internacional.xml"},
    {"name": "Corriere della Sera", "continent": "Europe", "country": "Italy", "category": "GENERAL", "url": "https://xml2.corriere.it/rss/esteri.xml"},
    {"name": "La Repubblica", "continent": "Europe", "country": "Italy", "category": "GENERAL", "url": "https://www.repubblica.it/rss/esteri/rss2.0.xml"},
    {"name": "ANSA", "continent": "Europe", "country": "Italy", "category": "ALL", "url": "https://www.ansa.it/sito/notizie/mondo/mondo_rss.xml"},
    {"name": "NOS", "continent": "Europe", "country": "Netherlands", "category": "GENERAL", "url": "https://feeds.nos.nl/nosnieuwsbuitenland"},
    {"name": "Público", "continent": "Europe", "country": "Portugal", "category": "GENERAL", "url": "https://feeds.feedburner.com/PublicoRSS"},
    {"name": "Gazeta Wyborcza", "continent": "Europe", "country": "Poland", "category": "GENERAL", "url": "https://wyborcza.pl/pub/rss/swiat.xml"},
    {"name": "Kathimerini", "continent": "Europe", "country": "Greece", "category": "GENERAL", "url": "https://www.kathimerini.gr/world/rss"},
    {"name": "Index.hu", "continent": "Europe", "country": "Hungary", "category": "GENERAL", "url": "https://index.hu/24ora/rss/"},

    # --- AFRICA ---
    {"name": "Fana Broadcasting", "continent": "Africa", "country": "Ethiopia", "category": "ALL", "url": "https://news.google.com/rss/search?q=site:fanabc.com+when:24h&hl=en-US&gl=US&ceid=US:en"},
    {"name": "The Reporter Ethiopia", "continent": "Africa", "country": "Ethiopia", "category": "GENERAL", "url": "https://news.google.com/rss/search?q=site:thereporterethiopia.com+when:24h&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Addis Fortune", "continent": "Africa", "country": "Ethiopia", "category": "GENERAL", "url": "https://news.google.com/rss/search?q=site:addisfortune.news+when:24h&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Capital Ethiopia", "continent": "Africa", "country": "Ethiopia", "category": "GENERAL", "url": "https://news.google.com/rss/search?q=site:capitalethiopia.com+when:24h&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Joy Online", "continent": "Africa", "country": "Ghana", "category": "ALL", "url": "https://www.myjoyonline.com/feed/"},
    {"name": "GhanaWeb", "continent": "Africa", "country": "Ghana", "category": "ALL", "url": "https://news.google.com/rss/search?q=site:ghanaweb.com+when:24h&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Citi Newsroom", "continent": "Africa", "country": "Ghana", "category": "ALL", "url": "https://citinewsroom.com/feed/"},
    {"name": "Daily Graphic", "continent": "Africa", "country": "Ghana", "category": "GENERAL", "url": "https://news.google.com/rss/search?q=site:graphic.com.gh+when:24h&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Radio Okapi (DRC)", "continent": "Africa", "country": "Congo", "category": "RED", "url": "https://www.radiookapi.net/rss.xml"},
    {"name": "Guineematin", "continent": "Africa", "country": "Guinea", "category": "ALL", "url": "https://guineematin.com/feed/"},
    {"name": "Corbeau News Centrafrique", "continent": "Africa", "country": "Central African Republic", "category": "RED", "url": "https://corbeaunews-centrafrique.org/feed/"},
    {"name": "L'Express Maurice", "continent": "Africa", "country": "Mauritius", "category": "GENERAL", "url": "https://lexpress.mu/feed"},
    {"name": "Al-Ahram Online", "continent": "Africa", "country": "Egypt", "category": "GENERAL", "url": "https://english.ahram.org.eg/RSS/All.aspx"},
    {"name": "Daily News Egypt", "continent": "Africa", "country": "Egypt", "category": "GENERAL", "url": "https://dailynewsegypt.com/feed/"},
    {"name": "Egypt Independent", "continent": "Africa", "country": "Egypt", "category": "GENERAL", "url": "https://egyptindependent.com/feed/"},
    {"name": "Mada Masr", "continent": "Africa", "country": "Egypt", "category": "RED", "url": "https://www.madamasr.com/en/feed/"},
    {"name": "Sudan Tribune", "continent": "Africa", "country": "Sudan", "category": "RED", "url": "https://sudantribune.com/feed/"},
    {"name": "Radio Dabanga", "continent": "Africa", "country": "Sudan", "category": "RED", "url": "https://www.dabangasudan.org/en/feed"},
    {"name": "Hiiraan Online", "continent": "Africa", "country": "Somalia", "category": "RED", "url": "https://news.google.com/rss/search?q=site:hiiraan.com+when:24h&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Garowe Online", "continent": "Africa", "country": "Somalia", "category": "RED", "url": "https://www.garoweonline.com/en/rss/feed"},
    {"name": "The Star Kenya", "continent": "Africa", "country": "Kenya", "category": "GENERAL", "url": "https://www.the-star.co.ke/rss"},
    {"name": "Daily Nation", "continent": "Africa", "country": "Kenya", "category": "GENERAL", "url": "https://nation.africa/kenya/rss"},
    {"name": "Premium Times Nigeria", "continent": "Africa", "country": "Nigeria", "category": "GENERAL", "url": "https://www.premiumtimesng.com/feed"},
    {"name": "Punch Nigeria", "continent": "Africa", "country": "Nigeria", "category": "ALL", "url": "https://punchng.com/feed/"},
    {"name": "News24 South Africa", "continent": "Africa", "country": "South Africa", "category": "GENERAL", "url": "https://feeds.news24.com/articles/news24/TopStories/rss"},
    {"name": "Africanews", "continent": "Africa", "country": "Pan-Africa", "category": "GENERAL", "url": "https://www.africanews.com/feed/"},
    {"name": "AllAfrica", "continent": "Africa", "country": "Pan-Africa", "category": "GENERAL", "url": "https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf"},

    # --- MIDDLE EAST ---
    {"name": "Arab News", "continent": "Middle East", "country": "Saudi Arabia", "category": "RED", "url": "https://www.arabnews.com/cat/1/rss.xml"},
    {"name": "Asharq Al-Awsat", "continent": "Middle East", "country": "Saudi Arabia", "category": "RED", "url": "https://aawsat.com/feed"},
    {"name": "Saudi Gazette", "continent": "Middle East", "country": "Saudi Arabia", "category": "GENERAL", "url": "https://saudigazette.com.sa/rss"},
    {"name": "Tehran Times", "continent": "Middle East", "country": "Iran", "category": "RED", "url": "https://www.tehrantimes.com/rss"},
    {"name": "Mehr News Agency", "continent": "Middle East", "country": "Iran", "category": "RED", "url": "https://en.mehrnews.com/rss"},
    {"name": "Tasnim News", "continent": "Middle East", "country": "Iran", "category": "RED", "url": "https://www.tasnimnews.com/en/rss/feed"},
    {"name": "Shafaq News", "continent": "Middle East", "country": "Iraq", "category": "RED", "url": "https://shafaq.com/en/rss"},
    {"name": "Rudaw", "continent": "Middle East", "country": "Iraq", "category": "RED", "url": "https://www.rudaw.net/english/rss"},
    {"name": "Anadolu Agency", "continent": "Middle East", "country": "Turkey", "category": "GENERAL", "url": "https://www.aa.com.tr/en/rss/default?cat=current"},
    {"name": "Daily Sabah", "continent": "Middle East", "country": "Turkey", "category": "GENERAL", "url": "https://www.dailysabah.com/rss/world"},
    {"name": "TRT World", "continent": "Middle East", "country": "Turkey", "category": "ALL", "url": "https://www.trtworld.com/feed/rss"},
    {"name": "Times of Israel", "continent": "Middle East", "country": "Israel", "category": "RED", "url": "https://www.timesofisrael.com/feed/"},
    {"name": "Al Jazeera (English)", "continent": "Middle East", "country": "Qatar", "category": "RED", "url": "https://www.aljazeera.com/xml/rss/all.xml"}
]

OPTIONAL_FEEDS = {
    "middle_east_eye": {
        "name": "Middle East Eye",
        "continent": "Middle East",
        "country": "Regional",
        "category": "RED",
        "url": "https://www.middleeasteye.net/rss"
    }
}

# ==============================================================================
# DATABASE LAYER WITH AUTO-MIGRATION
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
                published_date TIMESTAMP,
                fetched_at TIMESTAMP,
                keyword TEXT DEFAULT '',
                threat_level TEXT DEFAULT 'INFORMATIONAL'
            )
        ''')
        
        c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='news'")
        existing_cols = [row[0] for row in c.fetchall()]
        
        if "continent" not in existing_cols:
            c.execute("ALTER TABLE news ADD COLUMN continent TEXT DEFAULT 'Global'")
        if "country" not in existing_cols:
            c.execute("ALTER TABLE news ADD COLUMN country TEXT DEFAULT 'Global'")
        if "language" not in existing_cols:
            c.execute("ALTER TABLE news ADD COLUMN language TEXT DEFAULT 'English'")
        if "thumbnail" not in existing_cols:
            c.execute("ALTER TABLE news ADD COLUMN thumbnail TEXT DEFAULT ''")

        c.execute('CREATE INDEX IF NOT EXISTS idx_cat_src_cont ON news (category, source, continent, country, published_date);')
        conn.close()
        logger.info("Database initialized with thumbnail engine.")
    except Exception as e:
        logger.error(f"Database init error: {e}")

# ==============================================================================
# THUMBNAIL & THREAT EXTRACTION
# ==============================================================================
def extract_thumbnail_from_raw(entry_dict_or_obj):
    """Deep search for media enclosures, OpenGraph tags, and embedded image strings"""
    if isinstance(entry_dict_or_obj, dict):
        if entry_dict_or_obj.get("thumbnail") and isinstance(entry_dict_or_obj["thumbnail"], str):
            return entry_dict_or_obj["thumbnail"]
        if entry_dict_or_obj.get("enclosure") and isinstance(entry_dict_or_obj["enclosure"], dict):
            if entry_dict_or_obj["enclosure"].get("link"):
                return entry_dict_or_obj["enclosure"]["link"]
        desc = entry_dict_or_obj.get("description", "") or entry_dict_or_obj.get("content", "")
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', str(desc), re.IGNORECASE)
        if img_match:
            return img_match.group(1)
    else:
        if hasattr(entry_dict_or_obj, 'media_content') and entry_dict_or_obj.media_content:
            for m in entry_dict_or_obj.media_content:
                if isinstance(m, dict) and 'url' in m: return m['url']
        if hasattr(entry_dict_or_obj, 'media_thumbnail') and entry_dict_or_obj.media_thumbnail:
            for m in entry_dict_or_obj.media_thumbnail:
                if isinstance(m, dict) and 'url' in m: return m['url']
        if hasattr(entry_dict_or_obj, 'enclosures') and entry_dict_or_obj.enclosures:
            for enc in entry_dict_or_obj.enclosures:
                if hasattr(enc, 'href'): return enc.href
                if isinstance(enc, dict) and 'href' in enc: return enc['href']
        summary = getattr(entry_dict_or_obj, 'summary', '') or getattr(entry_dict_or_obj, 'description', '')
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', str(summary), re.IGNORECASE)
        if img_match:
            return img_match.group(1)
    return ""

def analyze_multilingual_threat(title: str):
    t_lower = title.lower()
    matched_keyword = ""
    matched_lang = "English"
    heat_score = 0

    for lang, dicts in MULTILINGUAL_LEXICON.items():
        for kw in dicts["critical"]:
            if re.search(r'\b' + re.escape(kw.lower()) + r'\b', t_lower):
                heat_score += 3
                if not matched_keyword:
                    matched_keyword = kw
                    matched_lang = lang

        for kw in dicts["elevated"]:
            if re.search(r'\b' + re.escape(kw.lower()) + r'\b', t_lower):
                heat_score += 1.5
                if not matched_keyword:
                    matched_keyword = kw
                    matched_lang = lang

        for kw in dicts["general"]:
            if re.search(r'\b' + re.escape(kw.lower()) + r'\b', t_lower):
                heat_score += 1
                if not matched_keyword:
                    matched_keyword = kw
                    matched_lang = lang

    if heat_score >= 3.0: level = "CRITICAL"
    elif heat_score >= 1.0: level = "ELEVATED"
    else: level = "INFORMATIONAL"

    return level, (f"Matched: '{matched_keyword}'" if matched_keyword else ""), matched_lang

def save_items_bulk(items):
    if not items: return 0
    conn = get_db_connection()
    c = conn.cursor()
    added = 0
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for item in items:
        try:
            c.execute('''
                INSERT INTO news (title, link, source, category, handle, continent, country, region, language, thumbnail, published_date, fetched_at, keyword, threat_level)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(link) DO NOTHING
            ''', (
                item['title'], item['link'], item['source'], item['category'],
                item.get('handle', 'N/A'), item.get('continent', 'Global'),
                item.get('country', 'Global'), item.get('country', 'Global'),
                item.get('language', 'English'), item.get('thumbnail', ''),
                item['published_date'], now_iso, item.get('keyword', ''),
                item.get('threat_level', 'INFORMATIONAL')
            ))
            if c.rowcount > 0:
                added += 1
        except Exception:
            pass
    conn.close()
    return added

# ==============================================================================
# MAXIMUM YIELD PARALLEL HARVESTER
# ==============================================================================
async def fetch_publisher_feed(client, semaphore, publisher, limit=40):
    items = []
    async with semaphore:
        url = publisher["url"]
        name = publisher["name"]
        continent = publisher["continent"]
        country = publisher["country"]
        category = publisher["category"]

        try:
            if "google.com" not in url and "reddit.com" not in url:
                api_url = "https://api.rss2json.com/v1/api.json"
                response = await client.get(api_url, params={"rss_url": url}, timeout=12.0, follow_redirects=True)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "ok":
                        for entry in data.get("items", [])[:limit]:
                            title = entry.get("title", "").strip()
                            link = entry.get("link", "").strip()
                            pub_date = entry.get("pubDate", "") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            thumb = extract_thumbnail_from_raw(entry)
                            
                            if title and link:
                                threat, kw_badge, lang = analyze_multilingual_threat(title)
                                items.append({
                                    'title': title, 'link': link, 'source': name,
                                    'continent': continent, 'country': country, 'category': category,
                                    'published_date': pub_date, 'keyword': kw_badge,
                                    'threat_level': threat, 'language': lang, 'thumbnail': thumb
                                })
            else:
                response = await client.get(url, timeout=8.0, follow_redirects=True)
                if response.status_code == 200:
                    feed = await asyncio.to_thread(feedparser.parse, response.content)
                    for entry in feed.entries[:limit]:
                        title = getattr(entry, 'title', '').strip()
                        link = getattr(entry, 'link', '').strip()
                        thumb = extract_thumbnail_from_raw(entry)
                        
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
                                'title': title, 'link': link, 'source': name,
                                'continent': continent, 'country': country, 'category': category,
                                'published_date': pub_date, 'keyword': kw_badge,
                                'threat_level': threat, 'language': lang, 'thumbnail': thumb
                            })
        except Exception:
            pass
            
    return items

# ==============================================================================
# WEBSOCKET & SWEEP ENGINE
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
    continent: str = Query("All"),
    country: str = Query("All"),
    publisher: str = Query("All"),
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
    if continent != "All":
        query += " AND continent = %s"
        params.append(continent)
    if country != "All":
        query += " AND country = %s"
        params.append(country)
    if publisher != "All":
        query += " AND source = %s"
        params.append(publisher)
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
        query += " AND (title ILIKE %s OR source ILIKE %s OR keyword ILIKE %s)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        
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
            
        if not r.get('keyword') or r.get('keyword') == 'N/A':
            _, kw_badge, lang = analyze_multilingual_threat(r.get('title', ''))
            r['keyword'] = kw_badge
            r['language'] = lang
            
        results.append(r)
    
    return results

@app.get("/api/meta/catalog")
def get_catalog_metadata():
    hierarchy = {}
    publishers_set = set()
    
    for item in MASTER_CATALOG:
        cont = item["continent"]
        country = item["country"]
        pub = item["name"]
        
        publishers_set.add(pub)
        if cont not in hierarchy:
            hierarchy[cont] = {}
        if country not in hierarchy[cont]:
            hierarchy[cont][country] = []
        hierarchy[cont][country].append(pub)

    return {
        "hierarchy": hierarchy,
        "publishers": sorted(list(publishers_set)),
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
def export_csv(category: str = Query("ALL"), continent: str = Query("All"), country: str = Query("All"), publisher: str = Query("All")):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT source, category, continent, country, language, keyword, threat_level, title, link, published_date FROM news WHERE 1=1"
    params = []
    if category.upper() != "ALL":
        query += " AND category = %s"
        params.append(category.upper())
    if continent != "All":
        query += " AND continent = %s"
        params.append(continent)
    if country != "All":
        query += " AND country = %s"
        params.append(country)
    if publisher != "All":
        query += " AND source = %s"
        params.append(publisher)
        
    query += " ORDER BY published_date DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Source", "Category", "Continent", "Country", "Language", "Keyword Trigger", "Threat Level", "Title", "URL", "Timestamp"])
    for row in rows: 
        writer.writerow([row["source"], row["category"], row["continent"], row["country"], row["language"], row.get("keyword", ""), row.get("threat_level", "INFORMATIONAL"), row["title"], row["link"], row["published_date"]])
    
    output.seek(0)
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=intel_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return response

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
