import ccxt
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)

class ExchangeService:
    @staticmethod
    def _get_exchange_instance(exchange_id: str, api_key: str, secret_key: str):
        if exchange_id not in ccxt.exchanges:
            raise ValueError(f"Exchange {exchange_id} not supported by CCXT")
        
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({
            'apiKey': api_key,
            'secret': secret_key,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}  # Default to futures for now as project seems leverage focused
        })
        return exchange

    @staticmethod
    def validate_keys(exchange_id: str, api_key: str, secret_key: str) -> bool:
        """
        Validate API keys by fetching balance.
        """
        try:
            exchange = ExchangeService._get_exchange_instance(exchange_id, api_key, secret_key)
            exchange.load_markets()
            exchange.fetch_balance()
            return True
        except Exception as e:
            logger.error(f"Failed to validate keys for {exchange_id}: {e}")
            return False

    @staticmethod
    def get_balance(exchange_id: str, api_key: str, secret_key: str) -> Dict[str, float]:
        """
        Get total account value and available cash (USDT).
        """
        try:
            exchange = ExchangeService._get_exchange_instance(exchange_id, api_key, secret_key)
            balance = exchange.fetch_balance()
            
            # Common stablecoins
            usdt_balance = balance.get('USDT', {}).get('total', 0.0)
            # For futures, 'total' usually contains 'totalMarginBalance' or similar in info
            # Keep it simple for generic support
            
            total_equity = balance.get('total', {}).get('USDT', 0.0)
            free_cash = balance.get('free', {}).get('USDT', 0.0)
             
            # If values are zero/missing, try to fallback to specific exchange logic or just return what we have
            if total_equity == 0 and 'info' in balance:
                # Binance specific fallback for futures
                if exchange_id == 'binance':
                    total_equity = float(balance['info'].get('totalMarginBalance', 0.0))
                    free_cash = float(balance['info'].get('availableBalance', 0.0))

            return {
                "total_equity": total_equity,
                "available_cash": free_cash
            }
        except Exception as e:
            logger.error(f"Failed to fetch balance from {exchange_id}: {e}")
            return {"total_equity": 0.0, "available_cash": 0.0}

    @staticmethod
    def get_positions(exchange_id: str, api_key: str, secret_key: str) -> List[Dict[str, Any]]:
        """
        Get current open positions.
        """
        try:
            exchange = ExchangeService._get_exchange_instance(exchange_id, api_key, secret_key)
            positions = exchange.fetch_positions()
            
            # Normalize positions
            active_positions = []
            for pos in positions:
                # CCXT structure varies, but generally looks for size/contracts > 0
                size = float(pos.get('contracts', 0) or pos.get('info', {}).get('positionAmt', 0))
                if size != 0:
                    symbol = pos.get('symbol')
                    side = pos.get('side').upper() if pos.get('side') else ('LONG' if size > 0 else 'SHORT')
                    entry_price = float(pos.get('entryPrice', 0))
                    leverage = float(pos.get('leverage', 1))
                    unrealized_pnl = float(pos.get('unrealizedPnl', 0))
                    
                    active_positions.append({
                        "symbol": symbol,
                        "side": side,
                        "quantity": abs(size),
                        "entry_price": entry_price,
                        "leverage": leverage,
                        "unrealized_pnl": unrealized_pnl,
                        "market_value": abs(size) * entry_price # Approximate
                    })
            return active_positions
        except Exception as e:
            logger.error(f"Failed to fetch positions from {exchange_id}: {e}")
            return []

    # TODO: Implement place_order for full trading
