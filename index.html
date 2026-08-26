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

app = FastAPI(title="Global Geopolitical Command Center", version="35.0 - The Boardroom Build")

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
# JOSIAH'S EXACT BOOLEAN & MULTILINGUAL LEXICONS
# ==============================================================================
MULTILINGUAL_LEXICON = {
    "English": {
        "critical": ["war", "strike", "attack", "missile", "assassination", "conflict", "explosion", "invasion", "airstrike", "casualty", "nuclear", "bombing", "artillery", "hostage", "idf", "offensive", "drone strike", "troops", "frontline", "combat", "terror", "muslim brotherhood", "cair", "migration crisis", "refugee", "border security", "illegal immigration", "sudan", "somalia", "iran", "ukraine", "russia", "demonstration", "protest", "parliament", "counter-terrorism", "middle east"],
        "elevated": ["sanctions", "tension", "warning", "ban", "dispute", "standoff", "threat", "cyberattack", "unrest", "crisis", "drill", "deployment", "ceasefire", "embargo", "coup", "blockade", "riot", "evacuation", "rebel"],
        "general": ["bilateral relations", "state visit", "diplomatic ties", "diplomatic mission", "foreign envoy", "ambassador meeting", "foreign ministry", "peace talks", "trade agreement", "foreign investment", "economic partnership", "tariff", "trade deal", "mou signed", "memorandum of understanding", "security partnership", "defense pact", "military agreement", "joint military exercise", "security cooperation", "defense treaty", "treaty signed", "international summit", "global governance", "un resolution", "international convention", "multilateral agreement", "geopolitical shift", "resource diplomacy", "foreign influence", "strategic alliance", "international relations", "diplomatic shift"]
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
    },
    "Spanish": {
        "critical": ["guerra", "ataque", "misil", "asesinato", "conflicto", "explosión", "invasión", "ataque aéreo", "víctimas", "nuclear", "bombardeo", "ofensiva", "rehén"],
        "elevated": ["sanciones", "protesta", "tensión", "advertencia", "prohibición", "disputa", "amenaza", "ciberataque", "disturbios", "crisis", "despliegue", "golpe de estado", "alto el fuego"],
        "general": ["diplomacia", "visita de estado", "embajador", "acuerdo comercial", "cumbre", "tratado", "política exterior", "elección"]
    },
    "Russian": {
        "critical": ["война", "удар", "атака", "ракета", "убийство", "конфликт", "взрыв", "вторжение", "авиаудар", "жертвы", "ядерный", "бомбардировка", "артиллерия", "заложник", "наступление"],
        "elevated": ["санкции", "протест", "напряженность", "предупреждение", "запрет", "спор", "угроза", "кибератака", "беспорядки", "кризис", "развертывание", "переворот", "прекращение огня"],
        "general": ["дипломатия", "государственный визит", "посол", "торговое соглашение", "саммит", "договор", "внешняя политика", "выборы"]
    },
    "Mandarin": {
        "critical": ["战争", "罢工", "袭击", "导弹", "暗杀", "冲突", "爆炸", "入侵", "空袭", "伤亡", "核武器", "轰炸", "炮兵", "人质", "攻势"],
        "elevated": ["制裁", "抗议", "紧张局势", "警告", "禁令", "争端", "威胁", "网络攻击", "动乱", "危机", "部署", "政变", "停火"],
        "general": ["外交", "国事访问", "大使", "贸易协定", "峰会", "条约", "外交政策", "选举"]
    }
}

# ==============================================================================
# MASTER PUBLISHER LIST (ULTIMATE SANCTION-PROOF FIREWALL BYPASS)
# ==============================================================================
MASTER_CATALOG = [
    # --- ARABIC (Bypass Google News Links) ---
    {"name": "BBC Arabic", "continent": "Middle East", "country": "Regional", "category": "ALL", "feed_type": "PUBLISHER", "language": "Arabic", "url": "https://feeds.bbci.co.uk/arabic/rss.xml"},
    {"name": "Sky News Arabia", "continent": "Middle East", "country": "UAE", "category": "ALL", "feed_type": "PUBLISHER", "language": "Arabic", "url": "https://news.google.com/rss/search?q=site:skynewsarabia.com&hl=ar&gl=AE&ceid=AE:ar"},
    {"name": "France 24 (Arabic)", "continent": "Middle East", "country": "Regional", "category": "ALL", "feed_type": "PUBLISHER", "language": "Arabic", "url": "https://www.france24.com/ar/rss"},
    {"name": "DW Arabic", "continent": "Middle East", "country": "Regional", "category": "ALL", "feed_type": "PUBLISHER", "language": "Arabic", "url": "https://rss.dw.com/rdf/rss-ar-all"},
    {"name": "Al Arabiya", "continent": "Middle East", "country": "Saudi Arabia", "category": "RED", "feed_type": "PUBLISHER", "language": "Arabic", "url": "https://news.google.com/rss/search?q=site:alarabiya.net&hl=ar&gl=SA&ceid=SA:ar"},
    {"name": "Asharq Al-Awsat (AR)", "continent": "Middle East", "country": "Saudi Arabia", "category": "RED", "feed_type": "PUBLISHER", "language": "Arabic", "url": "https://aawsat.com/feed"},
    {"name": "Saba Net Yemen", "continent": "Middle East", "country": "Yemen", "category": "RED", "feed_type": "PUBLISHER", "language": "Arabic", "url": "https://news.google.com/rss/search?q=site:sabanew.net&hl=ar&gl=YE&ceid=YE:ar"},

    # --- AMHARIC (Bypass Google News Links) ---
    {"name": "BBC News Amharic", "continent": "Africa", "country": "Ethiopia", "category": "ALL", "feed_type": "PUBLISHER", "language": "Amharic", "url": "https://feeds.bbci.co.uk/amharic/rss.xml"},
    {"name": "DW Amharic", "continent": "Africa", "country": "Ethiopia", "category": "ALL", "feed_type": "PUBLISHER", "language": "Amharic", "url": "https://rss.dw.com/rdf/rss-amh-news"},
    {"name": "VOA Amharic", "continent": "Africa", "country": "Ethiopia", "category": "ALL", "feed_type": "PUBLISHER", "language": "Amharic", "url": "https://news.google.com/rss/search?q=site:amharic.voanews.com&hl=am&gl=ET&ceid=ET:am"},
    {"name": "Fana Broadcasting", "continent": "Africa", "country": "Ethiopia", "category": "ALL", "feed_type": "PUBLISHER", "language": "Amharic", "url": "https://news.google.com/rss/search?q=site:fanabc.com&hl=am&gl=ET&ceid=ET:am"},

    # --- SPANISH / SOUTH AMERICA (Bypass Google News Links) ---
    {"name": "CNN en Español", "continent": "North America", "country": "United States", "category": "ALL", "feed_type": "PUBLISHER", "language": "Spanish", "url": "https://news.google.com/rss/search?q=site:cnnespanol.cnn.com&hl=es&gl=US&ceid=US:es"},
    {"name": "Clarín", "continent": "South America", "country": "Argentina", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "Spanish", "url": "https://news.google.com/rss/search?q=site:clarin.com&hl=es-419&gl=AR&ceid=AR:es-419"},
    {"name": "El Tiempo", "continent": "South America", "country": "Colombia", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "Spanish", "url": "https://news.google.com/rss/search?q=site:eltiempo.com&hl=es-419&gl=CO&ceid=CO:es-419"},
    {"name": "Folha de S.Paulo", "continent": "South America", "country": "Brazil", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "Spanish", "url": "https://news.google.com/rss/search?q=site:folha.uol.com.br/mundo&hl=pt-BR&gl=BR&ceid=BR:pt-419"},
    {"name": "RT Spanish", "continent": "South America", "country": "Regional", "category": "ALL", "feed_type": "PUBLISHER", "language": "Spanish", "url": "https://news.google.com/rss/search?q=site:actualidad.rt.com&hl=es-419&gl=US&ceid=US:es-419"},
    {"name": "UN News Spanish", "continent": "Global", "country": "Global", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "Spanish", "url": "https://news.un.org/feed/subscribe/es/news/all/rss.xml"},
    {"name": "El País", "continent": "Europe", "country": "Spain", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "Spanish", "url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada"},
    
    # --- FRENCH ---
    {"name": "Le Monde", "continent": "Europe", "country": "France", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "French", "url": "https://www.lemonde.fr/international/rss_full.xml"},
    {"name": "France 24", "continent": "Europe", "country": "France", "category": "ALL", "feed_type": "PUBLISHER", "language": "French", "url": "https://www.france24.com/fr/rss"},
    {"name": "RFI Afrique", "continent": "Africa", "country": "Regional", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "French", "url": "https://news.google.com/rss/search?q=site:rfi.fr/fr/afrique&hl=fr&gl=FR&ceid=FR:fr"},
    {"name": "Les Dépêches de Brazzaville", "continent": "Africa", "country": "Congo", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "French", "url": "https://news.google.com/rss/search?q=site:adiac-congo.com&hl=fr&gl=FR&ceid=FR:fr"},

    # --- RUSSIAN ---
    {"name": "BBC Russian", "continent": "Europe", "country": "Russia", "category": "ALL", "feed_type": "PUBLISHER", "language": "Russian", "url": "https://feeds.bbci.co.uk/russian/rss.xml"},
    {"name": "DW Russian", "continent": "Europe", "country": "Russia", "category": "ALL", "feed_type": "PUBLISHER", "language": "Russian", "url": "https://rss.dw.com/rdf/rss-ru-all"},
    {"name": "UN News Russian", "continent": "Global", "country": "Global", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "Russian", "url": "https://news.un.org/feed/subscribe/ru/news/all/rss.xml"},

    # --- MANDARIN / CHINESE ---
    {"name": "BBC Chinese", "continent": "Asia", "country": "China", "category": "ALL", "feed_type": "PUBLISHER", "language": "Mandarin", "url": "http://feeds.bbci.co.uk/zhongwen/simp/rss.xml"},
    {"name": "UN News Chinese", "continent": "Global", "country": "Global", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "Mandarin", "url": "https://news.un.org/feed/subscribe/zh/news/all/rss.xml"},

    # --- ENGLISH (AFRICA, MIDDLE EAST, GLOBAL) ---
    {"name": "The New York Times", "continent": "North America", "country": "United States", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "English", "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"},
    {"name": "The Washington Post", "continent": "North America", "country": "United States", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "English", "url": "https://feeds.washingtonpost.com/rss/world"},
    {"name": "CNN", "continent": "North America", "country": "United States", "category": "ALL", "feed_type": "PUBLISHER", "language": "English", "url": "http://rss.cnn.com/rss/edition_world.rss"},
    {"name": "Reuters", "continent": "Global", "country": "Global", "category": "ALL", "feed_type": "PUBLISHER", "language": "English", "url": "https://news.google.com/rss/search?q=site:reuters.com+when:24h&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Daily Nation", "continent": "Africa", "country": "Kenya", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "English", "url": "https://news.google.com/rss/search?q=site:nation.africa&hl=en-KE&gl=KE&ceid=KE:en"},
    {"name": "News24", "continent": "Africa", "country": "South Africa", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "English", "url": "https://news.google.com/rss/search?q=site:news24.com&hl=en-ZA&gl=ZA&ceid=ZA:en"},
    {"name": "Al Jazeera (English)", "continent": "Middle East", "country": "Qatar", "category": "RED", "feed_type": "PUBLISHER", "language": "English", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"name": "r/UkrainianConflict", "continent": "Europe", "country": "Ukraine", "category": "RED", "feed_type": "SOCIAL", "language": "English", "url": "https://www.reddit.com/r/UkrainianConflict/new.rss"},
    {"name": "r/Geopolitics", "continent": "Global", "country": "Global", "category": "ALL", "feed_type": "SOCIAL", "language": "English", "url": "https://www.reddit.com/r/geopolitics/new.rss"}
]

# ==============================================================================
# JOSIAH'S OFFICIAL SOCIAL HANDLES
# ==============================================================================
SOCIAL_CATALOG = [
    # US Officials
    {"handle": "@POTUS", "continent": "North America", "country": "United States", "category": "ALL", "language": "English"},
    {"handle": "@StateDept", "continent": "North America", "country": "United States", "category": "ALL", "language": "English"},
    
    # Africa Leaders
    {"handle": "@WilliamsRuto", "continent": "Africa", "country": "Kenya", "category": "GENERAL", "language": "English"},
    {"handle": "@PaulKagame", "continent": "Africa", "country": "Rwanda", "category": "GENERAL", "language": "English"},
    {"handle": "@CyrilRamaphosa", "continent": "Africa", "country": "South Africa", "category": "GENERAL", "language": "English"},
    {"handle": "@NGRPresident", "continent": "Africa", "country": "Nigeria", "category": "GENERAL", "language": "English"},
    {"handle": "@AlsisiOfficial", "continent": "Africa", "country": "Egypt", "category": "GENERAL", "language": "Arabic"},
    
    # Europe Leaders
    {"handle": "@EmmanuelMacron", "continent": "Europe", "country": "France", "category": "GENERAL", "language": "French"},
    {"handle": "@sanchezcastejon", "continent": "Europe", "country": "Spain", "category": "GENERAL", "language": "Spanish"},

    # Middle East
    {"handle": "@KingSalman", "continent": "Middle East", "country": "Saudi Arabia", "category": "RED", "language": "Arabic"},
    {"handle": "@mofauae", "continent": "Middle East", "country": "UAE", "category": "RED", "language": "Arabic"},
    {"handle": "@netanyahu", "continent": "Middle East", "country": "Israel", "category": "RED", "language": "English"},
    
    # Desks
    {"handle": "@BBCBreaking", "continent": "Europe", "country": "United Kingdom", "category": "ALL", "language": "English"}
]

# ==============================================================================
# DATABASE LAYER WITH MASSIVE RETROACTIVE AUTO-HEALER
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
        c.execute('CREATE INDEX IF NOT EXISTS idx_cat_src_cont_lang ON news (category, source, feed_type, language, continent, published_date);')
        
        # AGGRESSIVE AUTO-HEALER: Forces perfect accuracy of old records so filters ALWAYS work
        for pub in MASTER_CATALOG:
            c.execute("UPDATE news SET language = %s, continent = %s, country = %s, category = %s WHERE source = %s", 
                      (pub.get("language", "English"), pub["continent"], pub["country"], pub["category"], pub["name"]))
                
        for soc in SOCIAL_CATALOG:
            c.execute("UPDATE news SET language = %s, continent = %s, country = %s, category = %s WHERE handle = %s", 
                      (soc.get("language", "English"), soc["continent"], soc["country"], soc["category"], soc["handle"]))
                
        conn.close()
        logger.info("Database schema initialized and retroactive data auto-healer executed successfully.")
    except Exception as e:
        logger.error(f"Database init error: {e}")

# ==============================================================================
# UNICODE SCRIPT DETECTOR & MEDIA EXTRACTOR
# ==============================================================================
def extract_thumbnail(entry_obj):
    if isinstance(entry_obj, dict):
        if entry_obj.get("thumbnail") and isinstance(entry_obj["thumbnail"], str): return entry_obj["thumbnail"]
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

def analyze_multilingual_threat(title: str, feed_lang: str):
    t_lower = title.lower()
    matched_keyword = ""
    heat_score = 0
    
    for lang, dicts in MULTILINGUAL_LEXICON.items():
        for kw in dicts["critical"]:
            if kw.lower() in t_lower:
                heat_score += 3
                if not matched_keyword: matched_keyword = kw
        for kw in dicts["elevated"]:
            if kw.lower() in t_lower:
                heat_score += 1.5
                if not matched_keyword: matched_keyword = kw
        for kw in dicts["general"]:
            if kw.lower() in t_lower:
                heat_score += 1
                if not matched_keyword: matched_keyword = kw

    if heat_score >= 3.0: level = "CRITICAL"
    elif heat_score >= 1.0: level = "ELEVATED"
    else: level = "INFORMATIONAL"

    return level, (f"Matched: '{matched_keyword}'" if matched_keyword else ""), feed_lang

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
                ON CONFLICT(link) DO UPDATE SET
                    language = EXCLUDED.language,
                    keyword = CASE WHEN EXCLUDED.keyword != '' THEN EXCLUDED.keyword ELSE news.keyword END,
                    threat_level = EXCLUDED.threat_level,
                    continent = EXCLUDED.continent,
                    country = EXCLUDED.country,
                    source = EXCLUDED.source,
                    thumbnail = CASE WHEN news.thumbnail = '' THEN EXCLUDED.thumbnail ELSE news.thumbnail END
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
        feed_lang = publisher.get("language", "English")

        try:
            response = await client.get(url, timeout=9.0, follow_redirects=True)
            if response.status_code == 200:
                feed = await asyncio.to_thread(feedparser.parse, response.content)
                for entry in feed.entries[:limit]:
                    title = getattr(entry, 'title', '').strip()
                    link = getattr(entry, 'link', '').strip()
                    thumb = extract_thumbnail(entry)
                    try:
                        if hasattr(entry, 'published_parsed') and entry.published_parsed: pub_date = time.strftime("%Y-%m-%d %H:%M:%S", entry.published_parsed)
                        else: pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    except: pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    if title and link:
                        threat, kw_badge, final_lang = analyze_multilingual_threat(title, feed_lang)
                        items.append({'title': title, 'link': link, 'source': name, 'handle': 'N/A', 'continent': continent, 'country': country, 'category': category, 'feed_type': feed_type, 'published_date': pub_date, 'keyword': kw_badge, 'threat_level': threat, 'language': final_lang, 'thumbnail': thumb})
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
                                threat, kw_badge, final_lang = analyze_multilingual_threat(title, feed_lang)
                                items.append({'title': title, 'link': link, 'source': name, 'handle': 'N/A', 'continent': continent, 'country': country, 'category': category, 'feed_type': feed_type, 'published_date': pub_date, 'keyword': kw_badge, 'threat_level': threat, 'language': final_lang, 'thumbnail': thumb})
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
        feed_lang = target.get("language", "English")
        
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
                        if hasattr(entry, 'published_parsed') and entry.published_parsed: pub_date = time.strftime("%Y-%m-%d %H:%M:%S", entry.published_parsed)
                        else: pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    except: pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    if clean_title and link:
                        threat, kw_badge, final_lang = analyze_multilingual_threat(clean_title, feed_lang)
                        items.append({'title': clean_title, 'link': link, 'source': 'X (Twitter)', 'handle': handle, 'continent': continent, 'country': country, 'category': category, 'feed_type': 'SOCIAL', 'published_date': pub_date, 'keyword': kw_badge or f"Account: {handle}", 'threat_level': threat, 'language': final_lang, 'thumbnail': thumb})
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
            try: await connection.send_text(message)
            except Exception: self.disconnect(connection)

manager = ConnectionManager()
is_syncing = False

async def run_fast_sweep():
    semaphore = asyncio.Semaphore(15) 
    limits = httpx.Limits(max_keepalive_connections=60, max_connections=120)
    
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, limits=limits) as client:
        tasks = [fetch_publisher_feed(client, semaphore, pub) for pub in MASTER_CATALOG]
        tasks += [fetch_social_target(client, semaphore, sock) for sock in SOCIAL_CATALOG]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_results = [item for sublist in results if isinstance(sublist, list) for item in sublist]
        return await asyncio.to_thread(save_items_bulk, all_results)

async def async_sweep_controller(silent=False):
    global is_syncing
    if is_syncing: return
    is_syncing = True

    event_start = "sync_started_silent" if silent else "sync_started"
    await manager.broadcast(json.dumps({"event": event_start}))

    try:
        total_added = await run_fast_sweep()
        timestamp = datetime.now().strftime("%I:%M %p")
        await manager.broadcast(json.dumps({"event": "new_intel", "count": total_added, "silent": silent, "time": timestamp}))
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
def ping(): return {"status": "awake"}

@app.websocket("/ws/news")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/api/sync")
async def trigger_manual_sync(background_tasks: BackgroundTasks):
    global is_syncing
    if is_syncing: return {"status": "Sync in progress"}
    background_tasks.add_task(async_sweep_controller, False)
    return {"status": "Sweep triggered"}

@app.get("/api/news")
async def get_news(
    category: str = Query("ALL"), publisher: str = Query("All"), handle: str = Query("All"),
    language: str = Query("All"), continent: str = Query("All"), country: str = Query("All"),
    time_filter: str = Query("all"), start_date: str = Query(None), end_date: str = Query(None), 
    q: str = Query(None), page: int = Query(1), limit: int = Query(30)
):
    offset = (page - 1) * limit
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM news WHERE 1=1"
    params = []
    
    # FLAWLESS MATRIX ROUTING: Ensures no filters cancel each other out
    if category.upper() != "ALL": query += " AND category = %s"; params.append(category.upper())
    
    if publisher != "All" and handle != "All":
        query += " AND (source = %s OR handle = %s)"
        params.extend([publisher, handle])
    elif publisher != "All":
        query += " AND source = %s"
        params.append(publisher)
    elif handle != "All":
        query += " AND handle = %s"
        params.append(handle)
        
    if continent != "All": query += " AND continent = %s"; params.append(continent)
    if country != "All": query += " AND country = %s"; params.append(country)
    if language != "All": query += " AND language = %s"; params.append(language)

    if start_date or end_date:
        if start_date: query += " AND published_date >= %s::timestamp"; params.append(f"{start_date} 00:00:00")
        if end_date: query += " AND published_date <= %s::timestamp"; params.append(f"{end_date} 23:59:59")
    else:
        time_mappings = {"1h": "1 hour", "4h": "4 hours", "8h": "8 hours", "12h": "12 hours", "1d": "1 day", "3d": "3 days", "7d": "7 days", "14d": "14 days", "30d": "30 days"}
        if time_filter in time_mappings: query += f" AND published_date >= NOW() - INTERVAL '{time_mappings[time_filter]}'"

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
        if isinstance(r.get('published_date'), datetime): r['published_date'] = r['published_date'].strftime("%Y-%m-%d %H:%M:%S")
        results.append(r)
    return results

@app.get("/api/meta/catalog")
def get_catalog_metadata():
    hierarchy = {}
    publishers_set = set()
    handles_set = set()
    
    all_continents = ["Africa", "Middle East", "North America", "South America", "Europe", "Asia", "Oceania", "Global"]
    for c in all_continents:
        if c not in hierarchy:
            hierarchy[c] = {}

    for item in MASTER_CATALOG:
        cont = item["continent"]
        country = item["country"]
        pub = item["name"]
        publishers_set.add(pub)
        if cont not in hierarchy: hierarchy[cont] = {}
        if country not in hierarchy[cont]: hierarchy[cont][country] = []
        if pub not in hierarchy[cont][country]: hierarchy[cont][country].append(pub)

    for item in SOCIAL_CATALOG:
        handles_set.add(item["handle"])

    return {
        "hierarchy": hierarchy,
        "publishers": sorted(list(publishers_set)),
        "handles": sorted(list(handles_set)),
        "languages": list(MULTILINGUAL_LEXICON.keys())
    }

@app.get("/api/stats")
def get_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DATE(published_date) as date, category, COUNT(*) as count FROM news WHERE published_date IS NOT NULL GROUP BY DATE(published_date), category ORDER BY DATE(published_date) ASC LIMIT 14")
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
    category: str = Query("ALL"), publisher: str = Query("All"), handle: str = Query("All"),
    language: str = Query("All"), continent: str = Query("All"), country: str = Query("All")
):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT feed_type, source, handle, category, continent, country, language, keyword, threat_level, title, link, published_date FROM news WHERE 1=1"
    params = []
    if category.upper() != "ALL": query += " AND category = %s"; params.append(category.upper())
    if publisher != "All": query += " AND source = %s"; params.append(publisher)
    if handle != "All": query += " AND handle = %s"; params.append(handle)
    if continent != "All": query += " AND continent = %s"; params.append(continent)
    if country != "All": query += " AND country = %s"; params.append(country)
    if language != "All": query += " AND language = %s"; params.append(language)
        
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
