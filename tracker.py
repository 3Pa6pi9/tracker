import sqlite3
import feedparser
import schedule
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_NAME = "tracker_data.db"

# --- CONFIGURATION: RED TAB (Middle East & Sensitive Watchlist) ---
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

# --- CONFIGURATION: GREEN TAB (Global, Africa, Europe Diplomacy) ---
GREEN_HANDLES = [
    # Africa Leaders & Ministries
    "@WilliamsRuto", "@PaulKagame", "@CyrilRamaphosa", "@officialABAT", "@AlsisiOfficial",
    "@MFAEthiopia", "@MusaliaMudavadi", "@ForeignOfficeKE", "@RonaldLamola", 
    "@DIRCO_ZA", "@NigeriaMFA", "@MFAEgOfficial", "@MfaEgypt",
    # Europe Leaders & Ministries
    "@EmmanuelMacron", "@GiorgiaMeloni", "@sanchezcastejon", "@donaldtusk", 
    "@_FriedrichMerz", "@bundeskanzler", "@AussenMinDE", "@AuswaertigesAmt", 
    "@GermanyDiplo", "@Ed_Miliband", "@FCDOGovUK"
]

GREEN_KEYWORDS = [
    # Diplomatic & Bilateral Relations
    "bilateral relations", "state visit", "diplomatic ties", "diplomatic mission", 
    "foreign envoy", "ambassador meeting", "foreign ministry", "peace talks",
    # Trade Agreements & Economic Diplomacy
    "trade agreement", "foreign direct investment", "foreign investment", 
    "economic partnership", "tariff", "sanctions", "trade deal", "memorandum of understanding", "MoU",
    # Security Partnerships & Defense Pacts
    "security partnership", "defense pact", "military agreement", 
    "joint military exercise", "security cooperation", "defense treaty",
    # Global Treaties & International Summits
    "treaty signed", "international summit", "global governance", 
    "UN resolution", "international convention", "multilateral agreement",
    # Geopolitical Shifts & Foreign Influence
    "geopolitical shift", "resource diplomacy", "foreign influence", 
    "strategic alliance", "international relations", "diplomatic shift", "strategic dialogue"
]

def init_db():
    """Initialize SQLite database tables and indices for rapid querying."""
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
    # Create an index on category and date for high-performance dashboard loading
    c.execute('CREATE INDEX IF NOT EXISTS idx_category_date ON news (category, published_date);')
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully with schema and indices.")

def matches_keywords(text: str, keywords: list) -> bool:
    """Strict evaluation to ensure content matches targeted keyword frameworks."""
    if not text:
        return False
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            return True
    return False

def fetch_rss_feed(handle: str, category: str, keywords: list):
    """Parses individual user handles via RSS endpoints and commits filtered rows."""
    clean_handle = handle.replace('@', '')
    rss_url = f"https://nitter.net/{clean_handle}/rss"
    logger.info(f"Scanning stream [{category}] for target source: {handle}")
    
    try:
        feed = feedparser.parse(rss_url)
        if not feed.entries:
            logger.debug(f"No entries parsed or network timeout for {handle}.")
            return

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        added_count = 0
        for entry in feed.entries:
            title = getattr(entry, 'title', 'Untitled Post')
            link = getattr(entry, 'link', '#')
            pub_date = getattr(entry, 'published', time.strftime("%Y-%m-%d %H:%M:%S"))
            
            if matches_keywords(title, keywords):
                try:
                    c.execute(
                        """
                        INSERT OR IGNORE INTO news (title, link, source, category, published_date) 
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (title, link, handle, category, pub_date)
                    )
                    if c.rowcount > 0:
                        added_count += 1
                except sqlite3.Error as db_err:
                    logger.error(f"Database insertion error for item from {handle}: {db_err}")
                    
        conn.commit()
        conn.close()
        if added_count > 0:
            logger.info(f"-> Saved {added_count} new entries for {handle} under [{category}]")
    except Exception as e:
        logger.error(f"Critical exception processing RSS feed for {handle}: {e}")

def run_intelligence_sweep():
    """Executes a full cycle sweep across all RED and GREEN handles."""
    logger.info("=============================================")
    logger.info(f"STARTING INTELLIGENCE SWEEP: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=============================================")
    
    logger.info("Processing RED (Middle East) streams...")
    for handle in RED_HANDLES:
        fetch_rss_feed(handle, "RED", RED_KEYWORDS)
        time.sleep(1.5) # Prevent rate-limiting blocks
        
    logger.info("Processing GREEN (Diplomatic/Global) streams...")
    for handle in GREEN_HANDLES:
        fetch_rss_feed(handle, "GREEN", GREEN_KEYWORDS)
        time.sleep(1.5)

    logger.info("=============================================")
    logger.info("INTELLIGENCE SWEEP COMPLETED SUCCESSFULLY")
    logger.info("=============================================")

if __name__ == "__main__":
    init_db()
    logger.info("Tracker engine boot sequence completed. Executing initial sweep...")
    
    # Run immediately on launch
    run_intelligence_sweep()
    
    # Schedule subsequent sweeps every 30 minutes
    schedule.every(30).minutes.do(run_intelligence_sweep)
    
    while True:
        schedule.run_pending()
        time.sleep(1)