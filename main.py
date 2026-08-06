from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
import sqlite3
import uvicorn
import logging
import csv
import io
import json
import os
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Geopolitical Intelligence API", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "tracker_data.db"

# --- WEBSOCKET MANAGER ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# --- ROOT ROUTE (SERVES DASHBOARD) ---
@app.get("/", response_class=FileResponse)
def read_root():
    """Serves index.html at the root URL."""
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    raise HTTPException(status_code=404, detail="index.html not found on server")

# --- WEBSOCKET ENDPOINT ---
@app.websocket("/ws/news")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # Keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/api/internal/trigger_update")
async def trigger_update():
    """Endpoint called by tracker.py to notify connected clients of new data."""
    await manager.broadcast(json.dumps({"event": "new_intel"}))
    return {"status": "broadcasted"}

@app.get("/api/news")
def get_news(
    category: str = Query(..., description="Select RED or GREEN"),
    search: str = Query(None, description="Advanced text filtering"),
    page: int = Query(1, description="Pagination page number"),
    limit: int = Query(30, description="Items per page")
):
    """Fetch paginated and filtered news."""
    cat_upper = category.upper()
    offset = (page - 1) * limit
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM news WHERE category = ?"
    params = [cat_upper]
    
    if search:
        query += " AND (title LIKE ? OR source LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
        
    query += " ORDER BY datetime(published_date) DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

@app.get("/api/stats")
def get_stats():
    """Endpoint for Chart.js telemetry visualization."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    cursor.execute("""
        SELECT date(published_date) as date, category, COUNT(*) as count 
        FROM news 
        WHERE date(published_date) >= ? 
        GROUP BY date(published_date), category
        ORDER BY date(published_date) ASC
    """, (seven_days_ago,))
    
    rows = cursor.fetchall()
    conn.close()
    
    stats = {"dates": [], "RED": [], "GREEN": []}
    temp_dict = {}
    
    for row in rows:
        d = row["date"]
        c = row["category"]
        if d not in temp_dict:
            temp_dict[d] = {"RED": 0, "GREEN": 0}
        temp_dict[d][c] = row["count"]
        
    for d in sorted(temp_dict.keys()):
        stats["dates"].append(d)
        stats["RED"].append(temp_dict[d]["RED"])
        stats["GREEN"].append(temp_dict[d]["GREEN"])
        
    return stats

@app.get("/api/export")
def export_csv(category: str = Query(..., description="Select RED or GREEN")):
    """Data export function to download telemetry logs as CSV."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT source, title, link, published_date FROM news WHERE category = ? ORDER BY published_date DESC", (category.upper(),))
    rows = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Source Handle", "Intel Title", "Source URL", "Timestamp"])
    for row in rows:
        writer.writerow([row["source"], row["title"], row["link"], row["published_date"]])
        
    output.seek(0)
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=intel_export_{category}_{datetime.now().strftime('%Y%m%d')}.csv"
    return response

@app.delete("/api/cleanup/uae")
def trigger_uae_cleanup():
    """Purge UAE content from database."""
    uae_handles = ["@MohamedBinZayed", "@HHShkMohd", "@ABZayed", "@mofauae", "@OFMUAE"]
    conn = get_db_connection()
    cursor = conn.cursor()
    placeholders = ', '.join(['?'] * len(uae_handles))
    cursor.execute(f"DELETE FROM news WHERE source IN ({placeholders})", uae_handles)
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"Purged {deleted_count} UAE records."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)