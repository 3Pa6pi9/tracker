from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import sqlite3
import uvicorn

app = FastAPI(title="Content Tracker Dashboard")

def get_db_data():
    """Fetch all tracked items from SQLite database."""
    conn = sqlite3.connect('tracker_data.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, source, title, link, published_at, fetched_at 
            FROM content_tracker 
            ORDER BY id DESC
        ''')
        rows = [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    return rows

@app.get("/api/items")
def api_get_items():
    return get_db_data()

@app.get("/", response_class=HTMLResponse)
def render_dashboard():
    return """
    
    
    
        
        
        Pulse Tracker | Content Command Center
        
        
        
    
    
        
        
            
                
                    
                        ⚡
                    
                    
                        Pulse Tracker
                        Live Article & Social Monitor
                    
                
                
                    
                    Refresh Data
                
            
        

        
            
            
                
                    Total Aggregated
                    0
                
                
                    Google News
                    0
                
                
                    X Posts
                    0
                
            

            
            
                
                
                    
                    
                

                
                
                    All
                    Google News
                    X Posts
                
            

            
            
                
            
        

        

        
    
    
    """

if __name__ == "__main__":
    print("🚀 Starting Web Dashboard on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
