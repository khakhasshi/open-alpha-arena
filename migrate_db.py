import sqlite3
import os

DB_PATH = "backend/data.db"

def migrate_db():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}. Skipping migration (will be created on startup).")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if columns exist
        cursor.execute("PRAGMA table_info(accounts)")
        columns = [info[1] for info in cursor.fetchall()]
        
        # Add exchange column
        if "exchange" not in columns:
            print("Adding 'exchange' column...")
            cursor.execute("ALTER TABLE accounts ADD COLUMN exchange VARCHAR(20) DEFAULT 'paper'")
        
        if "exchange_api_key" not in columns:
            print("Adding 'exchange_api_key' column...")
            cursor.execute("ALTER TABLE accounts ADD COLUMN exchange_api_key VARCHAR(500)")
            
        if "exchange_secret_key" not in columns:
            print("Adding 'exchange_secret_key' column...")
            cursor.execute("ALTER TABLE accounts ADD COLUMN exchange_secret_key VARCHAR(500)")

        conn.commit()
        print("Migration completed successfully.")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_db()
