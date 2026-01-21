from pydantic import BaseModel
from typing import Optional


class AccountCreate(BaseModel):
    """Create a new AI Trading Account"""
    name: str  # Display name (e.g., "GPT Trader", "Claude Analyst")
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    api_key: str
    initial_capital: float = 10000.0
    account_type: str = "AI"  # "AI" or "MANUAL"
    exchange: str = "paper"  # "paper" or "binance"
    exchange_api_key: Optional[str] = None
    exchange_secret_key: Optional[str] = None


class AccountUpdate(BaseModel):
    """Update AI Trading Account"""
    name: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    exchange: Optional[str] = None
    exchange_api_key: Optional[str] = None
    exchange_secret_key: Optional[str] = None


class AccountOut(BaseModel):
    """AI Trading Account output"""
    id: int
    user_id: int
    name: str
    model: str
    base_url: str
    api_key: str  # Will be masked in API responses
    exchange: str
    exchange_api_key: Optional[str]  # Will be masked
    initial_capital: float
    current_cash: float
    frozen_cash: float
    account_type: str
    is_active: bool

    class Config:
        from_attributes = True


class AccountOverview(BaseModel):
    """Account overview with portfolio information"""
    account: AccountOut
    total_assets: float  # Total assets in USD
    positions_value: float  # Total positions value in USD