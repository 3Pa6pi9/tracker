import os, re, html, asyncio, logging
from datetime import datetime
import httpx
from fastapi import APIRouter, Body
from deep_translator import GoogleTranslator

logger = logging.getLogger("uvicorn")
router = APIRouter()

RED_TPL = [
    "Cette sequence diffusee depuis le terrain met en lumiere l'evolution rapide de la situation securitaire concernant {country}. Les observateurs suivent avec attention les repercussions possibles sur l'equilibre regional.",
    "Les images qui circulent actuellement temoignent d'une nette montee des tensions autour de {country}. Plusieurs sources regionales confirment que le contexte reste particulierement sensible sur place.",
    "Ce nouveau developpement rapporte par {source} souligne la fragilite de la situation actuelle concernant {country}. Les acteurs internationaux restent attentifs aux prochaines reactions officielles."
]

GEN_TPL = [
    "Cette sequence illustre la dynamique diplomatique actuelle impliquant {country} et ses partenaires internationaux. Ces echanges confirment la volonte de consolider la cooperation strategique et economique.",
    "Point sur l'actualite internationale concernant {country}, ou les consultations bilaterales se poursuivent. Cette initiative traduit l'evolution des priorites politiques et commerciales dans la region.",
    "Retour en images sur cette sequence diplomatique liee a {country} et relayee par {source}. Une etape significative qui souligne l'importance du dialogue bilateral actuel."
]

COUNTRIES_FR = {
    "United States": "les Etats-Unis", "United Kingdom": "le Royaume-Uni", "UAE": "les Emirats arabes unis",
    "Saudi Arabia": "l'Arabie saoudite", "Turkey": "la Turquie", "Russia": "la Russie", "Iran": "l'Iran",
    "Israel": "Israel", "Lebanon": "le Liban", "Syria": "la Syrie", "Iraq": "l'Irak", "Yemen": "le Yemen",
    "Sudan": "le Soudan", "Somalia": "la Somalie", "Egypt": "l'Egypte", "Ethiopia": "l'Ethiopie",
    "France": "la France", "Qatar": "le Qatar", "Global": "la scene internationale", "Regional": "la region"
}

def strip_emojis(text: str) -> str:
    return re.sub(r'[\U00010000-\U0010ffff\u2600-\u27bf]', '', str(text or '')).strip()

def translate_fr(text: str) -> str:
    clean = strip_emojis(text)
    if not clean:
        return "Point de situation international"
    try:
        res = GoogleTranslator(source='auto', target='fr').translate(clean)
        if res:
            return strip_emojis(res)
    except Exception:
        pass
    return clean

def build_french_editorial_kit(item: dict) -> dict:
    raw_title = strip_emojis(item.get("title") or "Point de situation international")
    fr_title = translate_fr(raw_title)
    if not fr_title.endswith((".", "!", "?")):
        fr_title += "."
    country = str(item.get("country") or "Global")
    country_fr = COUNTRIES_FR.get(country, country)
    source = strip_emojis(str(item.get("source") or "la redaction").replace("(Video)", ""))
    cat = str(item.get("category") or "GENERAL").upper()
    link = str(item.get("link") or "")
    idx = int(item.get("id") or len(raw_title)) % 3

    if cat == "RED":
        body_fr = RED_TPL[idx].format(country=country_fr, source=source)
        tags = "#ActualiteInternationale #Geopolitique #Securite #Analyse"
    else:
        body_fr = GEN_TPL[idx].format(country=country_fr, source=source)
        tags = "#Diplomatie #RelationsBilaterales #PolitiqueEtrangere #Cooperation"

    c_slug = re.sub(r'[^a-zA-Z0-9]', '', country)
    c_tag = f"#{c_slug}" if (c_slug and c_slug != "Global") else "#Monde"
    hashtags = f"{c_tag} {tags}"

    caption = f"{fr_title}\n\n{body_fr}\n\n{hashtags}"
    comment = f"Que pensez-vous de cette evolution concernant {country_fr} ? Partagez votre avis en commentaire.\nLien de la video : {link}"
    full_bundle = f"{caption}\n\n--- CUT COMMENT BELOW ---\n{comment}"
    return {"caption": caption, "comment": comment, "hashtags": hashtags, "full_bundle": full_bundle}

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
                red_exclude_uae_count INT DEFAULT 2,
                red_include_uae_count INT DEFAULT 2,
                general_bilateral_count INT DEFAULT 2,
                general_non_bilateral_count INT DEFAULT 2,
                bot_token TEXT DEFAULT '',
                red_chat_id TEXT DEFAULT '',
                red_topic_id TEXT DEFAULT '',
                general_chat_id TEXT DEFAULT '',
                general_topic_id TEXT DEFAULT '',
                last_run_date TEXT DEFAULT ''
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
    env_chat = os.getenv("TELEGRAM_CHAT_ID", "")
    if not d.get("bot_token") and env_token:
        d["bot_token"] = env_token
    if not d.get("red_chat_id") and env_chat:
        d["red_chat_id"] = env_chat
    if not d.get("general_chat_id"):
        d["general_chat_id"] = d.get("red_chat_id", env_chat)
    return d

def mark_link_posted(link: str, bucket: str = "POSTED"):
    import main
    if not link:
        return
    try:
        conn = main.get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO tg_sent_log (video_link, bucket) VALUES (%s, %s) ON CONFLICT (video_link) DO UPDATE SET bucket = EXCLUDED.bucket", (link, bucket))
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
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": referer, "Accept": "*/*"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        resp = await client.get(clean_url, headers=headers)
        resp.raise_for_status()
        return resp.content

async def send_single_video_to_tg(item: dict, settings: dict = None, bucket_label: str = "") -> dict:
    if settings is None:
        settings = get_tg_settings_dict()
    bot_token = (settings.get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    cat = str(item.get("category") or "GENERAL").upper()

    if cat == "RED":
        chat_id = (settings.get("red_chat_id") or os.getenv("TELEGRAM_CHAT_ID") or "").strip()
        topic_id = (settings.get("red_topic_id") or "").strip()
    else:
        chat_id = (settings.get("general_chat_id") or settings.get("red_chat_id") or os.getenv("TELEGRAM_CHAT_ID") or "").strip()
        topic_id = (settings.get("general_topic_id") or "").strip()

    if not bot_token or not chat_id:
        return {"status": "error", "detail": "Missing Telegram Bot Token or Chat ID in TG Settings."}

    kit = await asyncio.to_thread(build_french_editorial_kit, item)
    # Clean French caption + hashtags + comment + link ONLY (no extra wrappers)
    clean_tg_caption = f"{kit['caption']}\n\n{kit['comment']}"
    if len(clean_tg_caption) > 1020:
        clean_tg_caption = clean_tg_caption[:1017] + "..."

    video_url = item.get("link", "")
    try:
        video_bytes = await fetch_video_bytes(video_url)
    except Exception as e:
        return {"status": "error", "detail": f"Failed to fetch MP4 binary: {e}"}

    tg_api_url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    form_data = {"chat_id": chat_id, "caption": clean_tg_caption, "supports_streaming": "true"}
    if topic_id and topic_id.isdigit():
        form_data["message_thread_id"] = int(topic_id)
    files = {"video": ("video.mp4", video_bytes, "video/mp4")}

    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(tg_api_url, data=form_data, files=files)
        res_json = resp.json()
        if not res_json.get("ok"):
            return {"status": "error", "detail": res_json.get("description", "Telegram API error")}
        await asyncio.to_thread(mark_link_posted, video_url, bucket_label or f"TG_{cat}")
        return {"status": "success", "message": "Sent MP4 video to Telegram", "link": video_url, "kit": kit}

def query_unsent_videos(bucket: str, limit: int) -> list:
    import main
    if limit <= 0:
        return []
    conn = main.get_db_connection()
    c = conn.cursor()
    uae_cond = "(country = 'UAE' OR title ILIKE '%%UAE%%' OR title ILIKE '%%Emirates%%' OR title ILIKE '%%Abu Dhabi%%' OR title ILIKE '%%Dubai%%' OR title ILIKE '%%الإمارات%%')"
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

async def run_daily_batch_dispatch() -> dict:
    import main
    settings = get_tg_settings_dict()
    buckets = [
        ("red_exclude_uae", int(settings.get("red_exclude_uae_count") or 0), "RED"),
        ("red_include_uae", int(settings.get("red_include_uae_count") or 0), "RED"),
        ("general_bilateral", int(settings.get("general_bilateral_count") or 0), "GENERAL"),
        ("general_non_bilateral", int(settings.get("general_non_bilateral_count") or 0), "GENERAL"),
    ]
    total_sent = 0
    sent_links = []
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
            await asyncio.sleep(1.5)
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    try:
        conn = main.get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE tg_settings SET last_run_date = %s WHERE id = 1", (today_str,))
        conn.close()
    except Exception:
        pass
    return {"status": "success", "total_sent": total_sent, "sent_links": sent_links}

async def daily_tg_scheduler_loop():
    await asyncio.sleep(5)
    init_tg_tables()
    while True:
        try:
            settings = await asyncio.to_thread(get_tg_settings_dict)
            if settings.get("enabled"):
                now_utc = datetime.utcnow()
                today_str = now_utc.strftime("%Y-%m-%d")
                curr_hm = now_utc.strftime("%H:%M")
                sched_hm = str(settings.get("schedule_time") or "09:00").strip()
                if settings.get("last_run_date") != today_str and curr_hm == sched_hm:
                    await run_daily_batch_dispatch()
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        await asyncio.sleep(30)

@router.post("/api/french-kit")
async def api_french_kit(payload: dict = Body(...)):
    return await asyncio.to_thread(build_french_editorial_kit, payload)

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
            enabled = %s, schedule_time = %s,
            red_exclude_uae_count = %s, red_include_uae_count = %s,
            general_bilateral_count = %s, general_non_bilateral_count = %s,
            bot_token = %s, red_chat_id = %s, red_topic_id = %s,
            general_chat_id = %s, general_topic_id = %s
        WHERE id = 1
    """, (
        bool(payload.get("enabled", False)), str(payload.get("schedule_time", "09:00")).strip(),
        int(payload.get("red_exclude_uae_count", 2)), int(payload.get("red_include_uae_count", 2)),
        int(payload.get("general_bilateral_count", 2)), int(payload.get("general_non_bilateral_count", 2)),
        str(payload.get("bot_token", "")).strip(), str(payload.get("red_chat_id", "")).strip(),
        str(payload.get("red_topic_id", "")).strip(), str(payload.get("general_chat_id", "")).strip(),
        str(payload.get("general_topic_id", "")).strip()
    ))
    conn.close()
    return {"status": "success", "settings": await asyncio.to_thread(get_tg_settings_dict)}

@router.post("/api/telegram/run-daily-now")
async def api_run_daily():
    return await run_daily_batch_dispatch()

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
        c.execute("INSERT INTO tg_sent_log (video_link, bucket) VALUES (%s, %s) ON CONFLICT (video_link) DO UPDATE SET bucket = EXCLUDED.bucket", (link, bucket))
    conn.close()
    return {"status": "success", "link": link, "posted": not unmark}
