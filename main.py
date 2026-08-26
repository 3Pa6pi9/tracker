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

app = FastAPI(title="Global Geopolitical Command Center", version="28.0 - Master All-Continents & Multilingual Matrix")

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
# MULTILINGUAL THREAT & GEOPOLITICAL LEXICONS (10 LANGUAGES)
# ==============================================================================
MULTILINGUAL_LEXICON = {
    "English": {
        "critical": [
            "war", "strike", "attack", "missile", "assassination", "conflict", "explosion", "invasion", "airstrike", "casualty", "nuclear", "bombing", "artillery", "hostage", "idf", "offensive", "drone strike", "troops", "frontline", "combat", "terror", "insurgency", "militia", "ambush",
            "muslim brotherhood", "cair", "migration crisis", "refugee", "border security", "illegal immigration", "sudan", "somalia", "iran", "ukraine", "russia", "demonstration", "protest", "parliament", "counter-terrorism", "middle east"
        ],
        "elevated": [
            "sanctions", "tension", "warning", "ban", "dispute", "standoff", "threat", "cyberattack", "unrest", "crisis", "drill", "deployment", "ceasefire", "embargo", "coup", "blockade", "riot", "evacuation", "rebel"
        ],
        "general": [
            "bilateral relations", "state visit", "diplomatic ties", "diplomatic mission", "foreign envoy", "ambassador meeting", "foreign ministry", "peace talks", "election", "parliamentary",
            "trade agreement", "foreign investment", "economic partnership", "tariff", "trade deal", "mou signed", "memorandum of understanding", "export", "import", "imf", "world bank",
            "security partnership", "defense pact", "military agreement", "joint military exercise", "security cooperation", "defense treaty",
            "treaty signed", "international summit", "global governance", "un resolution", "international convention", "multilateral agreement",
            "geopolitical shift", "resource diplomacy", "foreign influence", "strategic alliance", "international relations", "diplomatic shift", "humanitarian aid"
        ]
    },
    "Arabic": {
        "critical": ["حرب", "غارة", "هجوم", "صاروخ", "اغتيال", "نزاع", "انفجار", "غزو", "ضربة جوية", "قصف", "قتلى", "نووي", "شهداء", "مواجهات مسلحة", "مسيرة", "جيش", "اشتباكات", "استهداف", "طيران", "إرهاب", "تمرد", "كمين", "شهيد", "غزة", "الحوثي", "حماس", "حزب الله"],
        "elevated": ["عقوبات", "احتجاج", "توتر", "تحذير", "حظر", "خلاف", "تهديد", "هجوم سيبراني", "اضطرابات", "أزمة", "انتشار عسكري", "مظاهرات", "وقف إطلاق النار", "حشود", "حصار", "انقلاب", "شغب", "لاجئين", "حدود"],
        "general": ["دبلوماسية", "قمة", "زيارة رسمية", "اتفاقية تجارية", "استثمار أجنبي", "معاهدة", "مجلس الأمن", "جامعة الدول العربية", "الاتحاد الأفريقي", "مباحثات", "انتخابات", "مساعدات إنسانية", "استيراد", "تصدير", "وزير الخارجية"]
    },
    "Amharic": {
        "critical": ["ጦርነት", "ጥቃት", "ሚሳይል", "ግድያ", "ግጭት", "ፍንዳታ", "ወረራ", "የአየር ድብደባ", "የሰው ጉዳት", "የኑክሌር", "ቦምብ", "የድሮን ጥቃት", "የታጠቀ ቡድን", "ተኩስ", "ግድያዎች", "የጦር ሰራዊት", "አሸባሪ", "አማፂ"],
        "elevated": ["ማዕቀብ", "ተቃውሞ", "ውጥረት", "ማስጠንቀቂያ", "እገዳ", "አለመግባባት", "ስጋት", "የሳይበር ጥቃት", "ቀውስ", "ወታደራዊ ዝግጅት", "ድንበር ጥበቃ", "የተኩስ አቁም", "አደጋ", "መፈንቅለ መንግስት", "ረብሻ"],
        "general": ["ዲፕሎማሲ", "የሁለትዮሽ", "የውጭ ጉዳይ", "የንግድ ስምምነት", "የአፍሪካ ህብረት", "ስምምነት", "የሰላም ንግግር", "ጉባኤ", "ውይይት", "ሽርክና", "ምርጫ", "እርዳታ", "ኢንቨስትመንት"]
    },
    "French": {
        "critical": ["guerre", "frappe", "attaque", "missile", "assassinat", "conflit", "explosion", "invasion", "frappe aérienne", "victimes", "nucléaire", "bombardement", "offensive", "otage", "terrorisme", "milice", "embuscade"],
        "elevated": ["sanctions", "manifestation", "tension", "avertissement", "interdiction", "différend", "menace", "cyberattaque", "émeutes", "crise", "déploiement", "coup d'état", "cessez-le-feu", "blocus", "rébellion"],
        "general": ["diplomatie", "visite d'état", "ambassadeur", "accord commercial", "sommet", "union africaine", "union européenne", "traité", "politique étrangère", "élection", "aide humanitaire", "investissement étranger"]
    },
    "Spanish": {
        "critical": ["guerra", "ataque", "misil", "asesinato", "conflicto", "explosión", "invasión", "ataque aéreo", "víctimas", "nuclear", "bombardeo", "ofensiva", "rehén", "terrorismo", "milicia", "emboscada"],
        "elevated": ["sanciones", "protesta", "tensión", "advertencia", "prohibición", "disputa", "amenaza", "ciberataque", "disturbios", "crisis", "despliegue", "golpe de estado", "alto el fuego", "bloqueo", "rebelión"],
        "general": ["diplomacia", "visita de estado", "embajador", "acuerdo comercial", "cumbre", "tratado", "política exterior", "elección", "ayuda humanitaria", "inversión extranjera"]
    },
    "Russian": {
        "critical": ["война", "удар", "атака", "ракета", "убийство", "конфликт", "взрыв", "вторжение", "авиаудар", "жертвы", "ядерный", "бомбардировка", "артиллерия", "заложник", "наступление", "терроризм", "ополчение", "засада"],
        "elevated": ["санкции", "протест", "напряженность", "предупреждение", "запрет", "спор", "угроза", "кибератака", "беспорядки", "кризис", "развертывание", "переворот", "прекращение огня", "блокада", "восстание"],
        "general": ["дипломатия", "государственный визит", "посол", "торговое соглашение", "саммит", "договор", "внешняя политика", "выборы", "гуманитарная помощь", "иностранные инвестиции"]
    },
    "Mandarin": {
        "critical": ["战争", "罢工", "袭击", "导弹", "暗杀", "冲突", "爆炸", "入侵", "空袭", "伤亡", "核武器", "轰炸", "炮兵", "人质", "攻势", "恐怖主义", "民兵", "伏击"],
        "elevated": ["制裁", "抗议", "紧张局势", "警告", "禁令", "争端", "威胁", "网络攻击", "动乱", "危机", "部署", "政变", "停火", "封锁", "叛乱"],
        "general": ["外交", "国事访问", "大使", "贸易协定", "峰会", "条约", "外交政策", "选举", "人道主义援助", "外国投资"]
    },
    "Persian": {
        "critical": ["جنگ", "حمله", "موشک", "ترور", "درگیری", "انفجار", "تهاجم", "حمله هوایی", "تلفات", "هسته‌ای", "بمباران", "توپخانه", "گروگان", "تروریسم", "شبه نظامیان", "کمین"],
        "elevated": ["تحریم", "اعتراض", "تنش", "هشدار", "ممنوعیت", "مناقشه", "تهدید", "حمله سایبری", "ناآرامی", "بحران", "استقرار", "کودتا", "آتش‌بس", "محاصره", "شورش"],
        "general": ["دیپلماسی", "سفر رسمی", "سفیر", "توافق تجاری", "اجلاس", "معاهده", "سیاست خارجی", "انتخابات", "کمک‌های بشردوستانه", "سرمایه‌گذاری خارجی"]
    },
    "Turkish": {
        "critical": ["savaş", "saldırı", "füze", "suikast", "çatışma", "patlama", "işgal", "hava saldırısı", "can kaybı", "nükleer", "bombalama", "topçu", "rehine", "terörizm", "milis", "pusu"],
        "elevated": ["yaptırım", "protesto", "gerilim", "uyarı", "yasak", "anlaşmazlık", "tehdit", "siber saldırı", "huzursuzluk", "kriz", "konuşlandırma", "darbe", "ateşkes", "abluka", "isyan"],
        "general": ["diplomasi", "devlet ziyareti", "büyükelçi", "ticaret anlaşması", "zirve", "antlaşma", "dış politika", "seçim", "insani yardım", "yabancı yatırım"]
    },
    "Swahili": {
        "critical": ["vita", "shambulio", "kombora", "mauaji", "mgogoro", "mlipuko", "uvamizi", "shambulio la anga", "vifo", "nyuklia", "mabomu", "mateka", "ugaidi", "anamgambo", "kuvizia"],
        "elevated": ["vikwazo", "maandamano", "mvutano", "onyo", "marufuku", "mzozo", "tishio", "shambulio la mtandao", "machafuko", "mgogoro", "kikosi", "mapinduzi", "kusitisha mapigano", "kuzingirwa", "uasi"],
        "general": ["diplomasia", "ziara ya kiserikali", "balozi", "mkataba wa biashara", "mkutano", "mkataba", "sera za kigeni", "uchaguzi", "msaada wa kibinadamu", "uwekezaji wa kigeni"]
    }
}

# ==============================================================================
# HIERARCHICAL PUBLISHER MASTER LIST (ALL CONTINENTS & NATIVE ARABIC STREAMS)
# ==============================================================================
MASTER_CATALOG = [
    # --- ARABIC NATIVE STREAMS (DIRECT HIGH-YIELD RSS) ---
    {"name": "BBC Arabic", "continent": "Middle East", "country": "Regional", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://feeds.bbci.co.uk/arabic/rss.xml"},
    {"name": "Sky News Arabia", "continent": "Middle East", "country": "UAE", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://www.skynewsarabia.com/rss"},
    {"name": "France 24 (Arabic)", "continent": "Middle East", "country": "Regional", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://www.france24.com/ar/rss"},
    {"name": "DW Arabic", "continent": "Middle East", "country": "Regional", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://rss.dw.com/rdf/rss-ar-all"},
    {"name": "RT Arabic", "continent": "Middle East", "country": "Regional", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://arabic.rt.com/rss/"},
    {"name": "Al Arabiya", "continent": "Middle East", "country": "Saudi Arabia", "category": "RED", "feed_type": "PUBLISHER", "url": "https://www.alarabiya.net/.mrss/ar.xml"},
    {"name": "Asharq Al-Awsat (AR)", "continent": "Middle East", "country": "Saudi Arabia", "category": "RED", "feed_type": "PUBLISHER", "url": "https://aawsat.com/feed"},
    {"name": "Hespress", "continent": "Africa", "country": "Morocco", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://www.hespress.com/feed"},
    {"name": "Saba Net (Yemen)", "continent": "Middle East", "country": "Yemen", "category": "RED", "feed_type": "PUBLISHER", "url": "https://news.google.com/rss/search?q=site:sabanew.net&hl=ar&gl=YE&ceid=YE:ar"},

    # --- AFRICA ---
    {"name": "BBC News Amharic", "continent": "Africa", "country": "Ethiopia", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://feeds.bbci.co.uk/amharic/rss.xml"},
    {"name": "DW Amharic", "continent": "Africa", "country": "Ethiopia", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://rss.dw.com/rdf/rss-amh-news"},
    {"name": "Fana Broadcasting", "continent": "Africa", "country": "Ethiopia", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://news.google.com/rss/search?q=site:fanabc.com/archives&hl=am&gl=ET&ceid=ET:am"},
    {"name": "The Reporter Ethiopia", "continent": "Africa", "country": "Ethiopia", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://news.google.com/rss/search?q=site:thereporterethiopia.com&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Addis Fortune", "continent": "Africa", "country": "Ethiopia", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://news.google.com/rss/search?q=site:addisfortune.news&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Daily Nation", "continent": "Africa", "country": "Kenya", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://nation.africa/kenya/rss"},
    {"name": "The Star Kenya", "continent": "Africa", "country": "Kenya", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://www.the-star.co.ke/rss"},
    {"name": "Premium Times", "continent": "Africa", "country": "Nigeria", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://www.premiumtimesng.com/feed"},
    {"name": "News24 South Africa", "continent": "Africa", "country": "South Africa", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://feeds.news24.com/articles/news24/TopStories/rss"},
    {"name": "Joy Online", "continent": "Africa", "country": "Ghana", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://www.myjoyonline.com/feed/"},
    {"name": "Les Dépêches de Brazzaville", "continent": "Africa", "country": "Congo", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://news.google.com/rss/search?q=site:adiac-congo.com&hl=fr&gl=FR&ceid=FR:fr"},
    {"name": "Al-Ahram Online", "continent": "Africa", "country": "Egypt", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://english.ahram.org.eg/RSS/All.aspx"},
    {"name": "Mada Masr", "continent": "Africa", "country": "Egypt", "category": "RED", "feed_type": "PUBLISHER", "url": "https://www.madamasr.com/en/feed/"},
    {"name": "Sudan Tribune", "continent": "Africa", "country": "Sudan", "category": "RED", "feed_type": "PUBLISHER", "url": "https://sudantribune.com/feed/"},
    {"name": "Hiiraan Online", "continent": "Africa", "country": "Somalia", "category": "RED", "feed_type": "PUBLISHER", "url": "https://news.google.com/rss/search?q=site:hiiraan.com&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Africanews", "continent": "Africa", "country": "Pan-Africa", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://www.africanews.com/feed/"},

    # --- MIDDLE EAST (ENGLISH & REGIONAL) ---
    {"name": "Arab News", "continent": "Middle East", "country": "Saudi Arabia", "category": "RED", "feed_type": "PUBLISHER", "url": "https://www.arabnews.com/cat/1/rss.xml"},
    {"name": "Al Jazeera (English)", "continent": "Middle East", "country": "Qatar", "category": "RED", "feed_type": "PUBLISHER", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"name": "Times of Israel", "continent": "Middle East", "country": "Israel", "category": "RED", "feed_type": "PUBLISHER", "url": "https://www.timesofisrael.com/feed/"},
    {"name": "Tehran Times", "continent": "Middle East", "country": "Iran", "category": "RED", "feed_type": "PUBLISHER", "url": "https://www.tehrantimes.com/rss"},
    {"name": "Shafaq News", "continent": "Middle East", "country": "Iraq", "category": "RED", "feed_type": "PUBLISHER", "url": "https://shafaq.com/en/rss"},
    {"name": "TRT World", "continent": "Middle East", "country": "Turkey", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://www.trtworld.com/feed/rss"},
    {"name": "Hürriyet", "continent": "Middle East", "country": "Turkey", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://www.hurriyetdailynews.com/rss"},

    # --- NORTH AMERICA ---
    {"name": "The New York Times", "continent": "North America", "country": "United States", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"},
    {"name": "The Washington Post", "continent": "North America", "country": "United States", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://feeds.washingtonpost.com/rss/world"},
    {"name": "The Wall Street Journal", "continent": "North America", "country": "United States", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml"},
    {"name": "CNN", "continent": "North America", "country": "United States", "category": "ALL", "feed_type": "PUBLISHER", "url": "http://rss.cnn.com/rss/edition_world.rss"},
    {"name": "Fox News", "continent": "North America", "country": "United States", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://moxie.foxnews.com/google-publisher/world.xml"},
    {"name": "CBC News", "continent": "North America", "country": "Canada", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://www.cbc.ca/cmlink/rss-world"},
    {"name": "El Universal", "continent": "North America", "country": "Mexico", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://www.eluniversal.com.mx/rss/mundo.xml"},

    # --- SOUTH AMERICA ---
    {"name": "Folha de S.Paulo", "continent": "South America", "country": "Brazil", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://feeds.folha.uol.com.br/mundo/rss091.xml"},
    {"name": "Clarín", "continent": "South America", "country": "Argentina", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://www.clarin.com/rss/mundo/"},
    {"name": "El Tiempo", "continent": "South America", "country": "Colombia", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://www.eltiempo.com/rss/mundo.xml"},

    # --- EUROPE ---
    {"name": "BBC News", "continent": "Europe", "country": "United Kingdom", "category": "ALL", "feed_type": "PUBLISHER", "url": "http://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "The Guardian", "continent": "Europe", "country": "United Kingdom", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://www.theguardian.com/world/rss"},
    {"name": "Le Monde", "continent": "Europe", "country": "France", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://www.lemonde.fr/international/rss_full.xml"},
    {"name": "France 24", "continent": "Europe", "country": "France", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://www.france24.com/fr/rss"},
    {"name": "Der Spiegel", "continent": "Europe", "country": "Germany", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://www.spiegel.de/international/index.rss"},
    {"name": "Deutsche Welle", "continent": "Europe", "country": "Germany", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://rss.dw.com/rdf/rss-en-world"},
    {"name": "El País", "continent": "Europe", "country": "Spain", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada"},
    {"name": "RT (Russia Today)", "continent": "Europe", "country": "Russia", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://www.rt.com/rss/news/"},
    {"name": "TASS", "continent": "Europe", "country": "Russia", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://tass.com/rss/v2.xml"},

    # --- ASIA ---
    {"name": "South China Morning Post", "continent": "Asia", "country": "China", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://www.scmp.com/rss/91/feed"},
    {"name": "The Times of India", "continent": "Asia", "country": "India", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms"},
    {"name": "Nikkei Asia", "continent": "Asia", "country": "Japan", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://asia.nikkei.com/rss/feed/nar"},
    {"name": "Dawn", "continent": "Asia", "country": "Pakistan", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://www.dawn.com/feeds/world/"},
    {"name": "The Straits Times", "continent": "Asia", "country": "Singapore", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://www.straitstimes.com/news/world/rss.xml"},

    # --- OCEANIA ---
    {"name": "ABC News Australia", "continent": "Oceania", "country": "Australia", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://www.abc.net.au/news/feed/51120/rss.xml"},
    {"name": "NZ Herald", "continent": "Oceania", "country": "New Zealand", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://www.nzherald.co.nz/arc/outboundfeeds/rss/section/world/?outputType=xml"},

    # --- GLOBAL & REDDIT HUBS ---
    {"name": "Reuters", "continent": "Global", "country": "Global", "category": "ALL", "feed_type": "PUBLISHER", "url": "https://news.google.com/rss/search?q=site:reuters.com+when:24h&hl=en-US&gl=US&ceid=US:en"},
    {"name": "The Economist", "continent": "Global", "country": "Global", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://www.economist.com/international/rss.xml"},
    {"name": "Politico", "continent": "Global", "country": "Global", "category": "GENERAL", "feed_type": "PUBLISHER", "url": "https://rss.politico.com/politics-news.xml"},
    {"name": "r/UkrainianConflict", "continent": "Europe", "country": "Ukraine", "category": "RED", "feed_type": "SOCIAL", "url": "https://www.reddit.com/r/UkrainianConflict/new.rss"},
    {"name": "r/Geopolitics", "continent": "Global", "country": "Global", "category": "ALL", "feed_type": "SOCIAL", "url": "https://www.reddit.com/r/geopolitics/new.rss"}
]

# ==============================================================================
# JOSIAH'S OFFICIAL DIPLOMATIC & NEWS DESK HANDLES
# ==============================================================================
SOCIAL_CATALOG = [
    # US Officials
    {"handle": "@POTUS", "continent": "North America", "country": "United States", "category": "ALL"},
    {"handle": "@VP", "continent": "North America", "country": "United States", "category": "ALL"},
    {"handle": "@SecRubio", "continent": "North America", "country": "United States", "category": "ALL"},
    {"handle": "@marcorubio", "continent": "North America", "country": "United States", "category": "ALL"},
    {"handle": "@StateDept", "continent": "North America", "country": "United States", "category": "ALL"},
    
    # Africa Leaders & Ministries
    {"handle": "@WilliamsRuto", "continent": "Africa", "country": "Kenya", "category": "GENERAL"},
    {"handle": "@PaulKagame", "continent": "Africa", "country": "Rwanda", "category": "GENERAL"},
    {"handle": "@UrugwiroVillage", "continent": "Africa", "country": "Rwanda", "category": "GENERAL"},
    {"handle": "@CyrilRamaphosa", "continent": "Africa", "country": "South Africa", "category": "GENERAL"},
    {"handle": "@officialABAT", "continent": "Africa", "country": "Nigeria", "category": "GENERAL"},
    {"handle": "@NGRPresident", "continent": "Africa", "country": "Nigeria", "category": "GENERAL"},
    {"handle": "@AlsisiOfficial", "continent": "Africa", "country": "Egypt", "category": "GENERAL"},
    {"handle": "@MFAEthiopia", "continent": "Africa", "country": "Ethiopia", "category": "GENERAL"},
    {"handle": "@MusaliaMudavadi", "continent": "Africa", "country": "Kenya", "category": "GENERAL"},
    {"handle": "@ForeignOfficeKE", "continent": "Africa", "country": "Kenya", "category": "GENERAL"},
    {"handle": "@RonaldLamola", "continent": "Africa", "country": "South Africa", "category": "GENERAL"},
    {"handle": "@DIRCO_ZA", "continent": "Africa", "country": "South Africa", "category": "GENERAL"},
    {"handle": "@NigeriaMFA", "continent": "Africa", "country": "Nigeria", "category": "GENERAL"},
    {"handle": "@MFAEgOfficial", "continent": "Africa", "country": "Egypt", "category": "GENERAL"},
    
    # Europe Leaders & Ministries
    {"handle": "@EmmanuelMacron", "continent": "Europe", "country": "France", "category": "GENERAL"},
    {"handle": "@GiorgiaMeloni", "continent": "Europe", "country": "Italy", "category": "GENERAL"},
    {"handle": "@sanchezcastejon", "continent": "Europe", "country": "Spain", "category": "GENERAL"},
    {"handle": "@donaldtusk", "continent": "Europe", "country": "Poland", "category": "GENERAL"},
    {"handle": "@_FriedrichMerz", "continent": "Europe", "country": "Germany", "category": "GENERAL"},
    {"handle": "@bundeskanzler", "continent": "Europe", "country": "Germany", "category": "GENERAL"},
    {"handle": "@FCDOGovUK", "continent": "Europe", "country": "United Kingdom", "category": "GENERAL"},

    # Middle East Leaders & Ministries
    {"handle": "@KingSalman", "continent": "Middle East", "country": "Saudi Arabia", "category": "RED"},
    {"handle": "@MohamedBinZayed", "continent": "Middle East", "country": "UAE", "category": "RED"},
    {"handle": "@HHShkMohd", "continent": "Middle East", "country": "UAE", "category": "RED"},
    {"handle": "@TamimBinHamad", "continent": "Middle East", "country": "Qatar", "category": "RED"},
    {"handle": "@RTErdogan", "continent": "Middle East", "country": "Turkey", "category": "RED"},
    {"handle": "@netanyahu", "continent": "Middle East", "country": "Israel", "category": "RED"},
    {"handle": "@FaisalbinFarhan", "continent": "Middle East", "country": "Saudi Arabia", "category": "RED"},
    {"handle": "@KSAMOFA", "continent": "Middle East", "country": "Saudi Arabia", "category": "RED"},
    {"handle": "@mofauae", "continent": "Middle East", "country": "UAE", "category": "RED"},
    {"handle": "@MofaQatar_EN", "continent": "Middle East", "country": "Qatar", "category": "RED"},
    {"handle": "@IsraelMFA", "continent": "Middle East", "country": "Israel", "category": "RED"},
    {"handle": "@araghchi", "continent": "Middle East", "country": "Iran", "category": "RED"},
    {"handle": "@IRIMFA_EN", "continent": "Middle East", "country": "Iran", "category": "RED"},

    # Breaking News Social Desks
    {"handle": "@BBCBreaking", "continent": "Europe", "country": "United Kingdom", "category": "ALL"},
    {"handle": "@ReutersWorld", "continent": "Global", "country": "Global", "category": "ALL"},
    {"handle": "@CNNbrk", "continent": "North America", "country": "United States", "category": "ALL"}
]

# ==============================================================================
# DATABASE LAYER WITH AUTO-REPAIR
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
        conn.close()
    except Exception as e:
        logger.error(f"Database init error: {e}")

# ==============================================================================
# UNICODE SCRIPT DETECTOR & MEDIA EXTRACTOR
# ==============================================================================
def detect_script_language(text: str) -> str:
    if re.search(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]', text): return "Arabic"
    if re.search(r'[\u1200-\u137F\u1380-\u139F\u2D80-\u2DDF\uAB00-\uAB2F]', text): return "Amharic"
    if re.search(r'[\u0400-\u04FF]', text): return "Russian"
    if re.search(r'[\u4E00-\u9FFF]', text): return "Mandarin"
    return "English"

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

def analyze_multilingual_threat(title: str):
    t_lower = title.lower()
    matched_keyword = ""
    heat_score = 0
    detected_lang = detect_script_language(title)

    for lang, dicts in MULTILINGUAL_LEXICON.items():
        for kw in dicts["critical"]:
            if re.search(r'\b' + re.escape(kw.lower()) + r'\b', t_lower):
                heat_score += 3
                if not matched_keyword: matched_keyword = kw; detected_lang = lang
        for kw in dicts["elevated"]:
            if re.search(r'\b' + re.escape(kw.lower()) + r'\b', t_lower):
                heat_score += 1.5
                if not matched_keyword: matched_keyword = kw; detected_lang = lang
        for kw in dicts["general"]:
            if re.search(r'\b' + re.escape(kw.lower()) + r'\b', t_lower):
                heat_score += 1
                if not matched_keyword: matched_keyword = kw; detected_lang = lang

    if heat_score >= 3.0: level = "CRITICAL"
    elif heat_score >= 1.0: level = "ELEVATED"
    else: level = "INFORMATIONAL"

    return level, (f"Matched: '{matched_keyword}'" if matched_keyword else ""), detected_lang

def save_items_bulk(items):
    """Saves rows and updates existing records with the latest language and threat level."""
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
                        threat, kw_badge, lang = analyze_multilingual_threat(title)
                        items.append({'title': title, 'link': link, 'source': name, 'handle': 'N/A', 'continent': continent, 'country': country, 'category': category, 'feed_type': feed_type, 'published_date': pub_date, 'keyword': kw_badge, 'threat_level': threat, 'language': lang, 'thumbnail': thumb})
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
                                items.append({'title': title, 'link': link, 'source': name, 'handle': 'N/A', 'continent': continent, 'country': country, 'category': category, 'feed_type': feed_type, 'published_date': pub_date, 'keyword': kw_badge, 'threat_level': threat, 'language': lang, 'thumbnail': thumb})
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
                        if hasattr(entry, 'published_parsed') and entry.published_parsed: pub_date = time.strftime("%Y-%m-%d %H:%M:%S", entry.published_parsed)
                        else: pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    except: pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    if clean_title and link:
                        threat, kw_badge, lang = analyze_multilingual_threat(clean_title)
                        items.append({'title': clean_title, 'link': link, 'source': 'X (Twitter)', 'handle': handle, 'continent': continent, 'country': country, 'category': category, 'feed_type': 'SOCIAL', 'published_date': pub_date, 'keyword': kw_badge or f"Account: {handle}", 'threat_level': threat, 'language': lang, 'thumbnail': thumb})
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
    semaphore = asyncio.Semaphore(50)
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
    
    if category.upper() != "ALL": query += " AND category = %s"; params.append(category.upper())
    if publisher != "All": query += " AND source = %s"; params.append(publisher)
    if handle != "All": query += " AND handle = %s"; params.append(handle)
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
        if not r.get('language') or r.get('language') == 'English': r['language'] = detect_script_language(r.get('title', ''))
        results.append(r)
    return results

@app.get("/api/meta/catalog")
def get_catalog_metadata():
    hierarchy = {}
    publishers_set = set()
    handles_set = set()
    
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
