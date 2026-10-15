import asyncio
import requests
import urllib.parse
from datetime import datetime, timezone
import yt_dlp
import logging

logger = logging.getLogger("uvicorn")

def scrape_videos_for_keyword(kw: str, is_critical: bool):
    results = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IntelTracker/1.0"}

    # A. Scrape Reddit Native Video Feeds (Direct MP4s from news/geopolitics/combat subs)
    try:
        r_url = f"https://www.reddit.com/search.json?q={urllib.parse.quote(kw)}&sort=new&limit=8"
        resp = requests.get(r_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            children = resp.json().get("data", {}).get("children", [])
            for child in children:
                post = child.get("data", {})
                media = post.get("secure_media") or post.get("media")
                if media and "reddit_video" in media:
                    mp4_url = media["reddit_video"].get("fallback_url")
                    if mp4_url:
                        thumb = post.get("thumbnail") if str(post.get("thumbnail", "")).startswith("http") else ""
                        results.append({
                            'title': post.get("title", f"Video Intel: {kw}")[:200],
                            'link': mp4_url,
                            'source': f"Social Video • r/{post.get('subreddit', 'Intel')}",
                            'category': 'RED' if is_critical else 'GENERAL',
                            'handle': f"u/{post.get('author', 'intel')}",
                            'continent': 'Global',
                            'country': 'Global',
                            'region': 'Global',
                            'language': 'English',
                            'thumbnail': thumb,
                            'feed_type': 'SOCIAL_VIDEO',
                            'published_date': datetime.now(timezone.utc).isoformat(),
                            'keyword': kw,
                            'threat_level': 'CRITICAL' if is_critical else 'ELEVATED'
                        })
    except Exception as e:
        logger.error(f"Reddit video scrape error for {kw}: {e}")

    # B. Scrape via yt-dlp native search for direct MP4 streams
    try:
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch2:{kw} news footage", download=False)
            for entry in info.get('entries', []) or []:
                if not entry or not entry.get('url'):
                    continue
                results.append({
                    'title': entry.get('title', f"Video Intel: {kw}")[:200],
                    'link': entry.get('url'),
                    'source': f"Video Feed • {entry.get('uploader', 'Global Desk')[:30]}",
                    'category': 'RED' if is_critical else 'GENERAL',
                    'handle': entry.get('channel', 'VideoDesk')[:40],
                    'continent': 'Global',
                    'country': 'Global',
                    'region': 'Global',
                    'language': 'English',
                    'thumbnail': entry.get('thumbnail', ''),
                    'feed_type': 'SOCIAL_VIDEO',
                    'published_date': datetime.now(timezone.utc).isoformat(),
                    'keyword': kw,
                    'threat_level': 'CRITICAL' if is_critical else 'ELEVATED'
                })
    except Exception as e:
        logger.error(f"yt-dlp search error for {kw}: {e}")

    return results

async def run_social_video_sweep(single_run: bool = False):
    import main
    while True:
        try:
            priority_kws = list(getattr(main, "PRIORITY_ALERT_KEYWORDS", ["Muslim Brotherhood", "CAIR", "sanctions", "Gaza"]))
            for kw in priority_kws[:8]:
                items = await asyncio.to_thread(scrape_videos_for_keyword, kw, True)
                if items:
                    await asyncio.to_thread(main.save_items_bulk, items)
                    logger.info(f"Saved {len(items)} videos for keyword: {kw}")
                await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"Video sweep loop error: {e}")

        if single_run:
            break
        await asyncio.sleep(900)
