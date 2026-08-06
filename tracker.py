import sqlite3
import feedparser
import schedule
import time
import requests
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_NAME = "tracker_data.db"
WEBHOOK_URL = "http://localhost:8000/api/internal/trigger_update"

# --- RED TAB (Middle East) ---
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

# --- GREEN TAB (Global / Africa / Europe) ---
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

def init_db():
    conn = sqlite3.connect(DB_NAME)
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

def matches_keywords(text: str, keywords: list) -> bool:
    if not text: return False
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)

def fetch_rss_feed(handle: str, category: str, keywords: list) -> int:
    clean_handle = handle.replace('@', '')
    rss_url = f"https://nitter.net/{clean_handle}/rss"
    
    try:
        feed = feedparser.parse(rss_url)
        if not feed.entries: return 0

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        added_count = 0
        
        for entry in feed.entries:
            title = getattr(entry, 'title', '')
            link = getattr(entry, 'link', '')
            pub_date = getattr(entry, 'published', time.strftime("%Y-%m-%d %H:%M:%S"))
            
            if matches_keywords(title, keywords):
                try:
                    c.execute(
                        "INSERT INTO news (title, link, source, category, published_date) VALUES (?, ?, ?, ?, ?)",
                        (title, link, handle, category, pub_date)
                    )
                    added_count += 1
                except sqlite3.IntegrityError:
                    pass
        conn.commit()
        conn.close()
        return added_count
    except Exception as e:
        logger.error(f"Error fetching {handle}: {e}")
        return 0

def run_sweep():
    logger.info(f"--- STARTING BACKGROUND WORKER SWEEP ---")
    total_new = 0
    
    for handle in RED_HANDLES:
        total_new += fetch_rss_feed(handle, "RED", RED_KEYWORDS)
        time.sleep(1)
        
    for handle in GREEN_HANDLES:
        total_new += fetch_rss_feed(handle, "GREEN", GREEN_KEYWORDS)
        time.sleep(1)

    if total_new > 0:
        logger.info(f"Sweep completed. {total_new} new items indexed. Pinging WebSockets...")
        try:
            requests.post(WEBHOOK_URL, timeout=5)
        except Exception:
            logger.warning("Could not reach webhook to broadcast WebSockets.")
    else:
        logger.info("Sweep completed. No new intel.")

if __name__ == "__main__":
    init_db()
    run_sweep()
    schedule.every(30).minutes.do(run_sweep)
    while True:
        schedule.run_pending()
        time.sleep(1)