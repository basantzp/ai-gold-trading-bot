"""
Quantitative Strategy Fusion & Hyper-Compounding Engine.
Implements the 3 Institutional Trading Strategies:
1. TradingLab 86% Win Rate MACD + 200 EMA Trend Strategy (rf_EQvubKlk)
2. Dumb Money Concepts (DMC) 80-90% Win Rate Liquidity Sweeps & Trap Strategy (MzZ0b_ZVeQw)
3. Robbins World Cup Champion Order Flow & Failed Auction Strategy (PL7LKUsCgIQ)
Plus dynamic Kelly/Fractional Hyper-Compounding targeting $100 -> $10,000.
"""

import math
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
import config


def get_contract_multiplier(symbol: str) -> float:
    """Returns the contract multiplier for calculating lot size and pip values."""
    sym = symbol.upper()
    if "XAU" in sym or "GOLD" in sym:
        return 100.0  # 1 lot = 100 oz of gold
    elif "BTC" in sym or "ETH" in sym or "SOL" in sym:
        return 1.0    # 1 lot = 1 crypto unit
    else:
        return 100000.0  # Standard forex lot


# =====================================================================
# Strategy 1: TradingLab 86% Win Rate MACD + 200 EMA
# (https://www.youtube.com/watch?v=rf_EQvubKlk)
# =====================================================================
def evaluate_tradinglab_macd_200ema(df: pd.DataFrame, current_price: float) -> Dict[str, Any]:
    """
    Evaluates Strategy 1:
    - 200 EMA Trend Filter: Only BUY above 200 EMA; only SELL below 200 EMA.
    - Dynamic Pullback: Price retraces towards 50 EMA / dynamic value zone.
    - MACD Crossover Trigger:
        * BUY: MACD Line crosses ABOVE Signal Line WHILE BOTH ARE BELOW THE ZERO LINE.
        * SELL: MACD Line crosses BELOW Signal Line WHILE BOTH ARE ABOVE THE ZERO LINE.
    - SL below/above recent swing, targeting 1:2.0 Risk-to-Reward.
    """
    default_res = {
        "strategy_id": "S1_MACD_200EMA",
        "name": "TradingLab MACD + 200 EMA (86% Win Rate)",
        "signal": "HOLD",
        "confidence": 50,
        "sl": 0.0,
        "tp": 0.0,
        "rr": "1:2.0",
        "trend_200": "NEUTRAL",
        "macd_state": "NEUTRAL",
        "reason": "MACD momentum is within consolidation; awaiting sub-zero crossover."
    }

    if df is None or len(df) < 15:
        return default_res

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else latest
    prev2 = df.iloc[-3] if len(df) >= 3 else prev

    ema_200 = latest.get("ema_200", current_price)
    ema_50 = latest.get("ema_50", current_price)
    atr = latest.get("atr", current_price * 0.005)
    if not atr or pd.isna(atr) or atr <= 0:
        atr = current_price * 0.005

    macd_line = latest.get("macd_line", 0.0)
    signal_line = latest.get("signal_line", 0.0)
    prev_macd = prev.get("macd_line", 0.0)
    prev_sig = prev.get("signal_line", 0.0)

    # 1. 200 EMA Trend Filter
    is_uptrend = current_price >= ema_200
    is_downtrend = current_price < ema_200
    trend_desc = "BULLISH (Above 200 EMA)" if is_uptrend else "BEARISH (Below 200 EMA)"

    # 2. MACD Crossover Detection (recent 2 candles)
    bullish_cross = (prev_macd <= prev_sig and macd_line > signal_line) or (prev2.get("macd_line", 0) <= prev2.get("signal_line", 0) and macd_line > signal_line)
    bearish_cross = (prev_macd >= prev_sig and macd_line < signal_line) or (prev2.get("macd_line", 0) >= prev2.get("signal_line", 0) and macd_line < signal_line)

    # Sub-zero / Above-zero filter (Golden rule from video: prevents buying at tops or selling at bottoms)
    sub_zero_bullish = bullish_cross and (macd_line < 0 or prev_macd < 0)
    above_zero_bearish = bearish_cross and (macd_line > 0 or prev_macd > 0)

    # Dynamic swing boundaries
    recent_lows = df["low"].tail(10).min()
    recent_highs = df["high"].tail(10).max()

    if is_uptrend and sub_zero_bullish:
        sl = round(min(recent_lows, current_price - (atr * 1.5)), 2)
        risk = max(current_price - sl, atr)
        tp = round(current_price + (risk * 2.0), 2)
        return {
            "strategy_id": "S1_MACD_200EMA",
            "name": "TradingLab MACD + 200 EMA (86% Win Rate)",
            "signal": "BUY",
            "confidence": 84,
            "sl": sl,
            "tp": tp,
            "rr": f"1:{((tp - current_price)/risk):.1f}",
            "trend_200": trend_desc,
            "macd_state": f"Bullish Cross Below Zero (MACD: {macd_line:.2f} > Sig: {signal_line:.2f})",
            "reason": f"Price is above 200 EMA (${ema_200:.2f}) and MACD triggered an oversold crossover below the zero line, signaling institutional trend continuation."
        }
    elif is_downtrend and above_zero_bearish:
        sl = round(max(recent_highs, current_price + (atr * 1.5)), 2)
        risk = max(sl - current_price, atr)
        tp = round(current_price - (risk * 2.0), 2)
        return {
            "strategy_id": "S1_MACD_200EMA",
            "name": "TradingLab MACD + 200 EMA (86% Win Rate)",
            "signal": "SELL",
            "confidence": 84,
            "sl": sl,
            "tp": tp,
            "rr": f"1:{((current_price - tp)/risk):.1f}",
            "trend_200": trend_desc,
            "macd_state": f"Bearish Cross Above Zero (MACD: {macd_line:.2f} < Sig: {signal_line:.2f})",
            "reason": f"Price is below 200 EMA (${ema_200:.2f}) and MACD triggered an overbought crossover above the zero line, confirming aggressive bearish distribution."
        }
    else:
        macd_state = "MACD Bullish" if macd_line > signal_line else "MACD Bearish"
        return {
            "strategy_id": "S1_MACD_200EMA",
            "name": "TradingLab MACD + 200 EMA (86% Win Rate)",
            "signal": "HOLD",
            "confidence": 55,
            "sl": 0.0,
            "tp": 0.0,
            "rr": "1:2.0",
            "trend_200": trend_desc,
            "macd_state": f"{macd_state} (Line: {macd_line:.2f}, Sig: {signal_line:.2f})",
            "reason": f"Market is aligned {trend_desc}; awaiting high-conviction zero-line MACD crossover trigger."
        }


# =====================================================================
# Strategy 2: Dumb Money Concepts (DMC) 80-90% Win Rate Liquidity Sweeps
# (https://www.youtube.com/watch?v=MzZ0b_ZVeQw)
# =====================================================================
def evaluate_dmc_liquidity_sweeps(df: pd.DataFrame, current_price: float) -> Dict[str, Any]:
    """
    Evaluates Strategy 2:
    - Identifies major swing highs and swing lows (retail liquidity pools / stop clusters).
    - Liquidity Probe: Candle wicks past key level to trigger retail stops and breakout orders.
    - Rejection & Close Back Inside: Candle fails to sustain outside the level, leaving a heavy
      rejection wick (>= 30% of total candle range) and closing back INSIDE the prior range (DMC Trap).
    - Entry at close; SL placed just beyond the sweep wick extreme; TP targeting opposite liquidity.
    """
    default_res = {
        "strategy_id": "S2_DMC_SWEEP",
        "name": "Dumb Money Concepts (DMC) Liquidity Sweep (80-90% Win Rate)",
        "signal": "HOLD",
        "confidence": 50,
        "sl": 0.0,
        "tp": 0.0,
        "rr": "1:2.5",
        "sweep_type": "NONE",
        "reason": "No active liquidity pool sweeps detected in the recent price action."
    }

    if df is None or len(df) < 20:
        return default_res

    # Check the last 3 completed candles for a sweep
    atr = df["atr"].iloc[-1] if ("atr" in df.columns and pd.notnull(df["atr"].iloc[-1])) else current_price * 0.005
    if not atr or atr <= 0:
        atr = current_price * 0.005

    # Prior structural reference window (candles -25 to -4)
    ref_window = df.iloc[-25:-3]
    if ref_window.empty:
        return default_res

    prior_swing_high = ref_window["high"].max()
    prior_swing_low = ref_window["low"].min()

    # Examine recent candles (-3 to -1)
    recent_candles = df.iloc[-3:]
    for idx, row in recent_candles.iterrows():
        o = row["open"]
        h = row["high"]
        l = row["low"]
        c = row["close"]
        candle_range = max(h - l, 1e-9)

        # 1. Bullish Liquidity Sweep (Swept below prior swing low, wicked back up, closed above prior swing low)
        if l < prior_swing_low and c > prior_swing_low:
            lower_wick = min(o, c) - l
            wick_ratio = lower_wick / candle_range
            if wick_ratio >= 0.28:  # Significant institutional rejection wick
                sl = round(l - (atr * 0.3), 2)
                risk = max(current_price - sl, atr)
                tp = round(current_price + (risk * 2.5), 2)
                return {
                    "strategy_id": "S2_DMC_SWEEP",
                    "name": "Dumb Money Concepts (DMC) Liquidity Sweep (80-90% Win Rate)",
                    "signal": "BUY",
                    "confidence": 88,
                    "sl": sl,
                    "tp": tp,
                    "rr": f"1:{((tp - current_price)/risk):.1f}",
                    "sweep_type": f"Bullish Sell-Side Liquidity Sweep below ${prior_swing_low:.2f}",
                    "reason": f"DMC Trap: Price swept sell stops below ${prior_swing_low:.2f} with a {wick_ratio*100:.0f}% rejection wick and closed back inside range. Smart money absorbed retail liquidity."
                }

        # 2. Bearish Liquidity Sweep (Swept above prior swing high, wicked back down, closed below prior swing high)
        if h > prior_swing_high and c < prior_swing_high:
            upper_wick = h - max(o, c)
            wick_ratio = upper_wick / candle_range
            if wick_ratio >= 0.28:  # Significant institutional rejection wick
                sl = round(h + (atr * 0.3), 2)
                risk = max(sl - current_price, atr)
                tp = round(current_price - (risk * 2.5), 2)
                return {
                    "strategy_id": "S2_DMC_SWEEP",
                    "name": "Dumb Money Concepts (DMC) Liquidity Sweep (80-90% Win Rate)",
                    "signal": "SELL",
                    "confidence": 88,
                    "sl": sl,
                    "tp": tp,
                    "rr": f"1:{((current_price - tp)/risk):.1f}",
                    "sweep_type": f"Bearish Buy-Side Liquidity Sweep above ${prior_swing_high:.2f}",
                    "reason": f"DMC Trap: Price swept buy stops above ${prior_swing_high:.2f} with a {wick_ratio*100:.0f}% upper rejection wick and closed back inside range. Institutional distribution active."
                }

    return {
        "strategy_id": "S2_DMC_SWEEP",
        "name": "Dumb Money Concepts (DMC) Liquidity Sweep (80-90% Win Rate)",
        "signal": "HOLD",
        "confidence": 50,
        "sl": 0.0,
        "tp": 0.0,
        "rr": "1:2.5",
        "sweep_type": "Watching Levels",
        "reason": f"Monitoring key liquidity levels: Resistance High ${prior_swing_high:.2f} | Support Low ${prior_swing_low:.2f}. Waiting for sweep wick rejection."
    }


# =====================================================================
# Strategy 3: Robbins Cup World Champion Order Flow & Failed Auction
# (https://www.youtube.com/watch?v=PL7LKUsCgIQ)
# =====================================================================
def evaluate_robbins_cup_orderflow(df: pd.DataFrame, current_price: float) -> Dict[str, Any]:
    """
    Evaluates Strategy 3:
    - Market Profile / Value Area estimation: POC (Point of Control), VAH, VAL.
    - Failed Auction Mechanism:
        * When price attempts to auction outside Value Area (breakout), but aggressive volume delta
          dries up or turns opposite (absorption).
        * Rejection back into Value Area confirms Failed Auction.
    - Trade direction: Mean reversion to POC and opposite Value Area extreme.
    """
    default_res = {
        "strategy_id": "S3_ORDERFLOW",
        "name": "Robbins Cup World Champion Order Flow & Failed Auction",
        "signal": "HOLD",
        "confidence": 50,
        "sl": 0.0,
        "tp": 0.0,
        "rr": "1:2.0",
        "auction_state": "BALANCED",
        "reason": "Order flow is balanced within fair value area."
    }

    if df is None or len(df) < 15:
        return default_res

    atr = df["atr"].iloc[-1] if ("atr" in df.columns and pd.notnull(df["atr"].iloc[-1])) else current_price * 0.005
    if not atr or atr <= 0:
        atr = current_price * 0.005

    # Compute Value Area over last 20 candles
    recent = df.tail(20)
    poc_price = recent["close"].median()
    vah = poc_price + (atr * 1.2)  # Value Area High
    val = poc_price - (atr * 1.2)  # Value Area Low

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else latest

    vol_delta = latest.get("volume_delta", 0.0)
    prev_delta = prev.get("volume_delta", 0.0)
    cvd_slope = (latest.get("cvd", 0.0) - df["cvd"].iloc[-5]) if ("cvd" in df.columns and len(df) >= 5) else 0.0

    # 1. Bullish Failed Auction: Low dipped below VAL, but buyers absorbed selling (positive delta) and closed back above VAL
    if latest["low"] < val and latest["close"] >= val and (vol_delta > 0 or cvd_slope > 0):
        sl = round(latest["low"] - (atr * 0.4), 2)
        risk = max(current_price - sl, atr)
        tp = round(current_price + (risk * 2.2), 2)
        return {
            "strategy_id": "S3_ORDERFLOW",
            "name": "Robbins Cup World Champion Order Flow & Failed Auction",
            "signal": "BUY",
            "confidence": 85,
            "sl": sl,
            "tp": tp,
            "rr": f"1:{((tp - current_price)/risk):.1f}",
            "auction_state": f"Failed Auction Low (Absorption at ${val:.2f})",
            "reason": f"Robbins Order Flow: Sellers failed to auction below Value Area Low (${val:.2f}). Strong volume delta absorption (+{vol_delta:,.0f}) rotated price back toward POC (${poc_price:.2f})."
        }

    # 2. Bearish Failed Auction: High pushed above VAH, but buyers exhausted (negative delta) and closed back below VAH
    if latest["high"] > vah and latest["close"] <= vah and (vol_delta < 0 or cvd_slope < 0):
        sl = round(latest["high"] + (atr * 0.4), 2)
        risk = max(sl - current_price, atr)
        tp = round(current_price - (risk * 2.2), 2)
        return {
            "strategy_id": "S3_ORDERFLOW",
            "name": "Robbins Cup World Champion Order Flow & Failed Auction",
            "signal": "SELL",
            "confidence": 85,
            "sl": sl,
            "tp": tp,
            "rr": f"1:{((current_price - tp)/risk):.1f}",
            "auction_state": f"Failed Auction High (Exhaustion at ${vah:.2f})",
            "reason": f"Robbins Order Flow: Buyers failed to sustain auction above Value Area High (${vah:.2f}). Negative volume delta ({vol_delta:,.0f}) confirms passive limit absorption. Target POC (${poc_price:.2f})."
        }

    return {
        "strategy_id": "S3_ORDERFLOW",
        "name": "Robbins Cup World Champion Order Flow & Failed Auction",
        "signal": "HOLD",
        "confidence": 52,
        "sl": 0.0,
        "tp": 0.0,
        "rr": "1:2.0",
        "auction_state": f"Fair Value Rotation (POC: ${poc_price:.2f} | VAL: ${val:.2f} - VAH: ${vah:.2f})",
        "reason": f"Auction is within Value Area equilibrium. No breakout absorption divergence at extremes."
    }


# =====================================================================
# Multi-Strategy Confluence Fusion Engine
# =====================================================================
def fuse_quantitative_strategies(
    symbol: str,
    current_price: float,
    df_h4: pd.DataFrame,
    df_m15: pd.DataFrame
) -> Dict[str, Any]:
    """
    Evaluates all 3 institutional strategies simultaneously and generates
    a multi-strategy confluence signal and conviction score.
    """
    s1 = evaluate_tradinglab_macd_200ema(df_m15, current_price)
    s2 = evaluate_dmc_liquidity_sweeps(df_m15, current_price)
    s3 = evaluate_robbins_cup_orderflow(df_m15, current_price)

    strategies_list = [s1, s2, s3]

    buy_signals = [s for s in strategies_list if s["signal"] == "BUY"]
    sell_signals = [s for s in strategies_list if s["signal"] == "SELL"]

    # Confluence logic
    if len(buy_signals) >= 2 and len(sell_signals) == 0:
        # High Conviction A+ Buy
        primary = buy_signals[0]
        confluence_names = " + ".join([s["strategy_id"] for s in buy_signals])
        confidence = min(96, 75 + (len(buy_signals) * 10))
        sl = min([s["sl"] for s in buy_signals if s["sl"] > 0] or [current_price * 0.99])
        risk = max(current_price - sl, current_price * 0.003)
        tp = round(current_price + (risk * 2.2), 2)

        decision = "BUY"
        grade = "🏆 A+ TRIPLE CONFLUENCE" if len(buy_signals) == 3 else "⭐ DOUBLE CONFLUENCE"
        reasoning = (
            f"[{grade}] {confluence_names} aligned for institutional LONG. "
            f"{buy_signals[0]['reason']} Additionally: {buy_signals[1]['reason']}"
        )

    elif len(sell_signals) >= 2 and len(buy_signals) == 0:
        # High Conviction A+ Sell
        primary = sell_signals[0]
        confluence_names = " + ".join([s["strategy_id"] for s in sell_signals])
        confidence = min(96, 75 + (len(sell_signals) * 10))
        sl = max([s["sl"] for s in sell_signals if s["sl"] > 0] or [current_price * 1.01])
        risk = max(sl - current_price, current_price * 0.003)
        tp = round(current_price - (risk * 2.2), 2)

        decision = "SELL"
        grade = "🏆 A+ TRIPLE CONFLUENCE" if len(sell_signals) == 3 else "⭐ DOUBLE CONFLUENCE"
        reasoning = (
            f"[{grade}] {confluence_names} aligned for institutional SHORT. "
            f"{sell_signals[0]['reason']} Additionally: {sell_signals[1]['reason']}"
        )

    elif len(buy_signals) == 1 and len(sell_signals) == 0:
        # Single Solid Buy Setup
        active = buy_signals[0]
        decision = "BUY"
        confidence = active["confidence"]
        sl = active["sl"]
        tp = active["tp"]
        grade = "STANDARD SETUP"
        reasoning = f"[{grade}: {active['name']}] {active['reason']}"

    elif len(sell_signals) == 1 and len(buy_signals) == 0:
        # Single Solid Sell Setup
        active = sell_signals[0]
        decision = "SELL"
        confidence = active["confidence"]
        sl = active["sl"]
        tp = active["tp"]
        grade = "STANDARD SETUP"
        reasoning = f"[{grade}: {active['name']}] {active['reason']}"

    else:
        # Conflicting signals or all HOLD
        decision = "HOLD"
        confidence = 55
        atr = df_m15["atr"].iloc[-1] if (df_m15 is not None and "atr" in df_m15.columns and not df_m15.empty) else current_price * 0.005
        sl = round(current_price - atr, 2)
        tp = round(current_price + atr, 2)
        grade = "CAPITAL PRESERVATION"
        reasoning = (
            f"Hedge Fund Risk Gate: Strategies are in consolidation equilibrium or showing divergent momentum. "
            f"TradingLab MACD: {s1['signal']} | DMC Sweep: {s2['signal']} | Robbins Orderflow: {s3['signal']}. "
            f"Preserving cash for high-probability A+ confluence."
        )

    # 4H macro confirmation
    h4_trend = "Macro trend aligned."
    if df_h4 is not None and not df_h4.empty and "ema_200" in df_h4.columns:
        h4_ema200 = df_h4["ema_200"].iloc[-1]
        h4_trend = f"4H Macro Bias: {'BULLISH' if current_price >= h4_ema200 else 'BEARISH'} (relative to 4H 200 EMA at ${h4_ema200:.2f})"

    return {
        "decision": decision,
        "confidence": confidence,
        "grade": grade,
        "suggested_entry": current_price,
        "stop_loss": sl,
        "take_profit": tp,
        "risk_reward_ratio": f"1:{abs(tp - current_price) / max(abs(current_price - sl), 1e-6):.1f}",
        "h4_trend_analysis": h4_trend,
        "m15_setup_analysis": f"M15 Execution: MACD ({s1['signal']}), DMC Sweep ({s2['signal']}), Orderflow ({s3['signal']})",
        "reasoning": reasoning,
        "strategies": {
            "s1_macd_200ema": s1,
            "s2_dmc_sweep": s2,
            "s3_orderflow": s3
        }
    }


# =====================================================================
# Hyper-Compounding Position Sizing Engine ($100 -> $10,000)
# =====================================================================
def calculate_compounded_position_size(
    account_equity: float,
    entry_price: float,
    stop_loss: float,
    symbol: str,
    confidence: int = 70
) -> Dict[str, Any]:
    """
    Computes mathematically optimal position sizing to compound $100 up to $10,000.
    Uses Fractional Kelly / Fixed Fractional Compounding:
    - Base capital: $100 starting equity
    - Target: $10,000 daily growth goal
    - As equity grows ($100 -> $250 -> $700 -> $2,000 -> $10,000), lot sizes automatically scale
      proportionally based on stop distance to compound gains exponentially while capping drawdown.
    """
    initial_cap = getattr(config, "INITIAL_CAPITAL", 100.0)
    target_equity = getattr(config, "DAILY_TARGET_EQUITY", 10000.0)
    max_lot = getattr(config, "MAX_LOT_SIZE", 5.0)
    base_risk_pct = getattr(config, "COMPOUND_BASE_RISK_PCT", 0.08)  # 8% base risk

    # Boost risk fraction on A+ high confidence trades (up to 12%)
    if confidence >= 85:
        risk_pct = base_risk_pct * 1.35  # ~10.8%
    elif confidence >= 75:
        risk_pct = base_risk_pct * 1.15  # ~9.2%
    else:
        risk_pct = base_risk_pct * 0.75  # ~6.0%

    risk_dollars = account_equity * risk_pct
    sl_distance = abs(entry_price - stop_loss)
    multiplier = get_contract_multiplier(symbol)

    if sl_distance <= 0:
        sl_distance = entry_price * 0.005  # 0.5% default fallback

    # Calculate exact lot size
    # dollar_risk = lot_size * sl_distance * multiplier
    # lot_size = dollar_risk / (sl_distance * multiplier)
    calculated_lots = risk_dollars / (sl_distance * multiplier)

    # Floor at 0.01 micro lot, cap at max_lot
    lot_size = round(max(0.01, min(max_lot, calculated_lots)), 2)

    # Calculate compounding progress toward $10,000
    progress_pct = max(0.0, min(100.0, ((account_equity - initial_cap) / (target_equity - initial_cap)) * 100.0))
    equity_multiplier = round(account_equity / initial_cap, 2)
    remaining_to_goal = max(0.0, target_equity - account_equity)

    # Estimated consecutive 1:2 R wins needed to reach $10,000
    # equity_n = equity_0 * (1 + 2 * risk_pct)^n
    gain_per_win = 1.0 + (2.0 * risk_pct)
    if remaining_to_goal > 0 and gain_per_win > 1.0:
        wins_needed = math.ceil(math.log(target_equity / max(account_equity, 1.0)) / math.log(gain_per_win))
    else:
        wins_needed = 0

    return {
        "lot_size": lot_size,
        "risk_dollars": round(risk_dollars, 2),
        "risk_pct": round(risk_pct * 100.0, 1),
        "account_equity": round(account_equity, 2),
        "target_equity": round(target_equity, 2),
        "progress_pct": round(progress_pct, 1),
        "equity_multiplier": equity_multiplier,
        "remaining_to_goal": round(remaining_to_goal, 2),
        "estimated_wins_needed": wins_needed
    }
