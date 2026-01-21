import sys
import os

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.connection import SessionLocal
from database.models import Account, User
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_list_accounts():
    db = SessionLocal()
    try:
        print("Querying accounts...")
        accounts = db.query(Account).filter(Account.is_active == "true").all()
        print(f"Found {len(accounts)} active accounts.")
        
        result = []
        for account in accounts:
            print(f"Processing account {account.id}...")
            user = db.query(User).filter(User.id == account.user_id).first()
            
            data = {
                "id": account.id,
                "user_id": account.user_id,
                "username": user.username if user else "unknown",
                "name": account.name,
                "account_type": account.account_type,
                "initial_capital": float(account.initial_capital),
                "current_cash": float(account.current_cash),
                "frozen_cash": float(account.frozen_cash),
                "model": account.model,
                "base_url": account.base_url,
                "api_key": account.api_key,
                "is_active": account.is_active == "true"
            }
            print(f"Account {account.id} processed successfully.")
            result.append(data)
            
        print("All accounts processed.")
        print(result)

    except Exception as e:
        logger.error(f"Failed to list accounts: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    test_list_accounts()
