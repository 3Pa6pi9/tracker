import sqlite3

def view_database():
    conn = sqlite3.connect('tracker_data.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT source, title, published_at, link 
            FROM content_tracker 
            ORDER BY id DESC LIMIT 10
        ''')
        rows = cursor.fetchall()
        
        print(f"\n{'SOURCE':<15} | {'TITLE':<50} | {'PUBLISHED'}")
        print("-" * 100)
        
        for row in rows:
            source, title, date, link = row
            short_title = (title[:47] + '...') if len(title) > 50 else title
            
            print(f"{source:<15} | {short_title:<50} | {date}")
            print(f"🔗 {link}\n")
            
    except sqlite3.OperationalError:
        print("Database not found. Please run tracker.py first to generate data.")
        
    finally:
        conn.close()

if __name__ == "__main__":
    view_database()