import asyncio, re, html, urllib.parse, logging
from datetime import datetime
import httpx

logger = logging.getLogger("uvicorn")

TELEGRAM_VIDEO_CHANNELS = [
    ("Middle_East_Spectator", "Middle East Spectator", "Middle East", "Regional", "RED"),
    ("clashreport", "Clash Report", "Middle East", "Turkey", "RED"),
    ("intelslava", "Intel Slava", "Europe", "Global", "RED"),
    ("warmonitors", "War Monitor", "Middle East", "Regional", "RED"),
    ("ddgeopolitics", "DD Geopolitics", "Global", "Global", "GENERAL"),
    ("wamnews_en", "WAM Emirates News", "Middle East", "UAE", "GENERAL"),
    ("dubaimediaoffice", "Dubai Media Office", "Middle East", "UAE", "GENERAL"),
    ("skynewsarabia", "Sky News Arabia", "Middle East", "UAE", "GENERAL"),
    ("TRTWorld", "TRT World", "Middle East", "Turkey", "GENERAL"),
    ("france24_en", "France 24", "Europe", "France", "GENERAL"),
]

async def scrape_social_videos():
    import main
    items = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    priority_kws = [k.lower() for k in getattr(main, "PRIORITY_ALERT_KEYWORDS", [])]
    crit_kws = ["war", "strike", "attack", "missile", "explosion", "airstrike", "bomb", "clash", "combat"]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=15.0) as client:
        for handle, source_name, continent, country, default_cat in TELEGRAM_VIDEO_CHANNELS:
            try:
                resp = await client.get(f"https://t.me/s/{handle}")
                if resp.status_code != 200:
                    continue
                blocks = resp.text.split("tgme_widget_message_wrap")
                for block in blocks[1:]:
                    v_match = re.search(r'<video[^>]+src="([^"]+\.mp4[^"]*)"', block)
                    if not v_match:
                        continue
                    mp4_url = html.unescape(v_match.group(1))
                    t_match = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
                    raw_text = re.sub(r'<[^>]+>', ' ', t_match.group(1)).strip() if t_match else f"Dispatch from {source_name}"
                    clean_title = re.sub(r'\s+', ' ', raw_text)[:220] or f"Dispatch from {source_name}"
                    thumb_match = re.search(r"tgme_widget_message_video_thumb[^>]+background-image:url\('([^']+)'\)", block)
                    thumb_url = thumb_match.group(1) if thumb_match else ""

                    lower_t = clean_title.lower()
                    is_crit = any(k in lower_t for k in priority_kws) or any(k in lower_t for k in crit_kws)
                    is_uae = any(u in lower_t for u in ["uae", "emirates", "abu dhabi", "dubai", "الإمارات", "أبوظبي", "دبي"]) or country == "UAE"
                    final_country = "UAE" if is_uae else country
                    final_cat = "GENERAL" if (default_cat == "GENERAL" and not is_crit) or (is_uae and not is_crit) else ("RED" if is_crit else default_cat)

                    items.append({
                        'title': clean_title, 'link': mp4_url, 'source': f"{source_name} (Video)",
                        'category': final_cat, 'handle': f"@{handle}", 'continent': continent,
                        'country': final_country, 'region': final_country, 'language': 'English',
                        'thumbnail': thumb_url, 'feed_type': 'SOCIAL_VIDEO', 'published_date': now_str,
                        'keyword': 'UAE Bilateral' if is_uae else 'Geopolitical Video',
                        'threat_level': 'CRITICAL' if final_cat == 'RED' else 'INFORMATIONAL'
                    })
            except Exception as e:
                logger.error(f"TG scrape error ({handle}): {e}")

        # Scrape Reddit / X videos for both RED and GENERAL (including UAE Bilateral)
        video_queries = [
            ("UAE diplomacy OR Abu Dhabi OR Dubai", "Middle East", "UAE", "GENERAL", "UAE Bilateral"),
            ("United Arab Emirates president OR summit", "Middle East", "UAE", "GENERAL", "UAE Bilateral"),
            ("bilateral summit OR diplomatic meeting", "Global", "Global", "GENERAL", "Diplomacy"),
            ("Gaza OR Israel OR Iran strike", "Middle East", "Regional", "RED", "Middle East Crisis"),
            ("Sudan OR Somalia OR Red Sea", "Africa", "Regional", "RED", "Security Alert"),
        ]
        for q_str, cont, cntry, q_cat, kw_label in video_queries:
            try:
                r_url = f"https://www.reddit.com/search.json?q={urllib.parse.quote(q_str)}&sort=new&limit=12"
                resp = await client.get(r_url)
                if resp.status_code != 200:
                    continue
                for child in resp.json().get("data", {}).get("children", []):
                    post = child.get("data", {})
                    media = post.get("secure_media") or post.get("media")
                    mp4_url = media["reddit_video"].get("fallback_url") if (media and "reddit_video" in media) else None
                    if mp4_url:
                        mp4_url = html.unescape(mp4_url)
                        thumb = post.get("thumbnail") if str(post.get("thumbnail", "")).startswith("http") else ""
                        items.append({
                            'title': post.get("title", kw_label)[:220], 'link': mp4_url,
                            'source': f"Social Video (r/{post.get('subreddit', 'worldnews')})",
                            'category': q_cat, 'handle': f"@{post.get('author', 'intel')}",
                            'continent': cont, 'country': cntry, 'region': cntry,
                            'language': 'English', 'thumbnail': thumb, 'feed_type': 'SOCIAL_VIDEO',
                            'published_date': now_str, 'keyword': kw_label,
                            'threat_level': 'CRITICAL' if q_cat == 'RED' else 'INFORMATIONAL'
                        })
            except Exception:
                pass

    if items:
        added, _, _, _ = await asyncio.to_thread(main.save_items_bulk, items)
        logger.info(f"Video sweep indexed {len(items)} videos ({added} new).")
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
