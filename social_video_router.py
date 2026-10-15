import httpx
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

router = APIRouter()

@router.get("/api/videos/download")
async def download_video_proxy(url: str = Query(...), inline: bool = Query(False)):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://t.me/"
    }
    client = httpx.AsyncClient(follow_redirects=True, timeout=30.0)
    req = client.build_request("GET", url, headers=headers)
    r = await client.send(req, stream=True)
    disposition = "inline" if inline else 'attachment; filename="intel_video.mp4"'
    return StreamingResponse(
        r.aiter_bytes(chunk_size=65536),
        media_type="video/mp4",
        headers={"Content-Disposition": disposition}
    )
