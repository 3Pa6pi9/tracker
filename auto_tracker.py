import asyncio
import feedparser
from social_video_router import fetch_and_upload_video

# Import the exact same keywords your news tracker uses.
# Change 'main' to the actual file where your list lives (e.g., config, database)
from main import KEYWORDS as NEWS_KEYWORDS

# Add your RSS bridge URLs here
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
                    
                    # Use the imported news keywords for the check
                    if any(kw.lower() in text for kw in NEWS_KEYWORDS):
                        link = entry.link
                        try:
                            firebase_url = fetch_and_upload_video(link)
                            print(f"Automated extraction successful: {firebase_url}")
                        except Exception:
                            pass
            except Exception as feed_err:
                print(f"Error reading feed {feed_url}: {feed_err}")
        
        await asyncio.sleep(1800)
