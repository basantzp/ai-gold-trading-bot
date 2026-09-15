"""
Portfolio & Account Manager: Tracks $100 starting capital, P&L, win/loss stats,
active open positions, and closed trades with institutional accuracy.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

STATE_FILE = Path(__file__).parent / "account_state.json"
DEFAULT_INITIAL_BALANCE = 100.0


def _get_contract_multiplier(symbol: str) -> float:
    """Returns the contract size for standard lot calculation."""
    sym = symbol.upper()
    if "XAU" in sym or "GOLD" in sym:
        return 100.0  # 1 lot = 100 oz of gold. 0.01 lot = 1 oz.
    elif "BTC" in sym:
        return 1.0    # 1 lot = 1 BTC. 0.01 lot = 0.01 BTC.
    elif "ETH" in sym:
        return 1.0    # 1 lot = 1 ETH. 0.01 lot = 0.01 ETH.
    else:
        return 100000.0  # Standard forex lot: 100,000 units.


def calculate_trade_pnl(action: str, entry_price: float, exit_price: float, volume: float, symbol: str) -> float:
    """Calculates exact dollar profit or loss for a trade."""
    multiplier = _get_contract_multiplier(symbol)
    if action.upper() == "BUY":
        return (exit_price - entry_price) * volume * multiplier
    elif action.upper() == "SELL":
        return (entry_price - exit_price) * volume * multiplier
    return 0.0


def initialize_account(initial_balance: float = DEFAULT_INITIAL_BALANCE, force: bool = False) -> Dict[str, Any]:
    """Initializes or resets the account state with starting capital (e.g. $100)."""
    if STATE_FILE.exists() and not force:
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
                if "balance" in state and "initial_balance" in state:
                    return state
        except Exception:
            pass

    default_state = {
        "initial_balance": float(initial_balance),
        "balance": float(initial_balance),
        "equity": float(initial_balance),
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "win_count": 0,
        "loss_count": 0,
        "breakeven_count": 0,
        "win_rate": 0.0,
        "total_trades": 0,
        "max_drawdown": 0.0,
        "peak_balance": float(initial_balance),
        "open_positions": [],
        "closed_trades": [],
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    }

    save_account_state(default_state)
    return default_state


def get_account_state() -> Dict[str, Any]:
    """Retrieves current account state, initializing if not present."""
    if not STATE_FILE.exists():
        return initialize_account(DEFAULT_INITIAL_BALANCE)
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return initialize_account(DEFAULT_INITIAL_BALANCE, force=True)


def save_account_state(state: Dict[str, Any]) -> None:
    """Saves the account state to JSON."""
    state["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    # Recalculate win rate
    closed = state.get("closed_trades", [])
    wins = [t for t in closed if t.get("pnl", 0.0) > 0.001]
    losses = [t for t in closed if t.get("pnl", 0.0) < -0.001]
    bes = [t for t in closed if abs(t.get("pnl", 0.0)) <= 0.001]

    state["win_count"] = len(wins)
    state["loss_count"] = len(losses)
    state["breakeven_count"] = len(bes)
    total = len(wins) + len(losses)
    state["win_rate"] = round((len(wins) / total * 100.0), 1) if total > 0 else 0.0
    state["total_trades"] = len(closed)

    # Track peak balance & drawdown
    balance = state.get("balance", DEFAULT_INITIAL_BALANCE)
    peak = max(state.get("peak_balance", DEFAULT_INITIAL_BALANCE), balance)
    state["peak_balance"] = round(peak, 2)
    dd = ((peak - balance) / peak * 100.0) if peak > 0 else 0.0
    state["max_drawdown"] = round(max(state.get("max_drawdown", 0.0), dd), 2)

    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[PORTFOLIO] Failed to save state: {e}")


def open_new_position(
    symbol: str,
    action: str,
    entry_price: float,
    volume: float,
    sl: float,
    tp: float,
    reason: str = "",
    model: str = "Antigravity AI"
) -> Dict[str, Any]:
    """Opens a new simulated position and adds it to the active portfolio."""
    state = get_account_state()
    action = action.upper().strip()
    if action not in ["BUY", "SELL"]:
        raise ValueError(f"Invalid trade action: {action}")

    position_id = f"POS-{int(time.time() * 1000) % 10000000}"
    position = {
        "position_id": position_id,
        "symbol": symbol.upper(),
        "action": action,
        "entry_price": float(entry_price),
        "current_price": float(entry_price),
        "volume": float(volume),
        "sl": float(sl) if sl else 0.0,
        "tp": float(tp) if tp else 0.0,
        "unrealized_pnl": 0.0,
        "return_pct": 0.0,
        "reason": reason,
        "model": model,
        "open_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    }

    state.setdefault("open_positions", []).append(position)
    save_account_state(state)
    return position


def close_existing_position(position_id: str, exit_price: float, exit_reason: str) -> Optional[Dict[str, Any]]:
    """Closes an active position, calculates realized PnL, and updates balance."""
    state = get_account_state()
    open_positions = state.get("open_positions", [])

    target_idx = None
    for i, pos in enumerate(open_positions):
        if pos.get("position_id") == position_id:
            target_idx = i
            break

    if target_idx is None:
        return None

    pos = open_positions.pop(target_idx)
    exit_price = float(exit_price)
    entry_price = float(pos["entry_price"])
    volume = float(pos["volume"])
    symbol = pos["symbol"]
    action = pos["action"]

    pnl = calculate_trade_pnl(action, entry_price, exit_price, volume, symbol)
    pnl = round(pnl, 2)
    return_pct = round((pnl / (entry_price * volume * _get_contract_multiplier(symbol))) * 100.0, 2) if entry_price > 0 else 0.0

    closed_record = {
        "trade_id": pos["position_id"],
        "symbol": symbol,
        "action": action,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "volume": volume,
        "sl": pos.get("sl", 0.0),
        "tp": pos.get("tp", 0.0),
        "pnl": pnl,
        "return_pct": return_pct,
        "exit_reason": exit_reason,
        "reason": pos.get("reason", ""),
        "model": pos.get("model", ""),
        "open_time": pos["open_time"],
        "close_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    }

    # Update account finances
    state["balance"] = round(state["balance"] + pnl, 2)
    state["realized_pnl"] = round(state.get("realized_pnl", 0.0) + pnl, 2)
    state.setdefault("closed_trades", []).insert(0, closed_record)

    # Recompute equity
    recalculate_equity(state, symbol, exit_price)
    save_account_state(state)

    # Sync with Trading Journal
    try:
        import journal
        journal.mark_journal_entry_closed(pos["position_id"], exit_price, pnl, exit_reason)
    except Exception as je:
        print(f"[PORTFOLIO] Journal close sync error: {je}")

    return closed_record


def recalculate_equity(state: Dict[str, Any], current_symbol: str, current_price: float) -> None:
    """Recalculates floating equity based on live prices of open positions."""
    balance = state.get("balance", DEFAULT_INITIAL_BALANCE)
    total_unrealized = 0.0

    for pos in state.get("open_positions", []):
        if pos.get("symbol") == current_symbol.upper():
            pos["current_price"] = current_price
            u_pnl = calculate_trade_pnl(pos["action"], pos["entry_price"], current_price, pos["volume"], pos["symbol"])
            pos["unrealized_pnl"] = round(u_pnl, 2)
            pos["return_pct"] = round((u_pnl / max(pos["entry_price"] * pos["volume"] * _get_contract_multiplier(pos["symbol"]), 1.0)) * 100.0, 2)
            total_unrealized += u_pnl
        else:
            total_unrealized += pos.get("unrealized_pnl", 0.0)

    state["unrealized_pnl"] = round(total_unrealized, 2)
    state["equity"] = round(balance + total_unrealized, 2)


def check_and_update_positions(symbol: str, current_price: float) -> List[Dict[str, Any]]:
    """
    Checks all open positions for TP or SL hits against the live price.
    Automatically closes any position that reached its target or stop level.
    """
    state = get_account_state()
    open_positions = list(state.get("open_positions", []))
    closed_events = []

    for pos in open_positions:
        if pos.get("symbol") != symbol.upper():
            continue

        pos_id = pos["position_id"]
        action = pos["action"]
        sl = float(pos.get("sl", 0.0))
        tp = float(pos.get("tp", 0.0))

        hit_tp = False
        hit_sl = False

        if action == "BUY":
            if tp > 0 and current_price >= tp:
                hit_tp = True
            elif sl > 0 and current_price <= sl:
                hit_sl = True
        elif action == "SELL":
            if tp > 0 and current_price <= tp:
                hit_tp = True
            elif sl > 0 and current_price >= sl:
                hit_sl = True

        if hit_tp:
            closed = close_existing_position(pos_id, exit_price=tp, exit_reason="🎯 Take Profit (TP) Hit")
            if closed:
                closed_events.append(closed)
        elif hit_sl:
            closed = close_existing_position(pos_id, exit_price=sl, exit_reason="🛑 Stop Loss (SL) Hit")
            if closed:
                closed_events.append(closed)

    # Re-fetch state and update equity
    state = get_account_state()
    recalculate_equity(state, symbol, current_price)
    save_account_state(state)
    return closed_events
