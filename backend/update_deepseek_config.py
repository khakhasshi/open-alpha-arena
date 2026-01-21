import sys
import os

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.connection import SessionLocal
from database.models import Account

def update_accounts():
    db = SessionLocal()
    try:
        # Find all AI accounts
        accounts = db.query(Account).filter(Account.account_type == "AI").all()
        print(f"Found {len(accounts)} AI accounts.")

        for account in accounts:
            print(f"Updating account: {account.name} (ID: {account.id})")
            account.model = "deepseek-chat"
            account.base_url = "https://api.deepseek.com"
            account.api_key = "sk-9a066116db774e3ba7c874822c2ad99c"
        
        if accounts:
            db.commit()
            print("Successfully updated all AI accounts to use Deepseek.")
        else:
            print("No accounts found to update.")
            
    except Exception as e:
        print(f"Error updating accounts: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_accounts()
