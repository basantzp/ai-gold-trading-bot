"""
Trading Journal Engine: Maintains an institutional trade journal with
visual chart snapshots, AI thesis, multi-timeframe confluences, and post-trade audits.
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

JOURNAL_FILE = Path(__file__).parent / "trade_journal.json"


def get_journal_entries() -> List[Dict[str, Any]]:
    """Retrieves all journal entries, sorted with newest first."""
    if JOURNAL_FILE.exists():
        try:
            with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_journal_entries(entries: List[Dict[str, Any]]) -> None:
    """Saves journal entries to local JSON ledger."""
    try:
        with open(JOURNAL_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
    except Exception as e:
        print(f"[JOURNAL] Error saving journal: {e}")


def create_journal_entry(
    trade_id: str,
    symbol: str,
    action: str,
    entry_price: float,
    volume: float,
    sl: float,
    tp: float,
    confidence: int,
    h4_analysis: str = "",
    m15_analysis: str = "",
    reasoning: str = "",
    screenshot_path: Optional[str] = None
) -> Dict[str, Any]:
    """Creates and logs a new institutional journal entry for an opened trade."""
    entries = get_journal_entries()

    # Avoid duplicate entry for the same trade_id
    for e in entries:
        if e.get("trade_id") == trade_id:
            return e

    risk = abs(entry_price - sl) if sl else 0.0
    reward = abs(tp - entry_price) if tp else 0.0
    rr_str = f"1:{reward / risk:.1f}" if risk > 0 else "1:2.0"

    entry = {
        "trade_id": trade_id,
        "symbol": symbol.upper(),
        "action": action.upper(),
        "entry_price": round(float(entry_price), 2),
        "volume": float(volume),
        "sl": round(float(sl), 2) if sl else 0.0,
        "tp": round(float(tp), 2) if tp else 0.0,
        "risk_reward": rr_str,
        "confidence": int(confidence),
        "status": "ACTIVE",
        "outcome": "PENDING",
        "open_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "close_time": None,
        "exit_price": None,
        "realized_pnl": 0.0,
        "return_pct": 0.0,
        "exit_reason": None,
        "h4_analysis": h4_analysis or "Bullish macro market structure intact.",
        "m15_analysis": m15_analysis or "Tactical pullback with RSI oversold recovery.",
        "reasoning": reasoning or "Multi-timeframe confluence long setup.",
        "screenshot_path": str(screenshot_path) if screenshot_path else None,
        "notes": f"Initial capital allocation with strict risk/reward ratio of {rr_str}."
    }

    entries.insert(0, entry)
    # Keep last 150 journal entries
    entries = entries[:150]
    save_journal_entries(entries)
    return entry


def mark_journal_entry_closed(
    trade_id: str,
    exit_price: float,
    realized_pnl: float,
    exit_reason: str
) -> Optional[Dict[str, Any]]:
    """Updates a journal entry when the trade closes (TP or SL hit)."""
    entries = get_journal_entries()
    target_entry = None

    for entry in entries:
        if entry.get("trade_id") == trade_id:
            target_entry = entry
            break

    if not target_entry:
        return None

    entry_price = float(target_entry.get("entry_price", exit_price))
    volume = float(target_entry.get("volume", 0.01))
    symbol = target_entry.get("symbol", "XAUUSD")

    outcome = "WIN" if realized_pnl > 0.01 else ("LOSS" if realized_pnl < -0.01 else "BREAKEVEN")
    return_pct = round((realized_pnl / max(entry_price * volume * 100.0, 1.0)) * 100.0, 2)

    target_entry["status"] = "CLOSED"
    target_entry["outcome"] = outcome
    target_entry["exit_price"] = round(float(exit_price), 2)
    target_entry["realized_pnl"] = round(float(realized_pnl), 2)
    target_entry["return_pct"] = return_pct
    target_entry["exit_reason"] = exit_reason
    target_entry["close_time"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if outcome == "WIN":
        target_entry["notes"] = f"🎯 Target achieved! {exit_reason}. Full thesis verified with ${realized_pnl:+.2f} profit."
    elif outcome == "LOSS":
        target_entry["notes"] = f"🛑 Capital protection triggered. {exit_reason}. Risk strictly controlled to ${realized_pnl:+.2f}."
    else:
        target_entry["notes"] = f"⚖️ Breakeven exit at market with minimal variance."

    save_journal_entries(entries)
    return target_entry
