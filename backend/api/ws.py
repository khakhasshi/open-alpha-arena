from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import Dict, Set
import json

from database.connection import SessionLocal
from repositories.user_repo import get_or_create_user, get_user
from repositories.account_repo import get_or_create_default_account, get_account
from repositories.order_repo import list_orders
from repositories.position_repo import list_positions
from services.asset_calculator import calc_positions_value, calc_positions_market_value
from services.market_data import get_last_price
from services.scheduler import add_account_snapshot_job, remove_account_snapshot_job
from database.models import Trade, User, Account, CryptoPrice, AIDecisionLog
from sqlalchemy import func
from datetime import datetime, timedelta, date
import logging
from services.asset_curve_calculator import get_all_asset_curves_data_new
from services.exchange_service import ExchangeService


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket):
        pass  # WebSocket is already accepted in the endpoint

    def register(self, account_id: int, websocket: WebSocket):
        self.active_connections.setdefault(account_id, set()).add(websocket)
        # Add scheduled snapshot task for new account
        add_account_snapshot_job(account_id, interval_seconds=10)

    def unregister(self, account_id: int, websocket: WebSocket):
        if account_id in self.active_connections:
            self.active_connections[account_id].discard(websocket)
            if not self.active_connections[account_id]:
                del self.active_connections[account_id]
                # Remove the scheduled task for this account
                remove_account_snapshot_job(account_id)

    async def send_to_account(self, account_id: int, message: dict):
        if account_id not in self.active_connections:
            return
        payload = json.dumps(message, ensure_ascii=False)
        for ws in list(self.active_connections[account_id]):
            try:
                # Check if WebSocket is still open before sending
                if ws.client_state.name != "CONNECTED":
                    self.active_connections[account_id].discard(ws)
                    continue
                await ws.send_text(payload)
            except Exception as e:
                # Log the error and remove broken connection
                logging.warning(f"Failed to send message to WebSocket: {e}")
                self.active_connections[account_id].discard(ws)

    async def broadcast_to_all(self, message: dict):
        """Broadcast message to all connected clients"""
        payload = json.dumps(message, ensure_ascii=False)
        for account_id, websockets in list(self.active_connections.items()):
            for ws in list(websockets):
                try:
                    # Check if WebSocket is still open before sending
                    if ws.client_state.name != "CONNECTED":
                        websockets.discard(ws)
                        continue
                    await ws.send_text(payload)
                except Exception as e:
                    # Log the error and remove broken connection
                    logging.warning(f"Failed to broadcast message to WebSocket: {e}")
                    websockets.discard(ws)


manager = ConnectionManager()


async def broadcast_asset_curve_update(timeframe: str = "1h"):
    """Broadcast asset curve updates to all connected clients"""
    db = SessionLocal()
    try:
        asset_curves = get_all_asset_curves_data(db, timeframe)
        await manager.broadcast_to_all({
            "type": "asset_curve_update",
            "timeframe": timeframe,
            "data": asset_curves
        })
    except Exception as e:
        logging.error(f"Failed to broadcast asset curve update: {e}")
    finally:
        db.close()


def get_all_asset_curves_data(db: Session, timeframe: str = "1h"):
    """Get timeframe-based asset curve data for all accounts - WebSocket version
    
    Uses the new algorithm that draws curves by accounts and creates all-time lists.
    
    Args:
        timeframe: Time period for the curve, options: "5m", "1h", "1d"
    """
    return get_all_asset_curves_data_new(db, timeframe)


manager = ConnectionManager()


async def _send_snapshot_optimized(db: Session, account_id: int):
    """Optimized version of snapshot that reduces expensive operations"""
    account = get_account(db, account_id)
    if not account:
        return
    
    # Real Trading Data Fetching
    real_balance = None
    real_positions = []
    if account.exchange and account.exchange != "paper" and account.exchange_api_key and account.exchange_secret_key:
        try:
            # Note: This is a synchronous call blocking the event loop. 
            # Ideally use run_in_executor or ccxt.async_support
            real_balance = ExchangeService.get_balance(account.exchange, account.exchange_api_key, account.exchange_secret_key)
            real_positions = ExchangeService.get_positions(account.exchange, account.exchange_api_key, account.exchange_secret_key)
            logging.info(f"Fetched real data for {account.name}: Bal={real_balance}, Pos={len(real_positions)}")
        except Exception as e:
            logging.error(f"Failed to fetch real data for account {account.id}: {e}")

    positions = list_positions(db, account_id)
    orders = list_orders(db, account_id)
    trades = (
        db.query(Trade).filter(Trade.account_id == account_id).order_by(Trade.trade_time.desc()).limit(10).all()  # Reduced from 20 to 10
    )
    ai_decisions = (
        db.query(AIDecisionLog).filter(AIDecisionLog.account_id == account_id).order_by(AIDecisionLog.decision_time.desc()).limit(10).all()  # Reduced from 20 to 10
    )
    
    # Calculate positions MARKET VALUE (equity) and NOTIONAL VALUE (exposure)
    positions_market_value = calc_positions_market_value(db, account_id)
    positions_notional_value = calc_positions_value(db, account_id)

    # Override for Real Trading
    current_cash = float(account.current_cash)
    if real_balance:
        # Use Total Equity as Total Assets, and Available Cash
        # But here 'total_assets' = market_value + cash. 
        # Exchange returns 'total_equity' which is exactly that.
        total_assets = real_balance.get("total_equity", 0.0)
        current_cash = real_balance.get("available_cash", 0.0)
        
        # Recalculate market value from real positions if needed, or deduce
        # positions_market_value = total_assets - current_cash
        # But simpler to sum up real positions if we want exact breakdown
        positions_market_value = sum(p.get('market_value', 0) for p in real_positions)
        positions_notional_value = sum(p.get('quantity', 0) * p.get('entry_price', 0) * p.get('leverage', 1) for p in real_positions) # Approx
    else:
        # Paper Trading Default
        total_assets = positions_market_value + float(account.current_cash)

    initial_capital = float(account.initial_capital)
    return_rate = (total_assets / initial_capital) - 1 if initial_capital > 0 else 0.0

    overview = {
        "account": {
            "id": account.id,
            "user_id": account.user_id,
            "name": account.name,
            "account_type": account.account_type,
            "initial_capital": float(account.initial_capital),
            "current_cash": current_cash,
            "frozen_cash": float(account.frozen_cash) if not real_balance else 0.0, # Real trading usually manages frozen internally
            "exchange": account.exchange or "paper", # Pass exchange info
        },
        "return_rate": return_rate,
        "total_assets": total_assets,  # CHANGED: Equity-based total
        "positions_market_value": positions_market_value,  # CHANGED: Market value
        "total_notional_value": total_assets,  # DEPRECATED: Keep for compatibility but use total_assets
        "positions_notional_value": positions_notional_value,  # DEPRECATED: Still available for risk exposure
    }
    
    # Optimize position enrichment - batch price fetching
    enriched_positions = []
    
    if real_balance:
        # Use Real Positions
        # Need to fetch current prices for real positions too to show updated PnL/Value if not provided by exchange fully
        # CCXT positions usually have unrealizedPnl.
        # We map real_positions to frontend structure
        for p in real_positions:
             enriched_positions.append({
                "id": f"{p['symbol']}_{p['side']}", # Fake ID
                "account_id": account_id,
                "symbol": p['symbol'],
                "name": p['symbol'], # Simple name
                "market": "CRYPTO",
                "quantity": float(p['quantity']),
                "available_quantity": float(p['quantity']),
                "avg_cost": float(p['entry_price']),
                "leverage": float(p['leverage']),
                "last_price": 0, # Could fetch, but maybe UI handles missing? Or use entry_price as placeholder?
                                 # Ideally fetch current price.
                "market_value": float(p['market_value']),
                "notional_value": float(p['quantity'] * p['entry_price'] * p['leverage']), # Approx
                "side": p['side'],
                "unrealized_pnl": p.get('unrealized_pnl', 0)
            })
             
        # Fetch prices for real positions to fill 'last_price'
        unique_symbols = set((p['symbol'], "CRYPTO") for p in real_positions) # Assuming CRYPTO market
    else:
        # Paper Trading Logic
        price_error_message = None
    
        # Group positions by symbol to reduce API calls
        unique_symbols = set((p.symbol, p.market) for p in positions)
    
    price_cache = {}
    
    # Fetch all unique prices in one go
    for symbol, market in unique_symbols:
        try:
            price = get_last_price(symbol, market)
            price_cache[(symbol, market)] = price
        except Exception as e:
            price_cache[(symbol, market)] = None
            # Log only if really needed

    if real_balance:
        # Fill price for real positions
        for p in enriched_positions:
            price = price_cache.get((p['symbol'], "CRYPTO"))
            if price:
                p['last_price'] = float(price)
                # Recalc market value if we want live tick updates vs exchange cached
                # But exchange PnL is often better. Let's keep exchange PnL if available or calc.
    else:
        for p in positions:
            price = price_cache.get((p.symbol, p.market))
            enriched_positions.append({
                "id": p.id,
                "account_id": p.account_id,
                "symbol": p.symbol,
                "name": p.name,
                "market": p.market,
                "quantity": float(p.quantity),
                "available_quantity": float(p.available_quantity),
                "avg_cost": float(p.avg_cost),
                "leverage": p.leverage,
                "last_price": float(price) if price is not None else None,
                "market_value": (float(price) * float(p.quantity)) if price is not None else None,
                "notional_value": (float(price) * float(p.quantity) * p.leverage) if price is not None else None,
                "side": p.side
            })

    # Prepare response data - exclude expensive asset curve calculation for frequent updates
    response_data = {
        "type": "snapshot_fast",  # Different type to indicate this is optimized
        "overview": overview,
        "positions": enriched_positions,
        "orders": [
            {
                "id": o.id,
                "order_no": o.order_no,
                "user_id": o.account_id,
                "symbol": o.symbol,
                "name": o.name,
                "market": o.market,
                "side": o.side,
                "order_type": o.order_type,
                "price": float(o.price) if o.price is not None else None,
                "quantity": float(o.quantity),
                "leverage": o.leverage,
                "filled_quantity": float(o.filled_quantity),
                "status": o.status,
            }
            for o in orders[:10]  # Reduced from 20 to 10
        ],
        "trades": [
            {
                "id": t.id,
                "order_id": t.order_id,
                "user_id": t.account_id,
                "symbol": t.symbol,
                "name": t.name,
                "market": t.market,
                "side": t.side,
                "price": float(t.price),
                "quantity": float(t.quantity),
                "commission": float(t.commission),
                "trade_time": str(t.trade_time),
            }
            for t in trades
        ],
        "ai_decisions": [
            {
                "id": d.id,
                "decision_time": str(d.decision_time),
                "reason": d.reason,
                "operation": d.operation,
                "symbol": d.symbol,
                "prev_portion": float(d.prev_portion),
                "target_portion": float(d.target_portion),
                "total_balance": float(d.total_balance),
                "executed": str(d.executed).lower() if d.executed else "false",
                "order_id": d.order_id,
                "leverage": getattr(d, "leverage", 1),
            }
            for d in ai_decisions
        ],
        # Asset curves only included occasionally (every minute)
        "timestamp": datetime.now().timestamp()
    }
    
    # Only include expensive asset curve data every 60 seconds
    current_second = int(datetime.now().timestamp()) % 60
    if current_second < 10:  # First 10 seconds of each minute
        try:
            response_data["all_asset_curves"] = get_all_asset_curves_data(db, "1h")
            response_data["type"] = "snapshot_full"  # Indicate this includes full data
        except Exception as e:
            logger.error(f"Failed to get asset curves: {e}")

    if price_error_message:
        response_data["warning"] = {
            "type": "market_data_error",
            "message": price_error_message
        }

    await manager.send_to_account(account_id, response_data)


async def _send_snapshot(db: Session, account_id: int):
    account = get_account(db, account_id)
    if not account:
        return
    positions = list_positions(db, account_id)
    orders = list_orders(db, account_id)
    trades = (
        db.query(Trade).filter(Trade.account_id == account_id).order_by(Trade.trade_time.desc()).limit(20).all()
    )
    ai_decisions = (
        db.query(AIDecisionLog).filter(AIDecisionLog.account_id == account_id).order_by(AIDecisionLog.decision_time.desc()).limit(20).all()
    )
    
    # Calculate positions MARKET VALUE (equity) and NOTIONAL VALUE (exposure)
    positions_market_value = calc_positions_market_value(db, account_id)
    positions_notional_value = calc_positions_value(db, account_id)

    # Total assets = cash + market value (NOT notional!)
    total_assets = positions_market_value + float(account.current_cash)
    initial_capital = float(account.initial_capital)
    return_rate = (total_assets / initial_capital) - 1 if initial_capital > 0 else 0.0

    overview = {
        "account": {
            "id": account.id,
            "user_id": account.user_id,
            "name": account.name,
            "account_type": account.account_type,
            "initial_capital": float(account.initial_capital),
            "current_cash": float(account.current_cash),
            "frozen_cash": float(account.frozen_cash),
        },
        "return_rate": return_rate,
        "total_assets": total_assets,  # CHANGED: Equity-based total
        "positions_market_value": positions_market_value,  # CHANGED: Market value
        "total_notional_value": total_assets,  # DEPRECATED: Keep for compatibility
        "positions_notional_value": positions_notional_value,  # DEPRECATED: Still available for risk exposure
    }
    # enrich positions with latest price and market value
    enriched_positions = []
    price_error_message = None

    for p in positions:
        try:
            price = get_last_price(p.symbol, p.market)
        except Exception as e:
            price = None
            # Collect price retrieval error messages, especially cookie-related errors
            error_msg = str(e)
            if "cookie" in error_msg.lower() and price_error_message is None:
                price_error_message = error_msg

        enriched_positions.append({
            "id": p.id,
            "account_id": p.account_id,
            "symbol": p.symbol,
            "name": p.name,
            "market": p.market,
            "quantity": float(p.quantity),
            "available_quantity": float(p.available_quantity),
            "avg_cost": float(p.avg_cost),
            "leverage": p.leverage,
            "last_price": float(price) if price is not None else None,
            "market_value": (float(price) * float(p.quantity)) if price is not None else None,
            "notional_value": (float(price) * float(p.quantity) * p.leverage) if price is not None else None,
        })

    # Prepare response data
    response_data = {
        "type": "snapshot",
        "overview": overview,
        "positions": enriched_positions,
        "orders": [
            {
                "id": o.id,
                "order_no": o.order_no,
                "user_id": o.account_id,
                "symbol": o.symbol,
                "name": o.name,
                "market": o.market,
                "side": o.side,
                "order_type": o.order_type,
                "price": float(o.price) if o.price is not None else None,
                "quantity": float(o.quantity),
                "leverage": o.leverage,
                "filled_quantity": float(o.filled_quantity),
                "status": o.status,
            }
            for o in orders[:20]
        ],
        "trades": [
            {
                "id": t.id,
                "order_id": t.order_id,
                "user_id": t.account_id,
                "symbol": t.symbol,
                "name": t.name,
                "market": t.market,
                "side": t.side,
                "price": float(t.price),
                "quantity": float(t.quantity),
                "commission": float(t.commission),
                "trade_time": str(t.trade_time),
            }
            for t in trades
        ],
        "ai_decisions": [
            {
                "id": d.id,
                "decision_time": str(d.decision_time),
                "reason": d.reason,
                "operation": d.operation,
                "symbol": d.symbol,
                "prev_portion": float(d.prev_portion),
                "target_portion": float(d.target_portion),
                "total_balance": float(d.total_balance),
                "executed": str(d.executed).lower() if d.executed else "false",
                "order_id": d.order_id,
                "leverage": getattr(d, "leverage", 1),
            }
            for d in ai_decisions
        ],
        "all_asset_curves": get_all_asset_curves_data(db, "1h"),
    }

    if price_error_message:
        response_data["warning"] = {
            "type": "market_data_error",
            "message": price_error_message
        }

    await manager.send_to_account(account_id, response_data)


async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    account_id: int | None = None
    user_id: int | None = None  # Initialize user_id to avoid UnboundLocalError

    try:
        while True:
            # Check if WebSocket is still connected before trying to receive
            if websocket.client_state.name != "CONNECTED":
                break
                
            try:
                data = await websocket.receive_text()
            except WebSocketDisconnect:
                # Client disconnected gracefully
                break
            except Exception as e:
                # Handle other connection errors
                logging.error(f"WebSocket receive error: {e}")
                break
                
            try:
                msg = json.loads(data)
            except json.JSONDecodeError as e:
                logging.error(f"Invalid JSON received: {e}")
                try:
                    await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON format"}))
                except:
                    break
                continue
            kind = msg.get("type")
            db: Session = SessionLocal()
            try:
                if kind == "bootstrap":
                    #  mode: Create or get default default user
                    username = msg.get("username", "default")
                    user = get_or_create_user(db, username)
                    
                    # Get or create default account for this user
                    account = get_or_create_default_account(
                        db, 
                        user.id,
                        account_name=f"{username} AI Trader",
                        initial_capital=float(msg.get("initial_capital", 100000))
                    )
                    account_id = account.id
                    manager.register(account_id, websocket)
                    
                    # Send bootstrap confirmation with account info
                    try:
                        await manager.send_to_account(account_id, {
                            "type": "bootstrap_ok", 
                            "user": {"id": user.id, "username": user.username},
                            "account": {"id": account.id, "name": account.name, "user_id": account.user_id}
                        })
                        await _send_snapshot(db, account_id)
                    except Exception as e:
                        logging.error(f"Failed to send bootstrap response: {e}")
                        break
                elif kind == "subscribe":
                    # subscribe existing user_id
                    uid = int(msg.get("user_id"))
                    u = get_user(db, uid)
                    if not u:
                        try:
                            await websocket.send_text(json.dumps({"type": "error", "message": "user not found"}))
                        except:
                            break
                        continue
                    user_id = uid
                    manager.register(user_id, websocket)
                    try:
                        await _send_snapshot(db, user_id)
                    except Exception as e:
                        logging.error(f"Failed to send snapshot: {e}")
                        break
                elif kind == "switch_user":
                    # Switch to different user account
                    target_username = msg.get("username")
                    if not target_username:
                        await websocket.send_text(json.dumps({"type": "error", "message": "username required"}))
                        continue

                    # Unregister from current user if any
                    if user_id is not None:
                        manager.unregister(user_id, websocket)

                    # Find target user
                    target_user = get_or_create_user(db, target_username, 100000.0)
                    user_id = target_user.id

                    # Register to new user
                    manager.register(user_id, websocket)

                    # Send confirmation and snapshot
                    await manager.send_to_account(user_id, {
                        "type": "user_switched",
                        "user": {
                            "id": target_user.id,
                            "username": target_user.username
                        }
                    })
                    await _send_snapshot(db, user_id)
                elif kind == "switch_account":
                    # Switch to different account by ID
                    target_account_id = msg.get("account_id")
                    if not target_account_id:
                        await websocket.send_text(json.dumps({"type": "error", "message": "account_id required"}))
                        continue

                    # Unregister from current account if any
                    if account_id is not None:
                        manager.unregister(account_id, websocket)

                    # Get target account
                    target_account = get_account(db, target_account_id)
                    if not target_account:
                        await websocket.send_text(json.dumps({"type": "error", "message": "account not found"}))
                        continue

                    account_id = target_account.id
                    
                    # Register to new account
                    manager.register(account_id, websocket)

                    # Send confirmation and snapshot
                    await manager.send_to_account(account_id, {
                        "type": "account_switched",
                        "account": {
                            "id": target_account.id,
                            "user_id": target_account.user_id,
                            "name": target_account.name
                        }
                    })
                    await _send_snapshot(db, account_id)
                elif kind == "get_snapshot":
                    if account_id is not None:
                        await _send_snapshot(db, account_id)
                elif kind == "get_asset_curve":
                    # Get asset curve data with specific timeframe
                    timeframe = msg.get("timeframe", "1h")
                    if timeframe not in ["5m", "1h", "1d"]:
                        await websocket.send_text(json.dumps({"type": "error", "message": "Invalid timeframe. Must be 5m, 1h, or 1d"}))
                        continue
                    
                    asset_curves = get_all_asset_curves_data(db, timeframe)
                    await websocket.send_text(json.dumps({
                        "type": "asset_curve_data",
                        "timeframe": timeframe,
                        "data": asset_curves
                    }))
                elif kind == "place_order":
                    if account_id is None:
                        await websocket.send_text(json.dumps({"type": "error", "message": "not authenticated"}))
                        continue

                    try:
                        # Import the order creation service
                        from services.order_matching import create_order

                        # Get account and user object
                        account = get_account(db, account_id)
                        if not account:
                            await websocket.send_text(json.dumps({"type": "error", "message": "account not found"}))
                            continue

                        user = get_user(db, account.user_id)
                        if not user:
                            await websocket.send_text(json.dumps({"type": "error", "message": "user not found"}))
                            continue

                        # Extract order parameters
                        symbol = msg.get("symbol")
                        name = msg.get("name", symbol)  # Use symbol as name if not provided
                        market = msg.get("market", "CRYPTO")
                        side = msg.get("side")
                        order_type = msg.get("order_type")
                        price = msg.get("price")
                        quantity = msg.get("quantity")
                        leverage = msg.get("leverage", 1)

                        # Validate required parameters
                        if not all([symbol, side, order_type, quantity]):
                            await websocket.send_text(json.dumps({"type": "error", "message": "missing required parameters"}))
                            continue

                        # Convert quantity to float (crypto supports fractional quantities)
                        try:
                            quantity = float(quantity)
                        except (ValueError, TypeError):
                            await websocket.send_text(json.dumps({"type": "error", "message": "invalid quantity"}))
                            continue

                        # Validate leverage
                        try:
                            leverage = int(leverage)
                            if leverage < 1 or leverage > 50:
                                await websocket.send_text(json.dumps({"type": "error", "message": "leverage must be between 1 and 50"}))
                                continue
                        except (ValueError, TypeError):
                            await websocket.send_text(json.dumps({"type": "error", "message": "invalid leverage"}))
                            continue

                        # Create the order
                        order = create_order(
                            db=db,
                            account=account,
                            symbol=symbol,
                            name=name,
                            side=side,
                            order_type=order_type,
                            price=price,
                            quantity=quantity,
                            leverage=leverage
                        )

                        # Commit the order
                        db.commit()

                        # Send success response
                        await manager.send_to_account(account_id, {"type": "order_pending", "order_id": order.id})

                        # Send updated snapshot
                        await _send_snapshot(db, account_id)

                    except ValueError as e:
                        # Business logic errors (insufficient funds, etc.)
                        try:
                            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
                        except:
                            break
                    except Exception as e:
                        # Unexpected errors
                        import traceback
                        print(f"Order placement error: {e}")
                        print(traceback.format_exc())
                        try:
                            await websocket.send_text(json.dumps({"type": "error", "message": f"order placement failed: {str(e)}"}))
                        except:
                            break
                elif kind == "ping":
                    try:
                        await websocket.send_text(json.dumps({"type": "pong"}))
                    except:
                        break
                else:
                    try:
                        await websocket.send_text(json.dumps({"type": "error", "message": "unknown message"}))
                    except:
                        break
            finally:
                db.close()
    except WebSocketDisconnect:
        if account_id is not None:
            manager.unregister(account_id, websocket)
        if user_id is not None:
            manager.unregister(user_id, websocket)
        return
    finally:
        # Clean up resources when user disconnects
        if account_id is not None:
            manager.unregister(account_id, websocket)
        if user_id is not None:
            manager.unregister(user_id, websocket)
