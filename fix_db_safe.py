import os
import psycopg2
from urllib.parse import urlparse

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    # Fallback to direct connection parameters if set in main
    try:
        from main import get_db_connection
        conn = get_db_connection()
    except Exception:
        print("DATABASE_URL not found locally. Skipping local DB run; Render will handle it.")
        conn = None

if conn:
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE news 
        SET feed_type = 'SOCIAL_VIDEO' 
        WHERE link ILIKE '%.mp4%' OR link ILIKE '%fxtwitter%' OR source ILIKE '%Video%'
    """)
    conn.commit()
    conn.close()
    print("Database rows updated successfully!")

# Add cache buster to index.html
with open("index.html", "r") as f:
    html = f.read()

if "data-version" not in html:
    html = html.replace("<script>", '<script data-version="widvid-v4">')
    with open("index.html", "w") as f:
        f.write(html)
    print("Cache buster added to index.html!")
