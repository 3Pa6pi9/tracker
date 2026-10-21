import os
import re
import html
import random
import hashlib
import asyncio
import logging
from datetime import datetime, timedelta
import httpx
from fastapi import APIRouter, Body
from deep_translator import GoogleTranslator

logger = logging.getLogger("uvicorn")
router = APIRouter()
TRANSLATE_SEM = asyncio.Semaphore(3)
MEMORY_FR_CACHE = {}

CHROME_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

FR_STOPWORDS = {
    "dans", "avec", "pour", "plus", "sont", "cette", "comme", "mais", "elle",
    "leur", "tout", "tous", "aux", "des", "les", "une", "sur", "par", "pas",
    "que", "qui", "est", "ont", "ete", "fait", "etre", "avoir", "apres",
    "avant", "depuis", "alors", "entre", "selon", "contre", "vers", "chez",
    "sous", "sans", "dont", "tres", "meme", "autre", "autres", "deux", "trois",
    "lors", "pres", "suite", "cours", "afin", "autour", "ainsi", "encore",
    "apprend", "voit", "alors", "tandis", "plusieurs", "nouvelle", "nouveau"
}

ENGLISH_MARKER_WORDS = {
    "the", "and", "with", "from", "after", "before", "over", "under",
    "between", "during", "breaking", "watch", "video", "attack", "strike",
    "killed", "injured", "says", "said", "against", "military", "forces",
    "troops", "missile", "drone", "president", "minister", "government",
    "officials", "report", "reported", "according", "amid", "near", "into"
}

# Natural French synonym swaps so captions read like varied human writing
FR_SYNONYM_SWAPS = [
    [("selon les informations", "d'apres les premiers elements"), ("selon les informations", "a en croire les sources locales")],
    [("a declare", "a fait savoir"), ("a declare", "a indique"), ("a declare", "a affirme")],
    [("une attaque", "une offensive"), ("une attaque", "une frappe"), ("une attaque", "un assaut")],
    [("des affrontements", "des heurts"), ("des affrontements", "des echanges de tirs"), ("des affrontements", "des combats")],
    [("dans la region de", "du cote de"), ("dans la region de", "dans le secteur de")],
    [("plusieurs personnes", "plusieurs individus"), ("plusieurs personnes", "de nombreuses personnes")],
    [("les forces", "les unites"), ("les forces", "les troupes")],
    [("un incendie", "un important incendie"), ("un incendie", "un feu majeur")],
    [("les autorites", "les responsables"), ("les autorites", "les services concernes")],
    [("au cours de", "lors de"), ("au cours de", "pendant")],
]

def strip_emojis_and_noise(text: str) -> str:
    s = str(text or "")
    s = re.sub(r'[\U00010000-\U0010ffff\u2600-\u27bf]', '', s)
    s = re.sub(r'https?://\S+', '', s)
    s = re.sub(r'@[A-Za-z0-9_]+', '', s)
    for prefix in ("BREAKING:", "BREAKING -", "BREAKING", "URGENT:", "URGENT", "WATCH:", "VIDEO:", "UPDATE:", "FLASH:"):
        if s.upper().startswith(prefix):
            s = s[len(prefix):].strip()
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def looks_like_english(text: str) -> bool:
    words = [w.lower() for w in re.findall(r"[A-Za-z]+", str(text or ""))]
    if not words:
        return True
    en_hits = sum(1 for w in words if w in ENGLISH_MARKER_WORDS)
    return en_hits >= 2

async def translate_raw_to_french(text: str) -> str:
    clean = strip_emojis_and_noise(text)
    if not clean:
        return ""
    if clean in MEMORY_FR_CACHE:
        return MEMORY_FR_CACHE[clean]

    async with TRANSLATE_SEM:
        # Engine 1: Google GTX API with Chrome User-Agent
        try:
            url = "https://translate.googleapis.com/translate_a/single"
            params = {"client": "gtx", "sl": "auto", "tl": "fr", "dt": "t", "q": clean}
            async with httpx.AsyncClient(headers=CHROME_HEADERS, timeout=10.0) as client:
                r = await client.get(url, params=params)
                if r.status_code == 200:
                    data = r.json()
                    if data and isinstance(data[0], list):
                        translated = "".join(seg[0] for seg in data[0] if seg and seg[0])
                        translated = strip_emojis_and_noise(translated)
                        if translated and not looks_like_english(translated):
                            MEMORY_FR_CACHE[clean] = translated
                            return translated
        except Exception as e:
            logger.warning(f"GTX translate error: {e}")

        # Engine 2: Google Chrome Dict Extension Endpoint (Forced sl=en -> tl=fr)
        try:
            url2 = "https://clients5.google.com/translate_a/t"
            params2 = {"client": "dict-chrome-ex", "sl": "en", "tl": "fr", "q": clean}
            async with httpx.AsyncClient(headers=CHROME_HEADERS, timeout=10.0) as client:
                r2 = await client.get(url2, params=params2)
                if r2.status_code == 200:
                    d2 = r2.json()
                    cand = ""
                    if isinstance(d2, list) and d2:
                        if isinstance(d2[0], str):
                            cand = d2[0]
                        elif isinstance(d2[0], list) and d2[0]:
                            cand = str(d2[0][0])
                    cand = strip_emojis_and_noise(cand)
                    if cand and not looks_like_english(cand):
                        MEMORY_FR_CACHE[clean] = cand
                        return cand
        except Exception as e:
            logger.warning(f"Clients5 translate error: {e}")

        # Engine 3: deep_translator GoogleTranslator with explicit target='fr'
        try:
            res = await asyncio.to_thread(lambda: GoogleTranslator(source='auto', target='fr').translate(clean))
            if res:
                cand3 = strip_emojis_and_noise(res)
                if cand3 and not looks_like_english(cand3):
                    MEMORY_FR_CACHE[clean] = cand3
                    return cand3
        except Exception as e:
            logger.warning(f"deep_translator error: {e}")

        # Engine 4: MyMemory Translation API fallback
        try:
            lang_pair = "en" + chr(124) + "fr"
            url4 = "https://api.mymemory.translated.net/get"
            async with httpx.AsyncClient(headers=CHROME_HEADERS, timeout=10.0) as client:
                r4 = await client.get(url4, params={"q": clean[:450], "langpair": lang_pair})
                if r4.status_code == 200:
                    cand4 = r4.json().get("responseData", {}).get("translatedText", "")
                    cand4 = strip_emojis_and_noise(cand4)
                    if cand4 and not looks_like_english(cand4):
                        MEMORY_FR_CACHE[clean] = cand4
                        return cand4
        except Exception:
            pass

    return ""

def humanize_french_caption(fr_text: str, seed_int: int) -> str:
    text = strip_emojis_and_noise(fr_text)
    if not text:
        return ""

    rng = random.Random(seed_int)

    # 1. Apply natural French synonym variations so captions are uniquely worded
    for swap_group in FR_SYNONYM_SWAPS:
        chosen_old, chosen_new = rng.choice(swap_group)
        pattern = re.compile(re.escape(chosen_old), re.IGNORECASE)
        if pattern.search(text):
            text = pattern.sub(chosen_new, text, count=1)

    # 2. Restructure sentences naturally based on seed
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    if not sentences:
        sentences = [text]

    first = sentences[0].rstrip(".!?").strip()
    rest = " ".join(sentences[1:]).strip()

    # Clause inversion when a comma separates context and action
    if "," in first and (seed_int % 2 == 1):
        parts = [p.strip() for p in first.split(",", 1)]
        if len(parts) == 2 and len(parts[0]) > 14 and len(parts[1]) > 18:
            p0, p1 = parts[0], parts[1]
            if not p1[0].isupper():
                p1 = p1[0].upper() + p1[1:]
            if p0[:2].isupper():
                rebuilt = f"{p1}, {p0}"
            else:
                rebuilt = f"{p1}, tandis que {p0[0].lower() + p0[1:]}" if (seed_int % 4 == 1) else f"{p1}, {p0[0].lower() + p0[1:]}"
            first = rebuilt

    out = f"{first}."
    if rest:
        if not rest.endswith((".", "!", "?")):
            rest += "."
        if seed_int % 3 == 0:
            out = f"{out}\n{rest}"
        else:
            out = f"{out} {rest}"

    return out.strip()

def extract_dynamic_hashtags(fr_text: str, seed_int: int) -> str:
    words = re.findall(r"[A-Za-zÀ-ÿ]{4,}", fr_text)
    dynamic_tags = []
    seen = set()

    for w in words:
        clean_w = w.capitalize()
        low_w = w.lower()
        if low_w not in FR_STOPWORDS and low_w not in seen and len(clean_w) >= 5:
            if w[0].isupper():
                seen.add(low_w)
                dynamic_tags.append(f"#{clean_w}")

    for w in words:
        clean_w = w.capitalize()
        low_w = w.lower()
        if low_w not in FR_STOPWORDS and low_w not in seen and len(clean_w) >= 6:
            seen.add(low_w)
            dynamic_tags.append(f"#{clean_w}")

    rng = random.Random(seed_int)
    if len(dynamic_tags) > 4:
        picked = dynamic_tags[:2] + rng.sample(dynamic_tags[2:], k=min(2, len(dynamic_tags) - 2))
    else:
        picked = dynamic_tags[:4]

    return " ".join(picked)

def get_cached_db_kit(link: str):
    import main
    if not link:
        return None
    try:
        conn = main.get_db_connection()
        c = conn.cursor()
        c.execute("SELECT caption, hashtags, full_bundle FROM fr_kit_cache WHERE video_link = %s", (link,))
        row = c.fetchone()
        conn.close()
        if row and row[0] and not looks_like_english(row[0]):
            return {
                "caption": row[0],
                "comment": link,
                "hashtags": row[1],
                "full_bundle": row[2],
            }
    except Exception:
        pass
    return None

def save_cached_db_kit(link: str, kit: dict):
    import main
    if not link or not kit:
        return
    try:
        conn = main.get_db_connection()
        c = conn.cursor()
        c.execute(
            "INSERT INTO fr_kit_cache (video_link, caption, hashtags, full_bundle) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (video_link) DO UPDATE SET "
            "caption = EXCLUDED.caption, hashtags = EXCLUDED.hashtags, full_bundle = EXCLUDED.full_bundle",
            (link, kit.get("caption", ""), kit.get("hashtags", ""), kit.get("full_bundle", ""))
        )
        conn.close()
    except Exception:
        pass

async def build_french_editorial_kit_async(item: dict) -> dict:
    nl = chr(10)
    raw_title = str(item.get("title") or "").strip()
    link = str(item.get("link") or "").strip()

    cached = await asyncio.to_thread(get_cached_db_kit, link)
    if cached:
        return cached

    seed_str = f"{item.get('id', '')}_{raw_title}_{link}"
    seed_int = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest()[:8], 16)

    translated_fr = await translate_raw_to_french(raw_title)
    unique_caption = humanize_french_caption(translated_fr, seed_int)

    # Strict guard: never allow English text in the caption
    if not unique_caption or looks_like_english(unique_caption):
        # Retry with explicit source='en'
        try:
            retry_fr = await asyncio.to_thread(lambda: GoogleTranslator(source='en', target='fr').translate(strip_emojis_and_noise(raw_title)))
            unique_caption = humanize_french_caption(retry_fr, seed_int)
        except Exception:
            unique_caption = ""

    hashtags = extract_dynamic_hashtags(unique_caption, seed_int)

    parts = []
    if unique_caption:
        parts.append(unique_caption)
    if link:
        parts.append(link)
    if hashtags:
        parts.append(hashtags)

    full_post = (nl + nl).join(parts)
    caption_with_tags = unique_caption + (nl + nl + hashtags if hashtags else "")

    kit = {
        "caption": caption_with_tags,
        "comment": link,
        "hashtags": hashtags,
        "full_bundle": full_post,
    }
    if unique_caption and not looks_like_english(unique_caption):
        await asyncio.to_thread(save_cached_db_kit, link, kit)
    return kit

def init_tg_tables():
    import main
    try:
        conn = main.get_db_connection()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS tg_settings (
                id INT PRIMARY KEY DEFAULT 1,
                enabled BOOLEAN DEFAULT FALSE,
                schedule_time TEXT DEFAULT '09:00',
                general_schedule_time TEXT DEFAULT '09:00',
                tz_offset_minutes INT DEFAULT 180,
                tz_name TEXT DEFAULT 'Local Time',
                red_exclude_uae_count INT DEFAULT 2,
                red_include_uae_count INT DEFAULT 2,
                general_bilateral_count INT DEFAULT 2,
                general_non_bilateral_count INT DEFAULT 2,
                bot_token TEXT DEFAULT '',
                red_chat_id TEXT DEFAULT '',
                red_topic_id TEXT DEFAULT '',
                general_chat_id TEXT DEFAULT '',
                general_topic_id TEXT DEFAULT '',
                last_run_date TEXT DEFAULT '',
                last_general_run_date TEXT DEFAULT ''
            )
        """)
        c.execute("INSERT INTO tg_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING")
        c.execute("""
            CREATE TABLE IF NOT EXISTS tg_sent_log (
                id SERIAL PRIMARY KEY,
                video_link TEXT UNIQUE,
                bucket TEXT,
                sent_at TIMESTAMP DEFAULT NOW()
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS fr_kit_cache (
                video_link TEXT PRIMARY KEY,
                caption TEXT,
                hashtags TEXT,
                full_bundle TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.close()
    except Exception as e:
        logger.error(f"init_tg_tables error: {e}")

def get_tg_settings_dict() -> dict:
    import main
    init_tg_tables()
    conn = main.get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM tg_settings WHERE id = 1")
    row = c.fetchone()
    conn.close()
    d = dict(row) if row else {}
    env_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    env_red_chat = os.getenv("TELEGRAM_RED_CHAT_ID", "") or os.getenv("TELEGRAM_CHAT_ID", "")
    env_gen_chat = os.getenv("TELEGRAM_GENERAL_CHAT_ID", "") or os.getenv("TELEGRAM_CHAT_ID", "")
    if not d.get("bot_token") and env_token:
        d["bot_token"] = env_token
    if not d.get("red_chat_id") and env_red_chat:
        d["red_chat_id"] = env_red_chat
    if not d.get("general_chat_id") and env_gen_chat:
        d["general_chat_id"] = env_gen_chat
    return d

def mark_link_posted(link: str, bucket: str = "POSTED"):
    import main
    if not link:
        return
    try:
        conn = main.get_db_connection()
        c = conn.cursor()
        c.execute(
            "INSERT INTO tg_sent_log (video_link, bucket) VALUES (%s, %s) "
            "ON CONFLICT (video_link) DO UPDATE SET bucket = EXCLUDED.bucket",
            (link, bucket)
        )
        conn.close()
    except Exception:
        pass

async def fetch_video_bytes(video_url: str) -> bytes:
    clean_url = html.unescape(video_url.strip())
    referer = "https://t.me/"
    if "twimg.com" in clean_url or "twitter.com" in clean_url or "x.com" in clean_url:
        referer = "https://x.com/"
    elif "redd.it" in clean_url or "reddit.com" in clean_url:
        referer = "https://www.reddit.com/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": referer,
        "Accept": "*/*",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        resp = await client.get(clean_url, headers=headers)
        resp.raise_for_status()
        return resp.content

async def send_single_video_to_tg(item: dict, settings: dict = None, bucket_label: str = "") -> dict:
    if settings is None:
        settings = await asyncio.to_thread(get_tg_settings_dict)

    bot_token = (settings.get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    cat = str(item.get("category") or "GENERAL").upper()

    if cat == "RED":
        chat_id = (settings.get("red_chat_id") or os.getenv("TELEGRAM_RED_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID") or "").strip()
        topic_id = (settings.get("red_topic_id") or "").strip()
    else:
        chat_id = (settings.get("general_chat_id") or os.getenv("TELEGRAM_GENERAL_CHAT_ID") or settings.get("red_chat_id") or os.getenv("TELEGRAM_CHAT_ID") or "").strip()
        topic_id = (settings.get("general_topic_id") or "").strip()

    if not bot_token or not chat_id:
        return {"status": "error", "detail": f"Missing Bot Token or {cat} Channel Chat ID."}

    kit = await build_french_editorial_kit_async(item)
    clean_tg_caption = kit["full_bundle"]
    if len(clean_tg_caption) > 1020:
        clean_tg_caption = clean_tg_caption[:1017] + "..."

    video_url = item.get("link", "")
    try:
        video_bytes = await fetch_video_bytes(video_url)
    except Exception as e:
        return {"status": "error", "detail": f"Failed to download MP4 binary: {e}"}

    tg_api_url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    form_data = {
        "chat_id": chat_id,
        "caption": clean_tg_caption,
        "supports_streaming": "true",
    }
    if topic_id and topic_id.isdigit():
        form_data["message_thread_id"] = int(topic_id)
    files = {"video": ("video.mp4", video_bytes, "video/mp4")}

    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(tg_api_url, data=form_data, files=files)
        res_json = resp.json()
        if not res_json.get("ok"):
            return {"status": "error", "detail": res_json.get("description", "Telegram API error")}
        await asyncio.to_thread(mark_link_posted, video_url, bucket_label or f"TG_{cat}")
        return {
            "status": "success",
            "message": f"Sent MP4 to {cat} Channel ({chat_id})",
            "link": video_url,
            "kit": kit,
        }

def query_unsent_videos(bucket: str, limit: int) -> list:
    import main
    if limit <= 0:
        return []
    conn = main.get_db_connection()
    c = conn.cursor()
    uae_cond = (
        "(country = 'UAE' OR title ILIKE '%%UAE%%' OR title ILIKE '%%Emirates%%' "
        "OR title ILIKE '%%Abu Dhabi%%' OR title ILIKE '%%Dubai%%' OR title ILIKE '%%الإمارات%%')"
    )
    sql = "SELECT * FROM news WHERE feed_type = 'SOCIAL_VIDEO' AND link NOT IN (SELECT video_link FROM tg_sent_log)"
    if bucket == "red_exclude_uae":
        sql += f" AND category = 'RED' AND NOT {uae_cond}"
    elif bucket == "red_include_uae":
        sql += " AND category = 'RED'"
    elif bucket == "general_bilateral":
        sql += f" AND {uae_cond}"
    elif bucket == "general_non_bilateral":
        sql += f" AND category = 'GENERAL' AND NOT {uae_cond}"
    sql += " ORDER BY published_date DESC LIMIT %s"
    c.execute(sql, (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

async def run_daily_batch_dispatch(target_group: str = "ALL") -> dict:
    import main
    settings = await asyncio.to_thread(get_tg_settings_dict)
    all_buckets = [
        ("red_exclude_uae", int(settings.get("red_exclude_uae_count") or 0), "RED"),
        ("red_include_uae", int(settings.get("red_include_uae_count") or 0), "RED"),
        ("general_bilateral", int(settings.get("general_bilateral_count") or 0), "GENERAL"),
        ("general_non_bilateral", int(settings.get("general_non_bilateral_count") or 0), "GENERAL"),
    ]
    if target_group == "RED":
        buckets = [b for b in all_buckets if b[2] == "RED"]
    elif target_group == "GENERAL":
        buckets = [b for b in all_buckets if b[2] == "GENERAL"]
    else:
        buckets = all_buckets

    total_sent = 0
    sent_links = []
    errors = []
    for b_key, count, forced_cat in buckets:
        if count <= 0:
            continue
        videos = await asyncio.to_thread(query_unsent_videos, b_key, count)
        for v in videos:
            v["category"] = forced_cat
            res = await send_single_video_to_tg(v, settings=settings, bucket_label=b_key)
            if res.get("status") == "success":
                total_sent += 1
                sent_links.append(v.get("link"))
            else:
                errors.append(res.get("detail", "Error"))
            await asyncio.sleep(1.5)

    offset_mins = int(settings.get("tz_offset_minutes") or 180)
    local_now = datetime.utcnow() + timedelta(minutes=offset_mins)
    today_str = local_now.strftime("%Y-%m-%d")
    try:
        conn = main.get_db_connection()
        c = conn.cursor()
        if target_group in ("ALL", "RED"):
            c.execute("UPDATE tg_settings SET last_run_date = %s WHERE id = 1", (today_str,))
        if target_group in ("ALL", "GENERAL"):
            c.execute("UPDATE tg_settings SET last_general_run_date = %s WHERE id = 1", (today_str,))
        conn.close()
    except Exception:
        pass
    return {"status": "success", "total_sent": total_sent, "sent_links": sent_links, "errors": errors[:3]}

async def daily_tg_scheduler_loop():
    await asyncio.sleep(5)
    init_tg_tables()
    while True:
        try:
            settings = await asyncio.to_thread(get_tg_settings_dict)
            if settings.get("enabled"):
                offset_mins = int(settings.get("tz_offset_minutes") or 180)
                local_now = datetime.utcnow() + timedelta(minutes=offset_mins)
                today_str = local_now.strftime("%Y-%m-%d")
                curr_hm = local_now.strftime("%H:%M")

                red_hm = str(settings.get("schedule_time") or "09:00").strip()
                gen_hm = str(settings.get("general_schedule_time") or red_hm).strip()

                if settings.get("last_run_date") != today_str and curr_hm == red_hm:
                    await run_daily_batch_dispatch(target_group="RED")
                if settings.get("last_general_run_date") != today_str and curr_hm == gen_hm:
                    await run_daily_batch_dispatch(target_group="GENERAL")
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        await asyncio.sleep(25)

@router.post("/api/french-kit")
async def api_french_kit(payload: dict = Body(...)):
    return await build_french_editorial_kit_async(payload)

@router.post("/api/telegram/dispatch")
async def api_dispatch_single(payload: dict = Body(...)):
    return await send_single_video_to_tg(payload)

@router.post("/api/telegram/dispatch-batch")
async def api_dispatch_batch(payload: dict = Body(...)):
    items = payload.get("items", [])
    override_cat = payload.get("override_category")
    settings = await asyncio.to_thread(get_tg_settings_dict)
    sent = 0
    sent_links = []
    errors = []
    for item in items:
        if override_cat in ("RED", "GENERAL"):
            item["category"] = override_cat
        res = await send_single_video_to_tg(item, settings=settings)
        if res.get("status") == "success":
            sent += 1
            sent_links.append(item.get("link"))
        else:
            errors.append(res.get("detail", "Error"))
        await asyncio.sleep(1.0)
    if sent > 0:
        return {"status": "success", "sent": sent, "sent_links": sent_links, "errors": errors}
    return {"status": "error", "detail": "; ".join(errors[:3]) if errors else "No videos sent"}

@router.get("/api/telegram/settings")
async def api_get_settings():
    return await asyncio.to_thread(get_tg_settings_dict)

@router.post("/api/telegram/settings")
async def api_save_settings(payload: dict = Body(...)):
    import main
    init_tg_tables()
    conn = main.get_db_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE tg_settings SET
            enabled = %s,
            schedule_time = %s,
            general_schedule_time = %s,
            tz_offset_minutes = %s,
            tz_name = %s,
            red_exclude_uae_count = %s,
            red_include_uae_count = %s,
            general_bilateral_count = %s,
            general_non_bilateral_count = %s,
            bot_token = %s,
            red_chat_id = %s,
            red_topic_id = %s,
            general_chat_id = %s,
            general_topic_id = %s
        WHERE id = 1
    """, (
        bool(payload.get("enabled", False)),
        str(payload.get("schedule_time", "09:00")).strip(),
        str(payload.get("general_schedule_time", payload.get("schedule_time", "09:00"))).strip(),
        int(payload.get("tz_offset_minutes", 180)),
        str(payload.get("tz_name", "Local Time")).strip(),
        int(payload.get("red_exclude_uae_count", 2)),
        int(payload.get("red_include_uae_count", 2)),
        int(payload.get("general_bilateral_count", 2)),
        int(payload.get("general_non_bilateral_count", 2)),
        str(payload.get("bot_token", "")).strip(),
        str(payload.get("red_chat_id", "")).strip(),
        str(payload.get("red_topic_id", "")).strip(),
        str(payload.get("general_chat_id", "")).strip(),
        str(payload.get("general_topic_id", "")).strip(),
    ))
    conn.close()
    return {"status": "success", "settings": await asyncio.to_thread(get_tg_settings_dict)}

@router.post("/api/telegram/run-daily-now")
async def api_run_daily(payload: dict = Body(default={})):
    target_group = str(payload.get("target_group") or "ALL").upper()
    return await run_daily_batch_dispatch(target_group=target_group)

@router.get("/api/posted")
async def api_get_posted():
    import main
    init_tg_tables()
    conn = main.get_db_connection()
    c = conn.cursor()
    c.execute("SELECT video_link, bucket FROM tg_sent_log")
    rows = {r[0]: r[1] for r in c.fetchall() if r[0]}
    conn.close()
    return {"posted": rows}

@router.post("/api/posted/mark")
async def api_mark_posted(payload: dict = Body(...)):
    import main
    init_tg_tables()
    link = str(payload.get("link") or "").strip()
    unmark = bool(payload.get("unmark", False))
    bucket = str(payload.get("bucket") or "POSTED")
    if not link:
        return {"status": "error"}
    conn = main.get_db_connection()
    c = conn.cursor()
    if unmark:
        c.execute("DELETE FROM tg_sent_log WHERE video_link = %s", (link,))
    else:
        c.execute(
            "INSERT INTO tg_sent_log (video_link, bucket) VALUES (%s, %s) "
            "ON CONFLICT (video_link) DO UPDATE SET bucket = EXCLUDED.bucket",
            (link, bucket)
        )
    conn.close()
    return {"status": "success", "link": link, "posted": not unmark}
