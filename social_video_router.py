import re
import html
import urllib.parse
import httpx
from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter()

@router.get("/api/videos/download")
async def download_video_proxy(
    request: Request,
    url: str = Query(...),
    inline: bool = Query(False),
    filename: str = Query("intel_video.mp4")
):
    clean_url = html.unescape(url.strip())
    if not clean_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid video URL")

    referer = "https://t.me/"
    if "twimg.com" in clean_url or "twitter.com" in clean_url or "x.com" in clean_url:
        referer = "https://x.com/"
    elif "redd.it" in clean_url or "reddit.com" in clean_url:
        referer = "https://www.reddit.com/"

    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": referer,
        "Accept": "*/*",
    }
    if "range" in request.headers and inline:
        req_headers["Range"] = request.headers["range"]

    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    if not safe_name.endswith(".mp4"):
        safe_name += ".mp4"

    client = httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(60.0, connect=15.0))
    req = client.build_request("GET", clean_url, headers=req_headers)
    r = await client.send(req, stream=True)

    if r.status_code >= 400:
        await r.aclose()
        await client.aclose()
        raise HTTPException(status_code=r.status_code, detail="Upstream video unavailable")

    disposition = "inline" if inline else f'attachment; filename="{safe_name}"'
    resp_headers = {
        "Content-Disposition": disposition,
        "Accept-Ranges": "bytes",
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "public, max-age=3600",
    }
    for h in ("content-length", "content-range"):
        if h in r.headers:
            resp_headers[h.title()] = r.headers[h]

    media_type = r.headers.get("content-type", "video/mp4")
    if "text/html" in media_type:
        media_type = "video/mp4"

    async def stream_video():
        try:
            async for chunk in r.aiter_bytes(chunk_size=65536):
                yield chunk
        finally:
            await r.aclose()
            await client.aclose()

    return StreamingResponse(
        stream_video(),
        status_code=r.status_code,
        media_type=media_type,
        headers=resp_headers
    )
