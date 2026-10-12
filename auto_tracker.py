import asyncio
import feedparser
from datetime import datetime, timezone
from social_video_router import fetch_and_upload_video

# Import your database save function and keywords
from main import PRIORITY_ALERT_KEYWORDS, MULTILINGUAL_LEXICON, save_items_bulk

SOCIAL_FEEDS = [
    "https://rsshub.app/twitter/search/muslim+brotherhood",
]

async def run_social_video_sweep():
    while True:
        for feed_url in SOCIAL_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    text = (entry.title + " " + entry.get("description", "")).lower()
                    
                    is_priority = any(kw in text for kw in PRIORITY_ALERT_KEYWORDS)
                    
                    matched_keyword = ""
                    heat_score = 0
                    for lang, dicts in MULTILINGUAL_LEXICON.items():
                        for kw in dicts.get("critical", []):
                            if kw.lower() in text: heat_score += 3; matched_keyword = matched_keyword or kw
                        for kw in dicts.get("elevated", []):
                            if kw.lower() in text: heat_score += 1.5; matched_keyword = matched_keyword or kw
                        for kw in dicts.get("general", []):
                            if kw.lower() in text: heat_score += 1; matched_keyword = matched_keyword or kw

                    if is_priority or heat_score >= 1.0:
                        level = "CRITICAL" if (is_priority or heat_score >= 3.0) else ("ELEVATED" if heat_score >= 1.0 else "INFORMATIONAL")
                        category = "ALL" # Use ALL so it appears in general, adjust if you want STRICT routing
                        
                        try:
                            # 1. Download and get the Firebase MP4 link
                            firebase_url = fetch_and_upload_video(entry.link)
                            
                            # 2. Package it for your existing database function
                            item = {
                                'title': entry.title,
                                'link': firebase_url, 
                                'source': 'Social Video Extraction',
                                'category': category,
                                'handle': 'Auto-Tracker',
                                'continent': 'Global',
                                'country': 'Global',
                                'region': 'Global',
                                'language': 'English',
                                'thumbnail': '', 
                                'feed_type': 'SOCIAL_VIDEO',
                                'published_date': datetime.now(timezone.utc).isoformat(),
                                'keyword': matched_keyword,
                                'threat_level': level
                            }
                            
                            # 3. Save to PostgreSQL
                            await asyncio.to_thread(save_items_bulk, [item])
                            print(f"[{level}] Saved to DB: {firebase_url}")
                            
                        except Exception as e:
                            print(f"Extraction failed: {e}")
            except Exception as feed_err:
                print(f"Error reading feed {feed_url}: {feed_err}")
        
        await asyncio.sleep(1800)
