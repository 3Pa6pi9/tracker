from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from deep_translator import GoogleTranslator
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

app = FastAPI(title="Global Geopolitical Command Center", version="42.0 - Final Production Core")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres.afdzhavjcejvmnrwyaid:5wNGFgK3H5q3CwUZ@aws-0-eu-west-2.pooler.supabase.com:6543/postgres"
)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# ==============================================================================
# TIER 1 PRIORITY ALERT KEYWORDS
# ==============================================================================
PRIORITY_ALERT_KEYWORDS = [
    "muslim brotherhood", 
    "الإخوان المسلمين", 
    "cair", 
    "council on american-islamic relations"
]

# ==============================================================================
# EXPANDED 14-LANGUAGE LEXICON
# ==============================================================================
MULTILINGUAL_LEXICON = {
    "English": {
        "critical": ["war", "strike", "attack", "missile", "assassination", "conflict", "explosion", "invasion", "airstrike", "casualty", "nuclear", "bombing", "artillery", "hostage", "idf", "offensive", "drone strike", "troops", "frontline", "combat", "terror", "migration crisis", "refugee", "border security", "illegal immigration", "sudan", "somalia", "iran", "ukraine", "russia", "demonstration", "protest", "parliament", "counter-terrorism", "middle east"],
        "elevated": ["sanctions", "tension", "warning", "ban", "dispute", "standoff", "threat", "cyberattack", "unrest", "crisis", "drill", "deployment", "ceasefire", "embargo", "coup", "blockade", "riot", "evacuation", "rebel"],
        "general": ["bilateral relations", "state visit", "diplomatic ties", "diplomatic mission", "foreign envoy", "ambassador meeting", "foreign ministry", "peace talks", "trade agreement", "foreign investment", "economic partnership", "tariff", "trade deal", "mou signed", "memorandum of understanding", "security partnership", "defense pact", "military agreement", "joint military exercise", "security cooperation", "defense treaty", "treaty signed", "international summit", "global governance", "un resolution", "international convention", "multilateral agreement", "geopolitical shift", "resource diplomacy", "foreign influence", "strategic alliance", "international relations", "diplomatic shift"]
    },
    "Arabic": {
        "critical": ["حرب", "غارة", "هجوم", "صاروخ", "اغتيال", "نزاع", "انفجار", "غزو", "ضربة جوية", "قصف", "قتلى", "نووي", "شهداء", "مواجهات مسلحة", "مسيرة", "جيش", "اشتباكات", "استهداف", "طيران", "حماس", "حزب الله"],
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
    "Italian": {
        "critical": ["guerra", "attacco", "missile", "assassinio", "conflitto", "esplosione", "invasione", "ostaggio", "terrorismo"],
        "elevated": ["sanzioni", "protesta", "tensione", "crisi", "sciopero", "ribelle"],
        "general": ["diplomazia", "ambasciatore", "accordo", "governo", "trattato"]
    },
    "Portuguese": {
        "critical": ["guerra", "ataque", "míssil", "assassinato", "conflito", "explosão", "invasão", "refém", "terrorismo"],
        "elevated": ["sanções", "protesto", "tensão", "crise", "rebelde", "golpe"],
        "general": ["diplomacia", "embaixador", "acordo", "governo", "tratado"]
    },
    "Hebrew": {
        "critical": ["מלחמה", "תקיפה", "טיל", "התנקשות", "סכסוך", "פיצוץ", "פלישה", "חטוף", "טרור"],
        "elevated": ["סנקציות", "מחאה", "מתיחות", "משבר"],
        "general": ["דיפלומטיה", "שגריר", "הסכם", "ממשלה"]
    },
    "Bosnian": {
        "critical": ["rat", "napad", "projektil", "atentat", "sukob", "eksplozija", "invazija", "talac", "terorizam"],
        "elevated": ["sankcije", "protest", "tenzija", "kriza", "pobuna"],
        "general": ["diplomatija", "ambasador", "sporazum", "vlada"]
    },
    "Danish": {
        "critical": ["krig", "angreb", "missil", "attentat", "konflikt", "eksplosion", "invasion", "gidsel", "terrorisme"],
        "elevated": ["sanktioner", "protest", "spænding", "krise", "oprør"],
        "general": ["diplomati", "ambassadør", "aftale", "regering"]
    },
    "Mandarin": {
        "critical": ["战争", "罢工", "袭击", "导弹", "暗杀", "冲突", "爆炸", "入侵", "空袭", "伤亡", "核武器", "轰炸", "炮兵", "人质", "攻势"],
        "elevated": ["制裁", "抗议", "紧张局势", "警告", "禁令", "争端", "威胁", "网络攻击", "动乱", "危机", "部署", "政变", "停火"],
        "general": ["外交", "国事访问", "大使", "贸易协定", "峰会", "条约", "外交政策", "选举"]
    }
}

# ==============================================================================
# LANGUAGE CODES FOR AUTO-TRANSLATION & DEEP SEARCH
# ==============================================================================
TRANSLATION_CODES = {
    "Arabic": "ar", "Amharic": "am", "French": "fr", "Spanish": "es",
    "Russian": "ru", "Italian": "it", "Portuguese": "pt", "Hebrew": "iw",
    "Bosnian": "bs", "Danish": "da", "Mandarin": "zh-CN"
}

# ==============================================================================
# MASTER CATALOG
# ==============================================================================
MASTER_CATALOG = [
    {"name": "Joy Online", "continent": "Africa", "country": "Ghana", "category": "ALL", "feed_type": "PUBLISHER", "language": "English", "url": "https://www.myjoyonline.com/feed/"},
    {"name": "GhanaWeb", "continent": "Africa", "country": "Ghana", "category": "ALL", "feed_type": "PUBLISHER", "language": "English", "url": "https://news.google.com/rss/search?q=site:ghanaweb.com&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Citi Newsroom", "continent": "Africa", "country": "Ghana", "category": "ALL", "feed_type": "PUBLISHER", "language": "English", "url": "https://citinewsroom.com/feed/"},
    {"name": "Les Dépêches de Brazzaville", "continent": "Africa", "country": "Republic of the Congo", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "French", "url": "https://news.google.com/rss/search?q=site:adiac-congo.com&hl=fr&gl=FR&ceid=FR:fr"},
    {"name": "Vox Congo", "continent": "Africa", "country": "Republic of the Congo", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "French", "url": "https://news.google.com/rss/search?q=site:vox.cg&hl=fr&gl=FR&ceid=FR:fr"},
    {"name": "Corbeau News Centrafrique", "continent": "Africa", "country": "Central African Republic", "category": "RED", "feed_type": "PUBLISHER", "language": "French", "url": "https://corbeaunews-centrafrique.org/feed/"},
    {"name": "Ndeke Luka", "continent": "Africa", "country": "Central African Republic", "category": "RED", "feed_type": "PUBLISHER", "language": "French", "url": "https://news.google.com/rss/search?q=site:radiondekeluka.org&hl=fr&gl=FR&ceid=FR:fr"},
    {"name": "L'Express Mauritius", "continent": "Africa", "country": "Mauritius", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "French", "url": "https://lexpress.mu/feed"},
    {"name": "O Democrata", "continent": "Africa", "country": "Guinea-Bissau", "category": "ALL", "feed_type": "PUBLISHER", "language": "Portuguese", "url": "https://news.google.com/rss/search?q=site:odemocratagb.com&hl=pt-PT&gl=PT&ceid=PT:pt"},
    {"name": "Guineematin", "continent": "Africa", "country": "Guinea", "category": "ALL", "feed_type": "PUBLISHER", "language": "French", "url": "https://guineematin.com/feed/"},
    {"name": "Hiiraan Online", "continent": "Africa", "country": "Somalia", "category": "RED", "feed_type": "PUBLISHER", "language": "English", "url": "https://news.google.com/rss/search?q=site:hiiraan.com&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Garowe Online", "continent": "Africa", "country": "Somalia", "category": "RED", "feed_type": "PUBLISHER", "language": "English", "url": "https://www.garoweonline.com/en/rss/feed"},
    {"name": "Sudan Tribune", "continent": "Africa", "country": "Sudan", "category": "RED", "feed_type": "PUBLISHER", "language": "English", "url": "https://sudantribune.com/feed/"},
    {"name": "Al-Ahram Online", "continent": "Africa", "country": "Egypt", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "English", "url": "https://english.ahram.org.eg/RSS/All.aspx"},
    {"name": "Mada Masr", "continent": "Africa", "country": "Egypt", "category": "RED", "feed_type": "PUBLISHER", "language": "English", "url": "https://www.madamasr.com/en/feed/"},
    {"name": "Premium Times", "continent": "Africa", "country": "Nigeria", "category": "ALL", "feed_type": "PUBLISHER", "language": "English", "url": "https://www.premiumtimesng.com/feed"},
    {"name": "Borkena", "continent": "Africa", "country": "Ethiopia", "category": "ALL", "feed_type": "PUBLISHER", "language": "English", "url": "https://borkena.com/feed/"},
    {"name": "BBC Amharic", "continent": "Africa", "country": "Ethiopia", "category": "ALL", "feed_type": "PUBLISHER", "language": "Amharic", "url": "https://news.google.com/rss/search?q=site:bbc.com/amharic&hl=am&gl=ET&ceid=ET:am"},
    {"name": "Fana Broadcasting", "continent": "Africa", "country": "Ethiopia", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "Amharic", "url": "https://news.google.com/rss/search?q=site:fanabc.com&hl=am&gl=ET&ceid=ET:am"},

    {"name": "ANSA", "continent": "Europe", "country": "Italy", "category": "ALL", "feed_type": "PUBLISHER", "language": "Italian", "url": "https://news.google.com/rss/search?q=site:ansa.it&hl=it&gl=IT&ceid=IT:it"},
    {"name": "B92", "continent": "Europe", "country": "Serbia", "category": "ALL", "feed_type": "PUBLISHER", "language": "Bosnian", "url": "https://news.google.com/rss/search?q=site:b92.net&hl=sr&gl=RS&ceid=RS:sr"},
    {"name": "Index.hu", "continent": "Europe", "country": "Hungary", "category": "ALL", "feed_type": "PUBLISHER", "language": "English", "url": "https://index.hu/24ora/rss/"},
    {"name": "TASS", "continent": "Europe", "country": "Russia", "category": "ALL", "feed_type": "PUBLISHER", "language": "Russian", "url": "https://tass.com/rss/v2.xml"},
    {"name": "Belta", "continent": "Europe", "country": "Belarus", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "Russian", "url": "https://news.google.com/rss/search?q=site:belta.by&hl=ru&gl=RU&ceid=RU:ru"},
    {"name": "Agerpres", "continent": "Europe", "country": "Romania", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "English", "url": "https://news.google.com/rss/search?q=site:agerpres.ro&hl=ro&gl=RO&ceid=RO:ro"},
    {"name": "HRT", "continent": "Europe", "country": "Croatia", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "Bosnian", "url": "https://news.google.com/rss/search?q=site:hrt.hr&hl=hr&gl=HR&ceid=HR:hr"},
    {"name": "Kathimerini", "continent": "Europe", "country": "Greece", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "English", "url": "https://www.kathimerini.gr/world/rss"},
    {"name": "RTK", "continent": "Europe", "country": "Kosovo", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "English", "url": "https://news.google.com/rss/search?q=site:rtklive.com&hl=sq&gl=AL&ceid=AL:sq"},
    
    {"name": "MEMRI", "continent": "Middle East", "country": "Global", "category": "ALL", "feed_type": "PUBLISHER", "language": "English", "url": "https://www.memri.org/rss/english"},
    {"name": "SABA News", "continent": "Middle East", "country": "Yemen", "category": "RED", "feed_type": "PUBLISHER", "language": "English", "url": "https://www.saba.ye/en/rss.xml"},
    {"name": "Al Masirah", "continent": "Middle East", "country": "Yemen", "category": "RED", "feed_type": "PUBLISHER", "language": "Arabic", "url": "https://news.google.com/rss/search?q=site:almasirah.net.ye&hl=ar&gl=YE&ceid=YE:ar"},
    {"name": "IRNA", "continent": "Middle East", "country": "Iran", "category": "RED", "feed_type": "PUBLISHER", "language": "English", "url": "https://en.irna.ir/rss"},
    {"name": "Tehran Times", "continent": "Middle East", "country": "Iran", "category": "RED", "feed_type": "PUBLISHER", "language": "English", "url": "https://www.tehrantimes.com/rss"},
    {"name": "Shafaq News", "continent": "Middle East", "country": "Iraq", "category": "RED", "feed_type": "PUBLISHER", "language": "English", "url": "https://shafaq.com/en/rss"},
    {"name": "Rudaw", "continent": "Middle East", "country": "Iraq", "category": "RED", "feed_type": "PUBLISHER", "language": "English", "url": "https://www.rudaw.net/english/rss"},
    {"name": "SANA", "continent": "Middle East", "country": "Syria", "category": "RED", "feed_type": "PUBLISHER", "language": "Arabic", "url": "https://news.google.com/rss/search?q=site:sana.sy&hl=ar&gl=SY&ceid=SY:ar"},
    {"name": "NNA Lebanon", "continent": "Middle East", "country": "Lebanon", "category": "RED", "feed_type": "PUBLISHER", "language": "English", "url": "https://news.google.com/rss/search?q=site:nna-leb.gov.lb&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Arab News", "continent": "Middle East", "country": "Saudi Arabia", "category": "RED", "feed_type": "PUBLISHER", "language": "English", "url": "https://www.arabnews.com/cat/1/rss.xml"},

    {"name": "The New York Times", "continent": "North America", "country": "United States", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "English", "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"},
    {"name": "Reuters", "continent": "Global", "country": "Global", "category": "ALL", "feed_type": "PUBLISHER", "language": "English", "url": "https://news.google.com/rss/search?q=site:reuters.com+when:24h&hl=en-US&gl=US&ceid=US:en"},
    {"name": "BBC News", "continent": "Europe", "country": "United Kingdom", "category": "ALL", "feed_type": "PUBLISHER", "language": "English", "url": "http://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "Le Monde", "continent": "Europe", "country": "France", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "French", "url": "https://www.lemonde.fr/international/rss_full.xml"},
    {"name": "El País", "continent": "Europe", "country": "Spain", "category": "GENERAL", "feed_type": "PUBLISHER", "language": "Spanish", "url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada"},

    {"name": "Global Intel: Muslim Brotherhood", "continent": "Global", "country": "Global", "category": "RED", "feed_type": "PUBLISHER", "language": "English", "url": "https://news.google.com/rss/search?q=%22Muslim+Brotherhood%22+when:3d&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Global Intel: الإخوان المسلمين", "continent": "Middle East", "country": "Egypt", "category": "RED", "feed_type": "PUBLISHER", "language": "Arabic", "url": "https://news.google.com/rss/search?q=%D8%A7%D9%84%D8%A5%D8%AE%D9%88%D8%A7%D9%86+%D8%A7%D9%84%D9%85%D8%B3%D9%84%D9%85%D9%8A%D9%86+when:3d&hl=ar&gl=EG&ceid=EG:ar"},
    {"name": "Global Intel: CAIR", "continent": "North America", "country": "United States", "category": "RED", "feed_type": "PUBLISHER", "language": "English", "url": "https://news.google.com/rss/search?q=%22Council+on+American-Islamic+Relations%22+OR+%22CAIR%22+when:3d&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Global Intel: Sudan Conflict", "continent": "Africa", "country": "Sudan", "category": "RED", "feed_type": "PUBLISHER", "language": "English", "url": "https://news.google.com/rss/search?q=Sudan+(SAF+OR+RSF+OR+clashes)+when:3d&hl=en-US&gl=US&ceid=US:en"}
]

SOCIAL_CATALOG = [
    {"handle": "@POTUS", "continent": "North America", "country": "United States", "category": "ALL", "language": "English"},
    {"handle": "@VP", "continent": "North America", "country": "United States", "category": "ALL", "language": "English"},
    {"handle": "@SecRubio", "continent": "North America", "country": "United States", "category": "ALL", "language": "English"},
    {"handle": "@marcorubio", "continent": "North America", "country": "United States", "category": "ALL", "language": "English"},
    {"handle": "@StateDept", "continent": "North America", "country": "United States", "category": "ALL", "language": "English"},
    {"handle": "@WilliamsRuto", "continent": "Africa", "country": "Kenya", "category": "GENERAL", "language": "English"},
    {"handle": "@PaulKagame", "continent": "Africa", "country": "Rwanda", "category": "GENERAL", "language": "English"},
    {"handle": "@CyrilRamaphosa", "continent": "Africa", "country": "South Africa", "category": "GENERAL", "language": "English"},
    {"handle": "@officialABAT", "continent": "Africa", "country": "Nigeria", "category": "GENERAL", "language": "English"},
    {"handle": "@AlsisiOfficial", "continent": "Africa", "country": "Egypt", "category": "GENERAL", "language": "Arabic"},
    {"handle": "@MFAEthiopia", "continent": "Africa", "country": "Ethiopia", "category": "GENERAL", "language": "English"},
    {"handle": "@MusaliaMudavadi", "continent": "Africa", "country": "Kenya", "category": "GENERAL", "language": "English"},
    {"handle": "@ForeignOfficeKE", "continent": "Africa", "country": "Kenya", "category": "GENERAL", "language": "English"},
    {"handle": "@RonaldLamola", "continent": "Africa", "country": "South Africa", "category": "GENERAL", "language": "English"},
    {"handle": "@DIRCO_ZA", "continent": "Africa", "country": "South Africa", "category": "GENERAL", "language": "English"},
    {"handle": "@NigeriaMFA", "continent": "Africa", "country": "Nigeria", "category": "GENERAL", "language": "English"},
    {"handle": "@MFAEgOfficial", "continent": "Africa", "country": "Egypt", "category": "GENERAL", "language": "Arabic"},
    {"handle": "@MfaEgypt", "continent": "Africa", "country": "Egypt", "category": "GENERAL", "language": "Arabic"},
    {"handle": "@EmmanuelMacron", "continent": "Europe", "country": "France", "category": "GENERAL", "language": "French"},
    {"handle": "@GiorgiaMeloni", "continent": "Europe", "country": "Italy", "category": "GENERAL", "language": "Italian"},
    {"handle": "@sanchezcastejon", "continent": "Europe", "country": "Spain", "category": "GENERAL", "language": "Spanish"},
    {"handle": "@donaldtusk", "continent": "Europe", "country": "Poland", "category": "GENERAL", "language": "English"},
    {"handle": "@_FriedrichMerz", "continent": "Europe", "country": "Germany", "category": "GENERAL", "language": "German"},
    {"handle": "@bundeskanzler", "continent": "Europe", "country": "Germany", "category": "GENERAL", "language": "German"},
    {"handle": "@AussenMinDE", "continent": "Europe", "country": "Germany", "category": "GENERAL", "language": "German"},
    {"handle": "@AuswaertigesAmt", "continent": "Europe", "country": "Germany", "category": "GENERAL", "language": "German"},
    {"handle": "@GermanyDiplo", "continent": "Europe", "country": "Germany", "category": "GENERAL", "language": "English"},
    {"handle": "@Ed_Miliband", "continent": "Europe", "country": "United Kingdom", "category": "GENERAL", "language": "English"},
    {"handle": "@FCDOGovUK", "continent": "Europe", "country": "United Kingdom", "category": "GENERAL", "language": "English"},
    {"handle": "@SabaNet", "continent": "Middle East", "country": "Yemen", "category": "RED", "language": "Arabic"},
    {"handle": "@KingSalman", "continent": "Middle East", "country": "Saudi Arabia", "category": "RED", "language": "Arabic"},
    {"handle": "@MohamedBinZayed", "continent": "Middle East", "country": "UAE", "category": "RED", "language": "Arabic"},
    {"handle": "@HHShkMohd", "continent": "Middle East", "country": "UAE", "category": "RED", "language": "Arabic"},
    {"handle": "@TamimBinHamad", "continent": "Middle East", "country": "Qatar", "category": "RED", "language": "Arabic"},
    {"handle": "@RTErdogan", "continent": "Middle East", "country": "Turkey", "category": "RED", "language": "Turkish"},
    {"handle": "@netanyahu", "continent": "Middle East", "country": "Israel", "category": "RED", "language": "English"},
    {"handle": "@FaisalbinFarhan", "continent": "Middle East", "country": "Saudi Arabia", "category": "RED", "language": "Arabic"},
    {"handle": "@KSAMOFA", "continent": "Middle East", "country": "Saudi Arabia", "category": "RED", "language": "Arabic"},
    {"handle": "@KSAmofaEN", "continent": "Middle East", "country": "Saudi Arabia", "category": "RED", "language": "English"},
    {"handle": "@ABZayed", "continent": "Middle East", "country": "UAE", "category": "RED", "language": "Arabic"},
    {"handle": "@mofauae", "continent": "Middle East", "country": "UAE", "category": "RED", "language": "Arabic"},
    {"handle": "@OFMUAE", "continent": "Middle East", "country": "UAE", "category": "RED", "language": "English"},
    {"handle": "@MBA_AlThani_", "continent": "Middle East", "country": "Qatar", "category": "RED", "language": "Arabic"},
    {"handle": "@MofaQatar_EN", "continent": "Middle East", "country": "Qatar", "category": "RED", "language": "English"},
    {"handle": "@IsraelMFA", "continent": "Middle East", "country": "Israel", "category": "RED", "language": "English"},
    {"handle": "@araghchi", "continent": "Middle East", "country": "Iran", "category": "RED", "language": "Persian"},
    {"handle": "@IRIMFA_EN", "continent": "Middle East", "country": "Iran", "category": "RED", "language": "English"},
    {"handle": "@MFATurkiye", "continent": "Middle East", "country": "Turkey", "category": "RED", "language": "Turkish"}
]

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
        if "continent" not in existing_cols: c.execute("ALTER TABLE news ADD COLUMN continent TEXT DEFAULT 'Global'")
        if "country" not in existing_cols: c.execute("ALTER TABLE news ADD COLUMN country TEXT DEFAULT 'Global'")
        if "language" not in existing_cols: c.execute("ALTER TABLE news ADD COLUMN language TEXT DEFAULT 'English'")
        if "thumbnail" not in existing_cols: c.execute("ALTER TABLE news ADD COLUMN thumbnail TEXT DEFAULT ''")
        if "feed_type" not in existing_cols: c.execute("ALTER TABLE news ADD COLUMN feed_type TEXT DEFAULT 'PUBLISHER'")
        if "keyword" not in existing_cols: c.execute("ALTER TABLE news ADD COLUMN keyword TEXT DEFAULT ''")
        if "threat_level" not in existing_cols: c.execute("ALTER TABLE news ADD COLUMN threat_level TEXT DEFAULT 'INFORMATIONAL'")
        
        c.execute('CREATE INDEX IF NOT EXISTS idx_cat_src_cont_lang ON news (category, source, feed_type, language, continent, published_date);')
        c.execute("DELETE FROM news WHERE source ILIKE '%Al Jazeera%' OR handle ILIKE '%AJBreaking%'")
        
        for pub in MASTER_CATALOG:
            c.execute("UPDATE news SET language = %s, continent = %s, country = %s, category = %s, feed_type = %s WHERE source = %s", 
                      (pub["language"], pub["continent"], pub["country"], pub["category"], pub["feed_type"], pub["name"]))
        for soc in SOCIAL_CATALOG:
            c.execute("UPDATE news SET language = %s, continent = %s, country = %s, category = %s, feed_type = %s WHERE handle = %s", 
                      (soc["language"], soc["continent"], soc["country"], soc["category"], "SOCIAL", soc["handle"]))
                
        conn.close()
    except Exception as e:
        logger.error(f"Database init error: {e}")

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
    
    is_priority_alert = any(kw in t_lower for kw in PRIORITY_ALERT_KEYWORDS)
    if is_priority_alert:
        return "PRIORITY_1", "⚠️ TIER 1 MATCH", feed_lang, True

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

    level = "CRITICAL" if heat_score >= 3.0 else ("ELEVATED" if heat_score >= 1.0 else "INFORMATIONAL")
    return level, (f"Matched: '{matched_keyword}'" if matched_keyword else ""), feed_lang, False

def save_items_bulk(items):
    if not items: return 0, False, None
    conn = get_db_connection()
    c = conn.cursor()
    added = 0
    priority_found = False
    priority_title = None
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
                    feed_type = EXCLUDED.feed_type,
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
            if c.rowcount > 0: 
                added += 1
                if item.get('is_priority_alert'):
                    priority_found = True
                    priority_title = item['title']
        except Exception:
            pass
    conn.close()
    return added, priority_found, priority_title

async def fetch_publisher_feed(client, semaphore, publisher, limit=50):
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
            response = await client.get(url, timeout=10.0, follow_redirects=True)
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
                    except: 
                        pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    if title and link:
                        threat, kw_badge, final_lang, is_priority = analyze_multilingual_threat(title, feed_lang)
                        items.append({
                            'title': title, 'link': link, 'source': name, 'handle': 'N/A', 
                            'continent': continent, 'country': country, 'category': category, 
                            'feed_type': feed_type, 'published_date': pub_date, 
                            'keyword': kw_badge, 'threat_level': threat, 
                            'language': final_lang, 'thumbnail': thumb, 'is_priority_alert': is_priority
                        })
        except Exception:
            pass
    return items

async def fetch_social_target(client, semaphore, target, limit=25):
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
                        if hasattr(entry, 'published_parsed') and entry.published_parsed: 
                            pub_date = time.strftime("%Y-%m-%d %H:%M:%S", entry.published_parsed)
                        else: 
                            pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    except: 
                        pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    if clean_title and link:
                        threat, kw_badge, final_lang, is_priority = analyze_multilingual_threat(clean_title, feed_lang)
                        items.append({
                            'title': clean_title, 'link': link, 'source': 'X (Twitter)', 'handle': handle, 
                            'continent': continent, 'country': country, 'category': category, 
                            'feed_type': 'SOCIAL', 'published_date': pub_date, 
                            'keyword': kw_badge or f"Account: {handle}", 
                            'threat_level': threat, 'language': final_lang, 'thumbnail': thumb, 'is_priority_alert': is_priority
                        })
        except Exception:
            pass
    return items

async def perform_live_on_demand_sweep(query_term: str, requested_lang: str = "All"):
    if not query_term or len(query_term.strip()) < 2: return
    
    search_query = query_term
    target_code = "en"
    
    if requested_lang != "All" and requested_lang in TRANSLATION_CODES:
        try:
            target_code = TRANSLATION_CODES[requested_lang]
            translated_q = GoogleTranslator(source='auto', target=target_code).translate(query_term)
            if translated_q: search_query = translated_q
        except Exception as e:
            logger.error(f"Translation failed in sweep: {e}")

    encoded_q = urllib.parse.quote(search_query.strip())
    search_url = f"https://news.google.com/rss/search?q={encoded_q}+when:7d&hl={target_code}"
    
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        try:
            res = await client.get(search_url, timeout=7.0, follow_redirects=True)
            if res.status_code == 200:
                feed = await asyncio.to_thread(feedparser.parse, res.content)
                items = []
                for entry in feed.entries[:35]:
                    title = getattr(entry, 'title', '').strip()
                    link = getattr(entry, 'link', '').strip()
                    source_name = entry.source.title if hasattr(entry, 'source') and hasattr(entry.source, 'title') else "Live Feed Sweep"
                    thumb = extract_thumbnail(entry)
                    try:
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            pub_date = time.strftime("%Y-%m-%d %H:%M:%S", entry.published_parsed)
                        else:
                            pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    if title and link:
                        saved_lang = requested_lang if requested_lang != "All" else "English"
                        threat, kw_badge, _, is_priority = analyze_multilingual_threat(title, saved_lang)
                        items.append({
                            'title': title, 'link': link, 'source': source_name, 'handle': 'N/A',
                            'continent': 'Global', 'country': 'Global', 'category': 'ALL',
                            'feed_type': 'PUBLISHER', 'published_date': pub_date,
                            'keyword': f"Live Match: {search_query}", 'threat_level': threat,
                            'language': saved_lang, 'thumbnail': thumb, 'is_priority_alert': is_priority
                        })
                await asyncio.to_thread(save_items_bulk, items)
        except Exception as e:
            logger.error(f"Live on-demand sweep error for query '{query_term}': {e}")

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
    semaphore = asyncio.Semaphore(20) 
    limits = httpx.Limits(max_keepalive_connections=80, max_connections=160)
    
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
        total_added, priority_found, priority_title = await run_fast_sweep()
        timestamp = datetime.now().strftime("%I:%M %p")
        await manager.broadcast(json.dumps({
            "event": "new_intel", 
            "count": total_added, 
            "silent": silent, 
            "time": timestamp,
            "priority_alert": priority_found,
            "alert_title": priority_title
        }))
    except Exception as e:
        logger.error(f"Sweep failure: {e}")
        await manager.broadcast(json.dumps({"event": "sync_error"}))
    finally:
        is_syncing = False

async def background_loop():
    while True:
        await asyncio.sleep(600)
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
    if os.path.exists(root_path): return FileResponse(root_path)
    raise HTTPException(status_code=404, detail="index.html not found")

@app.get("/api/ping")
def ping(): return {"status": "operational", "engine": "Telemetry Core 42.0"}

@app.get("/admin/health", response_class=HTMLResponse)
def admin_health_check():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT source, MAX(published_date) as last_seen, COUNT(*) as total_articles 
        FROM news 
        GROUP BY source 
        ORDER BY last_seen DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    total_sources = len(MASTER_CATALOG) + len(SOCIAL_CATALOG)
    
    rows_html = ""
    for r in rows:
        status_color = "text-emerald-400" if r["last_seen"] else "text-amber-400"
        status_text = "Healthy / Ingesting" if r["last_seen"] else "Awaiting Data"
        rows_html += f"""
            <tr class="border-b border-slate-800 hover:bg-slate-800/50 transition-colors">
                <td class="p-3 font-semibold text-slate-200">{r["source"]}</td>
                <td class="p-3 text-slate-400 font-mono text-xs">{r["last_seen"]}</td>
                <td class="p-3 text-indigo-300 font-mono">{r["total_articles"]}</td>
                <td class="p-3 font-bold {status_color} text-[10px] tracking-wider uppercase">{status_text}</td>
            </tr>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en" class="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>System Health • Intel Engine</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-[#030712] text-slate-300 font-sans p-8 selection:bg-indigo-600 selection:text-white">
        <div class="max-w-5xl mx-auto">
            <div class="flex items-center justify-between mb-8 border-b border-slate-800 pb-4">
                <div>
                    <h1 class="text-2xl font-black text-white tracking-wider flex items-center gap-3">
                        <span class="w-3 h-3 bg-emerald-500 rounded-full animate-pulse block"></span>
                        SYSTEM HEALTH & TELEMETRY
                    </h1>
                    <p class="text-slate-500 text-xs mt-1 font-mono">ENGINE STATUS: ONLINE & SCRAPING | TARGETS: {total_sources}</p>
                </div>
                <button onclick="window.location.href='/'" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-bold transition-all border border-slate-700 shadow-md">← Back to Dashboard</button>
            </div>
            
            <div class="bg-[#0f172a] rounded-xl border border-slate-800 overflow-hidden shadow-2xl">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="bg-slate-900/80 border-b border-slate-800 text-[10px] uppercase tracking-widest text-slate-500 font-bold">
                            <th class="p-4">Monitored Source</th>
                            <th class="p-4">Last Ingestion Time</th>
                            <th class="p-4">Total Indexed Records</th>
                            <th class="p-4">Status Node</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

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
    category: str = Query("ALL"), 
    feed_type: str = Query("ALL"),
    publisher: str = Query("All"), 
    handle: str = Query("All"),
    language: str = Query("All"), 
    continent: str = Query("All"), 
    country: str = Query("All"),
    time_filter: str = Query("all"), 
    start_date: str = Query(None), 
    end_date: str = Query(None), 
    q: str = Query(None), 
    exclude_uae_red: bool = Query(False),
    uae_bilateral: bool = Query(False),
    page: int = Query(1), 
    limit: int = Query(30)
):
    if q and page == 1:
        await perform_live_on_demand_sweep(q, language)

    offset = (page - 1) * limit
    conn = get_db_connection()
    cursor = conn.cursor()
    
    base_query = """
        WITH ranked_news AS (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY source ORDER BY published_date DESC) as source_rank
            FROM news
            WHERE 1=1
    """
    params = []
    
    if category.upper() != "ALL": base_query += " AND category = %s"; params.append(category.upper())
    if feed_type.upper() != "ALL": base_query += " AND feed_type = %s"; params.append(feed_type.upper())

    if publisher != "All" and handle != "All":
        base_query += " AND (source = %s OR handle = %s)"
        params.extend([publisher, handle])
    elif publisher != "All":
        base_query += " AND source = %s"
        params.append(publisher)
    elif handle != "All":
        base_query += " AND handle = %s"
        params.append(handle)
        
    if continent != "All": base_query += " AND continent = %s"; params.append(continent)
    if country != "All": base_query += " AND country = %s"; params.append(country)
    if language != "All": base_query += " AND language = %s"; params.append(language)
    
    if exclude_uae_red:
        base_query += " AND NOT (country = 'UAE' AND category = 'RED')"
        
    if uae_bilateral:
        base_query += " AND (country = 'UAE' OR title ILIKE '%%UAE%%' OR title ILIKE '%%Emirates%%') AND category = 'GENERAL'"

    if start_date or end_date:
        if start_date: base_query += " AND published_date >= %s::timestamp"; params.append(f"{start_date} 00:00:00")
        if end_date: base_query += " AND published_date <= %s::timestamp"; params.append(f"{end_date} 23:59:59")
    else:
        time_mappings = {"1h": "1 hour", "4h": "4 hours", "8h": "8 hours", "12h": "12 hours", "1d": "1 day", "3d": "3 days", "7d": "7 days", "14d": "14 days", "30d": "30 days"}
        if time_filter in time_mappings: base_query += f" AND published_date >= NOW() - INTERVAL '{time_mappings[time_filter]}'"

    if q:
        search_terms = [q]
        if language != "All" and language in TRANSLATION_CODES:
            try:
                target_code = TRANSLATION_CODES[language]
                translated_q = GoogleTranslator(source='auto', target=target_code).translate(q)
                if translated_q and translated_q.lower() != q.lower():
                    search_terms.append(translated_q)
            except Exception as e:
                logger.error(f"Translation failed: {e}")
        
        search_conditions = []
        for term in search_terms:
            search_conditions.append("(title ILIKE %s OR source ILIKE %s OR handle ILIKE %s OR keyword ILIKE %s)")
            params.extend([f"%{term}%", f"%{term}%", f"%{term}%", f"%{term}%"])
            
        base_query += " AND (" + " OR ".join(search_conditions) + ")"
        
    base_query += """
        )
        SELECT * FROM ranked_news 
        ORDER BY 
            CASE WHEN threat_level = 'PRIORITY_1' THEN 0 ELSE 1 END,
            source_rank ASC, 
            published_date DESC 
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    
    cursor.execute(base_query, params)
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        r = dict(row)
        if isinstance(r.get('published_date'), datetime): r['published_date'] = r['published_date'].strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(r.get('fetched_at'), datetime): r['fetched_at'] = r['fetched_at'].strftime("%Y-%m-%d %H:%M:%S")
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
    cursor.execute("SELECT COUNT(*) FROM news WHERE threat_level = 'CRITICAL' OR threat_level = 'PRIORITY_1'")
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
    feed_type: str = Query("ALL"),
    publisher: str = Query("All"), 
    handle: str = Query("All"),
    language: str = Query("All"), 
    continent: str = Query("All"), 
    country: str = Query("All")
):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT feed_type, source, handle, category, continent, country, language, keyword, threat_level, title, link, published_date FROM news WHERE 1=1"
    params = []
    
    if category.upper() != "ALL": query += " AND category = %s"; params.append(category.upper())
    if feed_type.upper() != "ALL": query += " AND feed_type = %s"; params.append(feed_type.upper())
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
    writer.writerow(["Platform Stream", "Publisher / Network", "Social Handle", "Threat Category", "Continent", "Country / Region", "Language Lexicon", "Keyword Trigger", "Threat Priority", "Headline", "Direct URL", "Timestamp"])
    for row in rows: 
        writer.writerow([row["feed_type"], row["source"], row["handle"], row["category"], row["continent"], row["country"], row["language"], row.get("keyword", ""), row.get("threat_level", "INFORMATIONAL"), row["title"], row["link"], row["published_date"]])
    
    output.seek(0)
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=geopolitical_dossier_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return response

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
