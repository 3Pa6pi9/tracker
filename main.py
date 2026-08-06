from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Geopolitical Intelligence Dashboard API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "tracker_data.db"

def get_db_connection():
    """Establish and return a safe SQLite database connection."""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail="Database connection failure.")

@app.get("/api/news")
def get_news(category: str = Query(..., description="Select RED or GREEN stream")):
    """Fetch structured news items filtered by category with fallback error handling."""
    cat_upper = category.upper()
    if cat_upper not in ["RED", "GREEN"]:
        raise HTTPException(status_code=400, detail="Invalid category parameter. Use 'RED' or 'GREEN'.")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            """
            SELECT id, title, link, source, category, published_date 
            FROM news 
            WHERE category = ? 
            ORDER BY datetime(published_date) DESC, id DESC 
            LIMIT 150
            """, 
            (cat_upper,)
        )
        rows = cursor.fetchall()
        logger.info(f"Successfully fetched {len(rows)} records for category: {cat_upper}")
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        logger.error(f"Query execution error on /api/news: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve intelligence records.")
    finally:
        conn.close()

@app.delete("/api/cleanup/uae")
def trigger_uae_cleanup():
    """Immediately purge all UAE-related handles and content from the RED tab database."""
    uae_handles = ["@MohamedBinZayed", "@HHShkMohd", "@ABZayed", "@mofauae", "@OFMUAE"]
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        placeholders = ', '.join(['?'] * len(uae_handles))
        cursor.execute(f"DELETE FROM news WHERE source IN ({placeholders})", uae_handles)
        deleted_count = cursor.rowcount
        conn.commit()
        logger.warning(f"SECURITY PURGE: Deleted {deleted_count} UAE-related records.")
        return {
            "status": "success", 
            "deleted_count": deleted_count,
            "message": f"Successfully purged {deleted_count} UAE-related records from the database."
        }
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"Failed to execute UAE data cleanup: {e}")
        raise HTTPException(status_code=500, detail="Database purge operation failed.")
    finally:
        conn.close()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)