import re
import html
import httpx
from fastapi import APIRouter, Query, Path, Request, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter()

async def _stream_mp4(request: Request, url: str, inline: bool, filename: str):
    clean_url = html.unescape(url.strip())
    if not clean_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid video URL")

    referer = "https://t.me/"
    if "twimg.com" in clean_url or "twitter.com" in clean_url or "x.com" in clean_url:
        referer = "https://x.com/"
    elif "redd.it" in clean_url or "reddit.com" in clean_url:
        referer = "https://www.reddit.com/"

    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": referer,
        "Accept": "*/*",
    }
    if "range" in request.headers and inline:
        req_headers["Range"] = request.headers["range"]

    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', filename or "video_intel.mp4")
    if not safe_name.lower().endswith(".mp4"):
        safe_name += ".mp4"

    client = httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(60.0, connect=15.0))
    req = client.build_request("GET", clean_url, headers=req_headers)
    r = await client.send(req, stream=True)

    if r.status_code >= 400:
        await r.aclose()
        await client.aclose()
        raise HTTPException(status_code=r.status_code, detail="Upstream video unavailable")

    disposition = f'inline; filename="{safe_name}"' if inline else f'attachment; filename="{safe_name}"'
    resp_headers = {
        "Content-Disposition": disposition,
        "Accept-Ranges": "bytes",
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "public, max-age=3600",
    }
    for h in ("content-length", "content-range"):
        if h in r.headers:
            resp_headers[h.title()] = r.headers[h]

    async def stream_chunks():
        try:
            async for chunk in r.aiter_bytes(chunk_size=65536):
                yield chunk
        finally:
            await r.aclose()
            await client.aclose()

    return StreamingResponse(
        stream_chunks(),
        status_code=r.status_code,
        media_type="video/mp4",
        headers=resp_headers
    )

@router.get("/api/videos/download")
async def download_video_proxy(
    request: Request,
    url: str = Query(...),
    inline: bool = Query(False),
    filename: str = Query("video_intel.mp4")
):
    return await _stream_mp4(request, url, inline, filename)

@router.get("/api/videos/direct/{item_id}/{filename}")
async def download_video_by_id(
    request: Request,
    item_id: int = Path(...),
    filename: str = Path(...),
    inline: bool = Query(False)
):
    import main
    conn = main.get_db_connection()
    c = conn.cursor()
    c.execute("SELECT link FROM news WHERE id = %s", (item_id,))
    row = c.fetchone()
    conn.close()
    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="Video ID not found")
    return await _stream_mp4(request, row[0], inline, filename)
