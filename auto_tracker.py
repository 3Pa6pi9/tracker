import asyncio
import feedparser
from social_video_router import fetch_and_upload_video

# Import the exact intelligence parameters from your main tracker
from main import PRIORITY_ALERT_KEYWORDS, MULTILINGUAL_LEXICON

SOCIAL_FEEDS = [
    "https://rsshub.app/twitter/search/muslim+brotherhood",
    # Add your other social RSS bridge URLs here
]

async def run_social_video_sweep():
    while True:
        for feed_url in SOCIAL_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    text = (entry.title + " " + entry.get("description", "")).lower()
                    
                    # 1. Replicate the PRIORITY_1 check
                    is_priority_alert = any(kw in text for kw in PRIORITY_ALERT_KEYWORDS)
                    
                    # 2. Replicate the heat score and lexicon loop
                    matched_keyword = ""
                    heat_score = 0
                    for lang, dicts in MULTILINGUAL_LEXICON.items():
                        for kw in dicts.get("critical", []):
                            if kw.lower() in text:
                                heat_score += 3
                                if not matched_keyword: matched_keyword = kw
                        for kw in dicts.get("elevated", []):
                            if kw.lower() in text:
                                heat_score += 1.5
                                if not matched_keyword: matched_keyword = kw
                        for kw in dicts.get("general", []):
                            if kw.lower() in text:
                                heat_score += 1
                                if not matched_keyword: matched_keyword = kw

                    # 3. Process if it hits any intelligence threshold
                    if is_priority_alert or heat_score >= 1.0:
                        level = "CRITICAL" if (is_priority_alert or heat_score >= 3.0) else ("ELEVATED" if heat_score >= 1.0 else "INFORMATIONAL")
                        category = "red" if level == "CRITICAL" else "general"
                        
                        link = entry.link
                        try:
                            firebase_url = fetch_and_upload_video(link)
                            print(f"[{level}] [{category.upper()} TAB] Video extracted for '{matched_keyword}': {firebase_url}")
                            
                            # TODO: Insert this result into your PostgreSQL 'news' table
                            # Make sure to set feed_type='SOCIAL_VIDEO' so the UI can filter it
                            
                        except Exception:
                            pass
            except Exception as feed_err:
                print(f"Error reading feed {feed_url}: {feed_err}")
        
        await asyncio.sleep(1800)
