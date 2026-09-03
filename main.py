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

app = FastAPI(title="Global Geopolitical Command Center", version="43.0 - Alert Deduplication Engine")

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
# IN-MEMORY ALERT TRACKER (PREVENTS DUPLICATE NOTIFICATIONS)
# ==============================================================================
ALERTED_PRIORITY_LINKS = set()

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
        "critical": ["krig", "angreb", "missil", "attentat", "
