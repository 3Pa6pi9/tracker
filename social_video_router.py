import yt_dlp
import requests
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

router = APIRouter()

def extract_direct_video_info(post_url: str):
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(post_url, download=False)
        if 'entries' in info and info['entries']:
            info = info['entries'][0]
        return {
            'mp4_url': info.get('url', post_url),
            'title': info.get('title', 'Extracted Social Video'),
            'thumbnail': info.get('thumbnail', ''),
            'uploader': info.get('uploader') or info.get('extractor_key', 'Social Video')
        }

@router.post("/api/videos/extract")
async def extract_social_video(post_url: str):
    info = extract_direct_video_info(post_url)
    return {"status": "success", "firebase_url": info["mp4_url"], "info": info}

@router.get("/api/videos/download")
def download_video_proxy(url: str = Query(...)):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, stream=True, timeout=30)
    return StreamingResponse(
        r.iter_content(chunk_size=65536),
        media_type="video/mp4",
        headers={"Content-Disposition": 'attachment; filename="intel_video.mp4"'}
    )
