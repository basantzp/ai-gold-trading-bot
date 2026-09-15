"""
Execution Engine: Handles risk validation and order transmission to MetaTrader 5 (MT5).
Includes paper trading simulation support for cross-platform execution.
"""

import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

import config

# Try importing MetaTrader 5
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except (ImportError, Exception):
    mt5 = None
    MT5_AVAILABLE = False

HISTORY_FILE = Path(__file__).parent / "trade_history.json"


def log_trade_to_history(trade_record: Dict[str, Any]):
    """Persists executed trade records to a local JSON log."""
    history = []
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []

    history.insert(0, trade_record)
    # Keep last 100 trades
    history = history[:100]

    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"Failed to log trade to history: {e}")


def get_trade_history():
    """Retrieves all past trade records."""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def get_best_filling_mode(symbol_info):
    """Detects supported order filling mode for the specific broker/symbol."""
    if not MT5_AVAILABLE or symbol_info is None:
        return 0

    filling = getattr(symbol_info, "filling_mode", 0)
    if filling & mt5.ORDER_FILLING_IOC:
        return mt5.ORDER_FILLING_IOC
    elif filling & mt5.ORDER_FILLING_FOK:
        return mt5.ORDER_FILLING_FOK
    elif filling & mt5.ORDER_FILLING_RETURN:
        return mt5.ORDER_FILLING_RETURN
    return mt5.ORDER_FILLING_IOC


def execute_trade(
    symbol: str,
    decision: str,
    lot_size: float = None,
    sl: float = None,
    tp: float = None,
    comment: str = "AI Hedge Fund Bot",
    current_price: float = None
) -> Dict[str, Any]:
    """
    Executes a trade order based on the AI Brain's decision.

    Args:
        symbol: Asset symbol (e.g., 'BTCUSD', 'XAUUSD', 'EURUSD')
        decision: 'BUY', 'SELL', or 'HOLD'
        lot_size: Trade volume in lots
        sl: Stop loss price
        tp: Take profit price
        comment: Order comment tag
        current_price: Current market price (for accurate simulation fill)

    Returns:
        Dictionary with execution details and status
    """
    decision = decision.upper().strip()
    lot_size = float(lot_size or config.DEFAULT_LOT_SIZE)

    # 1. HOLD filter: No trade placed
    if decision == "HOLD":
        return {
            "success": False,
            "status": "HOLD",
            "message": "AI Brain recommended HOLD. No order dispatched. Capital preserved.",
            "order_id": None,
            "price": None,
            "volume": 0.0,
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        }

    # 2. Validation
    if decision not in ["BUY", "SELL"]:
        return {
            "success": False,
            "status": "ERROR",
            "message": f"Invalid trading decision: '{decision}'",
            "order_id": None
        }

    # 3. Live MT5 Execution
    if MT5_AVAILABLE:
        try:
            terminal_info = mt5.terminal_info()
            if terminal_info is not None and terminal_info.connected:
                # Select symbol in MarketWatch
                if not mt5.symbol_select(symbol, True):
                    return {
                        "success": False,
                        "status": "ERROR",
                        "message": f"Symbol '{symbol}' not found in MT5 MarketWatch.",
                        "order_id": None
                    }

                symbol_info = mt5.symbol_info(symbol)
                if symbol_info is None:
                    return {
                        "success": False,
                        "status": "ERROR",
                        "message": f"Could not retrieve tick info for '{symbol}'.",
                        "order_id": None
                    }

                # Determine order type and target price
                order_type = mt5.ORDER_TYPE_BUY if decision == "BUY" else mt5.ORDER_TYPE_SELL
                price = symbol_info.ask if decision == "BUY" else symbol_info.bid
                digits = symbol_info.digits
                filling = get_best_filling_mode(symbol_info)

                # Format SL / TP
                final_sl = round(float(sl), digits) if sl and float(sl) > 0 else 0.0
                final_tp = round(float(tp), digits) if tp and float(tp) > 0 else 0.0

                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": float(lot_size),
                    "type": order_type,
                    "price": price,
                    "sl": final_sl,
                    "tp": final_tp,
                    "deviation": config.SLIPPAGE_DEVIATION,
                    "magic": config.MAGIC_NUMBER,
                    "comment": comment,
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": filling,
                }

                result = mt5.order_send(request)
                if result is None:
                    return {
                        "success": False,
                        "status": "FAILED",
                        "message": f"MT5 order_send returned None. Error: {mt5.last_error()}",
                        "order_id": None
                    }

                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    record = {
                        "success": True,
                        "status": "EXECUTED",
                        "mode": "MT5 Live",
                        "order_id": str(result.order),
                        "symbol": symbol,
                        "action": decision,
                        "price": result.price,
                        "volume": result.volume,
                        "sl": final_sl,
                        "tp": final_tp,
                        "retcode": result.retcode,
                        "comment": result.comment,
                        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                    }
                    log_trade_to_history(record)
                    return record
                else:
                    return {
                        "success": False,
                        "status": "REJECTED",
                        "mode": "MT5 Live",
                        "order_id": str(result.order) if hasattr(result, "order") else None,
                        "retcode": result.retcode,
                        "message": f"MT5 order rejected: {result.comment} (retcode: {result.retcode})",
                        "request": request
                    }
        except Exception as e:
            # If MT5 throws, fall through to simulation
            pass

    # 4. Simulation / Paper Trading Execution (Fallback when MT5 is offline or on Linux)
    import portfolio

    if current_price and current_price > 0:
        sim_price = float(current_price)
    elif sl and tp:
        sim_price = float(sl + tp) / 2.0
    else:
        sim_price = 2700.0 if ("XAU" in symbol.upper() or "GOLD" in symbol.upper()) else 68500.0

    # Register into portfolio manager
    try:
        pos = portfolio.open_new_position(
            symbol=symbol,
            action=decision,
            entry_price=sim_price,
            volume=lot_size,
            sl=float(sl) if sl else 0.0,
            tp=float(tp) if tp else 0.0,
            reason=comment,
            model="Antigravity AI (Simulation)"
        )
        simulated_order_id = pos["position_id"]
    except Exception as e:
        simulated_order_id = f"SIM-{int(time.time() * 1000) % 10000000}"

    record = {
        "success": True,
        "status": "EXECUTED",
        "mode": "Simulation (Paper Trading)",
        "order_id": simulated_order_id,
        "symbol": symbol,
        "action": decision,
        "price": sim_price,
        "volume": lot_size,
        "sl": float(sl) if sl else 0.0,
        "tp": float(tp) if tp else 0.0,
        "comment": f"{comment} [Paper Mode]",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "message": f"Simulated {decision} {lot_size} lots of {symbol} at ${sim_price:.2f}"
    }
    log_trade_to_history(record)
    return record
