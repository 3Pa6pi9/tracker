import asyncio
import feedparser
from social_video_router import fetch_and_upload_video

# Your standard intelligence keywords
KEYWORDS = [
    "muslim brotherhood", 
    "maritime security", 
    "human rights", 
    "european parliament"
]

# Add your RSS bridge URLs here (e.g., RSSHub or Nitter endpoints)
SOCIAL_FEEDS = [
    "https://rsshub.app/twitter/search/muslim+brotherhood",
]

async def run_social_video_sweep():
    while True:
        for feed_url in SOCIAL_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    # Check the title and description for keywords
                    text = (entry.title + " " + entry.get("description", "")).lower()
                    
                    if any(kw.lower() in text for kw in KEYWORDS):
                        link = entry.link
                        try:
                            # Pass the matched social link directly to your yt-dlp extractor
                            firebase_url = fetch_and_upload_video(link)
                            print(f"Automated extraction successful: {firebase_url}")
                            
                            # TODO: Log this firebase_url to your database 
                            # so it renders on the dashboard
                            
                        except Exception:
                            # Silently pass if the post matches keywords but contains no video
                            pass
            except Exception as feed_err:
                print(f"Error reading feed {feed_url}: {feed_err}")
        
        # Pause for 30 minutes before sweeping again to avoid rate limits
        await asyncio.sleep(1800)
