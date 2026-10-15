import asyncio
import re
import urllib.parse
from datetime import datetime
import httpx
import logging

logger = logging.getLogger("uvicorn")

TELEGRAM_VIDEO_CHANNELS = [
    ("aljazeera_english", "Al Jazeera English", "Middle East", "Qatar"),
    ("Middle_East_Spectator", "Middle East Spectator", "Middle East", "Regional"),
    ("clashreport", "Clash Report", "Middle East", "Turkey"),
    ("intelslava", "Intel Slava", "Europe", "Global"),
    ("warmonitors", "War Monitor", "Middle East", "Regional"),
    ("ddgeopolitics", "DD Geopolitics", "Global", "Global"),
]

async def scrape_social_videos():
    import main
    items = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    priority_kws = [k.lower() for k in getattr(main, "PRIORITY_ALERT_KEYWORDS", [])]
    general_kws = []
    for lang, dicts in getattr(main, "MULTILINGUAL_LEXICON", {}).items():
        for cat in ["critical", "elevated", "general"]:
            general_kws.extend([k.lower() for k in dicts.get(cat, [])])

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=15.0) as client:
        # A. Scrape Public Telegram Intelligence Video Channels for direct .mp4 files
        for handle, source_name, continent, country in TELEGRAM_VIDEO_CHANNELS:
            try:
                resp = await client.get(f"https://t.me/s/{handle}")
                if resp.status_code != 200:
                    continue
                blocks = resp.text.split("tgme_widget_message_wrap")
                for block in blocks[1:]:
                    v_match = re.search(r'<video[^>]+src="([^"]+\.mp4[^"]*)"', block)
                    if not v_match:
                        continue
                    mp4_url = v_match.group(1)
                    t_match = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
                    raw_text = re.sub(r'<[^>]+>', ' ', t_match.group(1)).strip() if t_match else f"Video intelligence from {source_name}"
                    clean_title = re.sub(r'\s+', ' ', raw_text)[:200]
                    if not clean_title:
                        clean_title = f"Video Dispatch • {source_name}"

                    thumb_match = re.search(r'tgme_widget_message_video_thumb[^>]+background-image:url\('([^']+)'\)', block)
                    thumb_url = thumb_match.group(1) if thumb_match else ""

                    matched_kw = ""
                    is_crit = False
                    lower_title = clean_title.lower()
                    for kw in priority_kws:
                        if kw and kw in lower_title:
                            matched_kw = kw
                            is_crit = True
                            break
                    if not matched_kw:
                        for kw in general_kws[:80]:
                            if kw and kw in lower_title:
                                matched_kw = kw
                                break

                    items.append({
                        'title': clean_title,
                        'link': mp4_url,
                        'source': f"{source_name} (Video)",
                        'category': 'RED' if is_crit else 'GENERAL',
                        'handle': f"@{handle}",
                        'continent': continent,
                        'country': country,
                        'region': country,
                        'language': 'English',
                        'thumbnail': thumb_url,
                        'feed_type': 'SOCIAL_VIDEO',
                        'published_date': now_str,
                        'keyword': matched_kw or 'Geopolitical Video',
                        'threat_level': 'CRITICAL' if is_crit else 'ELEVATED'
                    })
            except Exception as e:
                logger.error(f"Telegram video scrape error ({handle}): {e}")

        # B. Scrape Reddit Video & X/Twitter Video Statuses by Priority Keywords
        search_kws = list(getattr(main, "PRIORITY_ALERT_KEYWORDS", ["Gaza", "Iran", "Israel", "Sanctions", "Sudan", "RSF"]))[:6]
        for kw in search_kws:
            try:
                r_url = f"https://www.reddit.com/search.json?q={urllib.parse.quote(kw)}&sort=new&limit=10"
                resp = await client.get(r_url)
                if resp.status_code != 200:
                    continue
                for child in resp.json().get("data", {}).get("children", []):
                    post = child.get("data", {})
                    media = post.get("secure_media") or post.get("media")
                    mp4_url = None
                    if media and "reddit_video" in media:
                        mp4_url = media["reddit_video"].get("fallback_url")
                    
                    # Also check if post links to an X/Twitter status and resolve via FxTwitter API
                    ext_url = post.get("url_overridden_by_dest", "")
                    if not mp4_url and ("x.com/" in ext_url or "twitter.com/" in ext_url) and "/status/" in ext_url:
                        tw_id = ext_url.split("/status/")[1].split("?")[0].split("/")[0]
                        if tw_id.isdigit():
                            fx_resp = await client.get(f"https://api.fxtwitter.com/status/{tw_id}")
                            if fx_resp.status_code == 200:
                                videos = fx_resp.json().get("tweet", {}).get("media", {}).get("videos", [])
                                if videos:
                                    mp4_url = videos[0].get("url")

                    if mp4_url:
                        thumb = post.get("thumbnail") if str(post.get("thumbnail", "")).startswith("http") else ""
                        items.append({
                            'title': post.get("title", f"Video Intel: {kw}")[:200],
                            'link': mp4_url,
                            'source': f"Social Video • r/{post.get('subreddit', 'intel')}",
                            'category': 'RED',
                            'handle': f"@{post.get('author', 'intel')}",
                            'continent': 'Global',
                            'country': 'Global',
                            'region': 'Global',
                            'language': 'English',
                            'thumbnail': thumb,
                            'feed_type': 'SOCIAL_VIDEO',
                            'published_date': now_str,
                            'keyword': kw,
                            'threat_level': 'CRITICAL'
                        })
            except Exception as e:
                logger.error(f"Keyword video scrape error ({kw}): {e}")

    if items:
        added, _, _, _ = await asyncio.to_thread(main.save_items_bulk, items)
        logger.info(f"Social video sweep indexed {len(items)} videos ({added} new).")
    return len(items)

async def run_social_video_sweep(single_run: bool = False):
    while True:
        try:
            await scrape_social_videos()
        except Exception as e:
            logger.error(f"run_social_video_sweep error: {e}")
        if single_run:
            break
        await asyncio.sleep(600)
