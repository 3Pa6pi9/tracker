import yt_dlp
import os
from fastapi import APIRouter, BackgroundTasks
from firebase_admin import storage

router = APIRouter()

def fetch_and_upload_video(post_url: str):
    # 1. Download to Render's temporary storage
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
        'outtmpl': '/tmp/%(id)s.%(ext)s',
        'quiet': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(post_url, download=True)
        file_path = f"/tmp/{info['id']}.mp4"
        file_name = f"{info['id']}.mp4"
    
    # 2. Upload to Firebase Storage for persistence
    bucket = storage.bucket()
    blob = bucket.blob(f"intelligence_videos/{file_name}")
    blob.upload_from_filename(file_path)
    blob.make_public()
    
    # 3. Clean up Render's local disk
    os.remove(file_path)
    
    return blob.public_url

@router.post("/api/videos/extract")
async def extract_social_video(post_url: str):
    download_url = fetch_and_upload_video(post_url)
    return {"status": "success", "firebase_url": download_url}
