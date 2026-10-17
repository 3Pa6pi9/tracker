import os
import re
import html
import asyncio
import logging
from datetime import datetime, timedelta
import httpx
from fastapi import APIRouter, Body
from deep_translator import GoogleTranslator

logger = logging.getLogger("uvicorn")
router = APIRouter()

RED_TPL = [
    (
        "Sur le terrain, l'evolution rapide de la situation securitaire "
        "concernant {country} retient toute l'attention. Les derniers elements "
        "rapportes montrent une vigilance accrue autour des zones sensibles "
        "et laissent entrevoir des repercussions importantes pour l'equilibre regional."
    ),
    (
        "La tension reste vive autour de {country} alors que de nouveaux "
        "developpements viennent d'etre documentes sur place. Plusieurs observateurs "
        "soulignent le caractere delicat de cette sequence et suivent de pres "
        "les reactions des acteurs impliques."
    ),
    (
        "Cette sequence illustre la complexite du contexte securitaire actuel "
        "touchant {country}. Les informations qui remontent du terrain confirment "
        "que les prochaines heures seront determinantes pour la suite des evenements."
    ),
]

GEN_TPL = [
    (
        "Les echanges diplomatiques se poursuivent autour de {country} afin de "
        "renforcer la cooperation bilaterale et les partenariats strategiques. "
        "Cette dynamique temoigne d'une volonte commune d'approfondir le dialogue "
        "politique et economique."
    ),
    (
        "Retour sur cette sequence diplomatique impliquant {country} et ses "
        "partenaires internationaux. Les discussions engagées mettent en avant "
        "de nouvelles perspectives de collaboration regionale et commerciale."
    ),
    (
        "Cette rencontre marque une nouvelle etape dans les relations bilaterales "
        "concernant {country}. Les priorites abordees confirment l'importance "
        "accordee a la stabilite et au developpement des echanges."
    ),
]

COUNTRIES_FR = {
    "United States": "les Etats-Unis",
    "United Kingdom": "le Royaume-Uni",
    "UAE": "les Emirats arabes unis",
    "Saudi Arabia": "l'Arabie saoudite",
    "Turkey": "la Turquie",
    "Russia": "la Russie",
    "Iran": "l'Iran",
    "Israel": "Israel",
    "Lebanon": "le Liban",
    "Syria": "la Syrie",
    "Iraq": "l'Irak",
    "Yemen": "le Yemen",
    "Sudan": "le Soudan",
    "Somalia": "la Somalie",
    "Egypt": "l'Egypte",
    "Ethiopia": "l'Ethiopie",
    "France": "la France",
    "Qatar": "le Qatar",
    "Global": "la scene internationale",
    "Regional": "le Moyen-Orient",
}

def strip_emojis_and_noise(text: str) -> str:
    s = str(text or "")
    s = re.sub(r'[\U00010000-\U0010ffff\u2600-\u27bf]', '', s)
    s = re.sub(r'https?://\S+', '', s)
    s = re.sub(r'@[A-Za-z0-9_]+', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def detect_country_fr_from_text(title: str, fallback_country: str) -> str:
    t = str(title or "").lower()
    keyword_map = [
        ("uae", "les Emirats arabes unis"), ("emirates", "les Emirats arabes unis"),
        ("abu dhabi", "les Emirats arabes unis"), ("dubai", "les Emirats arabes unis"),
        ("israel", "Israel"), ("gaza", "Gaza"), ("palestin", "la Palestine"),
        ("lebanon", "le Liban"), ("liban", "le Liban"), ("beirut", "le Liban"),
        ("iran", "l'Iran"), ("tehran", "l'Iran"), ("syria", "la Syrie"),
        ("iraq", "l'Irak"), ("yemen", "le Yemen"), ("red sea", "la mer Rouge"),
        ("sudan", "le Soudan"), ("somalia", "la Somalie"), ("ethiopia", "l'Ethiopie"),
        ("egypt", "l'Egypte"), ("russia", "la Russie"), ("ukrain", "l'Ukraine"),
        ("german", "l'Allemagne"), ("france", "la France"), ("saudi", "l'Arabie saoudite"),
        ("qatar", "le Qatar"), ("united states", "les Etats-Unis"), ("pentagon", "les Etats-Unis")
    ]
    for kw, fr_name in keyword_map:
        if kw in t:
            return fr_name
    if fallback_country in ("Turkey", "Global", "Regional", ""):
        return "la scene internationale"
    return COUNTRIES_FR.get(fallback_country, fallback_country)

async def translate_to_french_reliable(text: str, country_fr: str, is_red: bool) -> str:
    clean = strip_emojis_and_noise(text)
    if not clean or clean.lower().startswith("video intelligence") or clean.lower().startswith("dispatch from"):
        return f"Point de situation en images sur l'actualite concernant {country_fr}."

    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": "auto", "tl": "fr", "dt": "t", "q": clean}
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(url, params=params)
            if r.status_code == 200:
                data = r.json()
                if data and isinstance(data[0], list):
                    translated = "".join(seg[0] for seg in data[0] if seg and seg[0])
                    translated = strip_emojis_and_noise(translated)
                    if translated:
                        return translated
    except Exception:
        pass

    try:
        res = await asyncio.to_thread(lambda: GoogleTranslator(source='auto', target='fr').translate(clean))
        if res:
            return strip_emojis_and_noise(res)
    except Exception:
        pass

    return f"Point de situation en images sur l'actualite concernant {country_fr}."

async def build_french_editorial_kit_async(item: dict) -> dict:
    nl = chr(10)
    raw_title = str(item.get("title") or "")
    fallback_country = str(item.get("country") or "Global")
    country_fr = detect_country_fr_from_text(raw_title, fallback_country)
    cat = str(item.get("category") or "GENERAL").upper()
    is_red = (cat == "RED")

    fr_lead = await translate_to_french_reliable(raw_title, country_fr, is_red)
    if not fr_lead.endswith((".", "!", "?")):
        fr_lead += "."

    if is_red:
        tags = "#ActualiteInternationale #Geopolitique #Securite #Analyse"
    else:
        tags = "#Diplomatie #RelationsBilaterales #PolitiqueEtrangere #Cooperation"

    c_slug = re.sub(r'[^a-zA-Z0-9]', '', country_fr.replace("les ", "").replace("le ", "").replace("la ", "").replace("l'", ""))
    c_tag = f"#{c_slug}" if (c_slug and len(c_slug) > 2 and "sceneinternationale" not in c_slug.lower()) else "#International"
    hashtags = f"{c_tag} {tags}"

    link = str(item.get("link") or "")
    caption = fr_lead + nl + nl + hashtags
    comment = (
        "Que pensez-vous de cette evolution ? "
        "Partagez votre analyse dans les commentaires." + nl +
        "Lien de la video : " + link
    )
    full_bundle = caption + nl + nl + "--- COMMENTAIRE A COUPER ET COLLER SOUS LE POST ---" + nl + comment
    return {
        "caption": caption,
        "comment": comment,
        "hashtags": hashtags,
        "full_bundle": full_bundle,
    }

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
        c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='tg_settings'")
        cols = [r[0] for r in c.fetchall()]
        if "general_schedule_time" not in cols:
            c.execute("ALTER TABLE tg_settings ADD COLUMN general_schedule_time TEXT DEFAULT '09:00'")
        if "tz_offset_minutes" not in cols:
            c.execute("ALTER TABLE tg_settings ADD COLUMN tz_offset_minutes INT DEFAULT 180")
        if "tz_name" not in cols:
            c.execute("ALTER TABLE tg_settings ADD COLUMN tz_name TEXT DEFAULT 'Local Time'")
        if "last_general_run_date" not in cols:
            c.execute("ALTER TABLE tg_settings ADD COLUMN last_general_run_date TEXT DEFAULT ''")

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
        return {"status": "error", "detail": f"Missing Bot Token or {cat} Channel Chat ID in TG Settings."}

    kit = await build_french_editorial_kit_async(item)
    # Strictly French caption + hashtags + French comment + video link (no headers, no emojis, no English)
    clean_tg_caption = f"{kit['caption']}\n\n{kit['comment']}"
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
                    logger.info(f"Running scheduled RED daily TG dispatch at {curr_hm} local time")
                    await run_daily_batch_dispatch(target_group="RED")

                if settings.get("last_general_run_date") != today_str and curr_hm == gen_hm:
                    logger.info(f"Running scheduled GENERAL daily TG dispatch at {curr_hm} local time")
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
