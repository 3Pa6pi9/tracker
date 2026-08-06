import sqlite3
import pandas as pd
import os

DB_NAME = "tracker_data.db"

def inspect_database():
    if not os.path.exists(DB_NAME):
        print(f"[!] Error: Database file '{DB_NAME}' does not exist yet. Run tracker.py first.")
        return

    conn = sqlite3.connect(DB_NAME)
    
    print("\n" + "="*50)
    print(" 📊 GEOPOLITICAL INTEL DATABASE DIAGNOSTIC TOOL ")
    print("="*50)
    
    total_rows = pd.read_sql_query("SELECT COUNT(*) as total FROM news", conn).iloc[0]['total']
    print(f"Total Logged Intelligence Items: {total_rows}\n")
    
    print("--- RED TAB BREAKDOWN (Middle East) ---")
    red_df = pd.read_sql_query("SELECT source, COUNT(*) as record_count FROM news WHERE category='RED' GROUP BY source ORDER BY record_count DESC", conn)
    print(red_df.to_string(index=False) if not red_df.empty else "No records found in RED category.")
    
    print("\n--- GREEN TAB BREAKDOWN (Global/Diplomatic) ---")
    green_df = pd.read_sql_query("SELECT source, COUNT(*) as record_count FROM news WHERE category='GREEN' GROUP BY source ORDER BY record_count DESC", conn)
    print(green_df.to_string(index=False) if not green_df.empty else "No records found in GREEN category.")
    
    print("\n" + "="*50)
    conn.close()

if __name__ == "__main__":
    inspect_database()