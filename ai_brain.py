"""
AI Brain: The Quantitative Strategy & Decision Engine.
Acts as a Senior Wall Street Hedge Fund Portfolio Manager.
Analyzes multi-timeframe market data (H4 trend + M15 execution)
using Google Gemini, Groq, or OpenAI, returning
high-precision trading signals (BUY / SELL / HOLD) with SL, TP, and reasoning.
"""

import json
import re
import os
import shutil
import subprocess
import requests
import pandas as pd
from typing import Dict, Any, Tuple

import config
from data_engine import format_candles_summary
from strategy_engine import fuse_quantitative_strategies

# Attempt Groq import
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    Groq = None
    GROQ_AVAILABLE = False

# Attempt OpenAI import
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None
    OPENAI_AVAILABLE = False

# Attempt Google GenAI import
try:
    from google import genai
    from google.genai import types
    GEMINI_SDK_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    GEMINI_SDK_AVAILABLE = False


SYSTEM_PROMPT = """You are a World-Class Quantitative Hedge Fund Portfolio Manager and Robbins World Cup Champion Trader.
Your objective is aggressive capital compounding from $100 up to $10,000 daily, adhering to strict mathematical risk-to-reward asymmetry (minimum 1:2.0 RR).

You combine THREE elite high win-rate quantitative trading methodologies:
1. TRADINGLAB 86% WIN RATE MACD + 200 EMA STRATEGY:
   - Trend Filter: Price > 200 EMA = strictly BUY; Price < 200 EMA = strictly SELL.
   - Dynamic Pullback: Price pulls back to 50 EMA or dynamic support/resistance.
   - MACD Trigger: BUY on MACD line crossing ABOVE signal line WHILE BELOW the zero line. SELL on MACD line crossing BELOW signal line WHILE ABOVE the zero line.
2. DUMB MONEY CONCEPTS (DMC) 80-90% WIN RATE LIQUIDITY SWEEPS:
   - Identify key swing highs and swing lows (liquidity pools / stop clusters).
   - Liquidity Sweep Trap: Price probes outside the key level, triggers retail stops, but wicks reject heavily (>= 30% wick) and closes back INSIDE the level range.
3. ROBBINS WORLD CHAMPION ORDER FLOW & FAILED AUCTION:
   - Value Area High (VAH), Value Area Low (VAL), and Point of Control (POC).
   - Failed Auction: Price pushes to extreme but aggressive volume delta exhausts/absorbs, rotating back to POC.

CRITICAL INSTRUCTIONS:
- You must decide only ONE action: "BUY", "SELL", or "HOLD".
- Look for MULTI-STRATEGY CONFLUENCE (when 2 or 3 strategies align in the same direction, grade as A+ Setup with 85-95% confidence).
- Provide explicit, non-zero Stop Loss (SL) and Take Profit (TP) calibrated to the market ATR and structural swings (minimum 1:2.0 Risk-to-Reward ratio).
- For BUY: Stop Loss MUST be BELOW current price; Take Profit MUST be ABOVE current price.
- For SELL: Stop Loss MUST be ABOVE current price; Take Profit MUST be BELOW current price.
- You MUST respond ONLY in valid JSON format matching this exact schema:

```json
{
  "decision": "BUY" | "SELL" | "HOLD",
  "confidence": 88,
  "suggested_entry": 2750.50,
  "stop_loss": 2742.00,
  "take_profit": 2770.00,
  "risk_reward_ratio": "1:2.3",
  "h4_trend_analysis": "Clear explanation of 4H macro trend",
  "m15_setup_analysis": "Explanation of 15M trigger and candle dynamics",
  "reasoning": "Comprehensive institutional thesis citing confluence of MACD, DMC sweep, and Orderflow"
}
```
Do not include any conversational filler, intro, or outro. Return ONLY the JSON object.
"""


def build_market_prompt(symbol: str, current_price: float, df_h4: pd.DataFrame, df_m15: pd.DataFrame) -> str:
    """Builds the comprehensive market context prompt with quantitative strategy signals for the AI model."""
    h4_summary = format_candles_summary(df_h4, f"{symbol} Higher Timeframe (4-Hour)")
    m15_summary = format_candles_summary(df_m15, f"{symbol} Execution Timeframe (15-Minute)")

    latest_m15 = df_m15.iloc[-1] if not df_m15.empty else {}
    rsi_14 = latest_m15.get("rsi_14", 50.0)
    atr = latest_m15.get("atr", current_price * 0.005)
    ema_200 = latest_m15.get("ema_200", current_price)
    macd_l = latest_m15.get("macd_line", 0.0)
    sig_l = latest_m15.get("signal_line", 0.0)

    # Run Quantitative Strategy Engine Analysis
    quant_signals = fuse_quantitative_strategies(symbol, current_price, df_h4, df_m15)
    s1 = quant_signals["strategies"]["s1_macd_200ema"]
    s2 = quant_signals["strategies"]["s2_dmc_sweep"]
    s3 = quant_signals["strategies"]["s3_orderflow"]

    prompt = f"""
ASSET SYMBOL: {symbol}
CURRENT MARKET PRICE: {current_price:.4f}
200 EMA LEVEL: {ema_200:.4f} ({'BULLISH: Above 200 EMA' if current_price >= ema_200 else 'BEARISH: Below 200 EMA'})
ESTIMATED ATR (VOLATILITY): {atr:.4f}
CURRENT 15M RSI (14): {rsi_14:.2f}
CURRENT 15M MACD: Line={macd_l:.4f}, Signal={sig_l:.4f}

=== ALGORITHMIC QUANTITATIVE STRATEGY METRICS ===
1. TradingLab MACD + 200 EMA: Signal={s1['signal']} | Trend={s1['trend_200']} | MACD={s1['macd_state']}
2. Dumb Money Concepts (DMC): Signal={s2['signal']} | Sweep Status={s2['sweep_type']}
3. Robbins Cup Order Flow: Signal={s3['signal']} | Auction State={s3['auction_state']}
QUANT CONFLUENCE GRADE: {quant_signals['grade']} (Algorithmic Conviction: {quant_signals['confidence']}%)

{h4_summary}

{m15_summary}

Based on this complete market snapshot and the 3 quantitative strategies:
1. Assess the 4H directional trend and 200 EMA bias.
2. Evaluate whether TradingLab MACD, DMC Liquidity Sweep, and Robbins Order Flow provide high-conviction confluence.
3. Formulate your final institutional trade recommendation (BUY, SELL, or HOLD) with exact SL, TP, confidence, and thesis targeting $100 -> $10,000 compounding.
"""
    return prompt



def clean_json_response(raw_text: str) -> Dict[str, Any]:
    """Extracts and parses JSON object from AI model text output."""
    raw_text = raw_text.strip()

    # Try direct parse first
    try:
        return json.loads(raw_text)
    except Exception:
        pass

    # Strip markdown code fences if present
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    # Match outer bracketed JSON directly
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(raw_text[start:end+1])

    raise ValueError(f"Could not parse valid JSON from AI response: {raw_text[:200]}")



AGY_BRIDGE_URL = "http://127.0.0.1:8400"


def call_antigravity_bridge(
    symbol: str, current_price: float, atr: float, rsi_15m: float,
    h4_summary: str, m15_summary: str, ttl: int = 300
) -> Dict[str, Any]:
    """
    ⚡ FAST PATH: Calls the persistent agy bridge server (stream-json mode).
    Requires agy_bridge.py to be running on localhost:8400.
    Response time: ~3-5s (vs 35s cold-start) with in-memory caching.
    """
    payload = {
        "symbol": symbol,
        "current_price": current_price,
        "atr": atr,
        "rsi_15m": rsi_15m,
        "h4_summary": h4_summary,
        "m15_summary": m15_summary,
        "ttl": ttl,
    }
    resp = requests.post(
        f"{AGY_BRIDGE_URL}/analyze",
        json=payload,
        timeout=130
    )
    if resp.status_code != 200:
        raise RuntimeError(f"AGY Bridge error {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def is_bridge_alive() -> bool:
    """Quick health check — does not block if bridge is down."""
    try:
        r = requests.get(f"{AGY_BRIDGE_URL}/health", timeout=1.5)
        return r.status_code == 200 and r.json().get("agy_alive", False)
    except Exception:
        return False


def call_antigravity_cli(prompt: str) -> Dict[str, Any]:
    """
    🔄 FALLBACK PATH: Cold-starts agy -p when bridge is not running.
    Slower (~35s) but zero-dependency — works without the bridge server.
    """
    agy_bin = shutil.which("agy") or os.path.expanduser("~/.local/bin/agy")
    if not os.path.exists(agy_bin):
        raise RuntimeError(f"Antigravity CLI ('agy') not found. Ensure agy is on PATH.")

    full_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"MARKET SNAPSHOT & DATA:\n{prompt}\n\n"
        f"Output ONLY valid JSON. No markdown."
    )
    try:
        res = subprocess.run(
            [agy_bin, "-p", full_prompt, "--output-format", "text",
             "--disable-slash-commands", "--effort", "low"],
            capture_output=True, text=True, timeout=180
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Antigravity CLI timed out after 180s.")
    except Exception as e:
        raise RuntimeError(f"Failed to execute Antigravity CLI: {e}")

    if res.returncode != 0:
        raise RuntimeError(f"agy exit {res.returncode}: {res.stderr.strip() or res.stdout.strip()}")
    return clean_json_response(res.stdout)


def call_gemini_api(api_key: str, model: str, prompt: str) -> Dict[str, Any]:
    """Calls Google Gemini model via official SDK or REST API."""
    clean_model = model.replace("models/", "")
    if not clean_model:
        clean_model = "gemini-2.5-flash"

    # 1. Try official google-genai SDK
    if GEMINI_SDK_AVAILABLE:
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=clean_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.2,
                )
            )
            if response and response.text:
                return clean_json_response(response.text)
        except Exception as e_sdk:
            pass

    # 2. Direct REST API Fallback
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": SYSTEM_PROMPT + "\n\nMARKET SNAPSHOT & DATA:\n" + prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=20)
    if resp.status_code == 200:
        data = resp.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        return clean_json_response(raw_text)
    else:
        raise RuntimeError(f"Gemini API request failed with status {resp.status_code}: {resp.text}")


def call_groq_api(api_key: str, model: str, prompt: str) -> Dict[str, Any]:
    """Calls Groq API with configured model."""
    if not GROQ_AVAILABLE:
        raise RuntimeError("groq package is not installed.")

    client = Groq(api_key=api_key)
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1000,
            response_format={"type": "json_object"}
        )
        raw_response = completion.choices[0].message.content
        return clean_json_response(raw_response)
    except Exception:
        # Retry without json_object constraint
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1000
        )
        raw_response = completion.choices[0].message.content
        return clean_json_response(raw_response)


def fallback_quant_engine(symbol: str, current_price: float, df_m15: pd.DataFrame, df_h4: pd.DataFrame = None) -> Dict[str, Any]:
    """
    Algorithmic quant strategy engine fallback (TradingLab MACD + DMC Sweeps + Robbins Order Flow).
    Evaluates multi-strategy confluence with mathematical precision.
    """
    if df_m15 is None or df_m15.empty:
        return {
            "decision": "HOLD",
            "confidence": 50,
            "suggested_entry": current_price,
            "stop_loss": current_price * 0.98,
            "take_profit": current_price * 1.04,
            "risk_reward_ratio": "1:2.0",
            "h4_trend_analysis": "Consolidation phase detected.",
            "m15_setup_analysis": "Insufficient candle data for high-conviction breakout.",
            "reasoning": "Fallback quant engine recommends HOLD due to neutral momentum and balanced order flow."
        }

    return fuse_quantitative_strategies(symbol, current_price, df_h4, df_m15)


def analyze_market(
    symbol: str,
    current_price: float,
    df_h4: pd.DataFrame,
    df_m15: pd.DataFrame,
    provider: str = "Auto",
    gemini_api_key: str = None,
    groq_api_key: str = None,
    openai_api_key: str = None,
    model_name: str = None
) -> Tuple[Dict[str, Any], str]:
    """
    Main AI Brain entrypoint. Routes analysis to Google Gemini, Groq, or OpenAI.
    """
    prompt = build_market_prompt(symbol, current_price, df_h4, df_m15)

    g_key = (gemini_api_key or config.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")).strip()
    groq_key = (groq_api_key or config.GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")).strip()
    oa_key = (openai_api_key or config.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")).strip()

    provider_clean = (provider or "Auto").lower()

    # ── 1. Antigravity Native Engine (Zero-API) ──────────────────
    if any(k in provider_clean for k in ["antigravity", "agy", "native"]):
        # Extract structured fields for the bridge endpoint
        latest_m15 = df_m15.iloc[-1] if (df_m15 is not None and not df_m15.empty) else {}
        atr_val    = float(latest_m15.get("atr", current_price * 0.005) or current_price * 0.005)
        rsi_val    = float(latest_m15.get("rsi_14", 50.0) or 50.0)
        h4_sum     = format_candles_summary(df_h4, f"{symbol} Higher Timeframe (4-Hour)")
        m15_sum    = format_candles_summary(df_m15, f"{symbol} Execution Timeframe (15-Minute)")

        # ⚡ FAST PATH — bridge (stream-json persistent process, ~3-5s)
        if is_bridge_alive():
            try:
                parsed = call_antigravity_bridge(
                    symbol=symbol, current_price=current_price,
                    atr=atr_val, rsi_15m=rsi_val,
                    h4_summary=h4_sum, m15_summary=m15_sum
                )
                elapsed = parsed.pop("_elapsed_s", "?")
                src     = parsed.pop("_source", "bridge")
                label   = f"⚡ Antigravity AI — Bridge ({elapsed}s, {src})"
                return parsed, label
            except Exception as e:
                print(f"[AGY-BRIDGE] error: {e} — falling back to CLI")

        # 🔄 SLOW FALLBACK — cold subprocess (-p mode, ~35-180s)
        try:
            print("[AGY] Bridge not available — using cold CLI (start agy_bridge.py for fast mode)")
            parsed = call_antigravity_cli(prompt)
            return parsed, "⚡ Antigravity AI — CLI Fallback (start bridge for fast mode)"
        except Exception as e:
            print(f"Antigravity CLI error: {e}")
            if provider_clean != "auto":
                raise


    # 2. Google Gemini Provider
    if provider_clean in ["gemini", "google gemini"] or (provider_clean == "auto" and g_key):
        if g_key:
            try:
                g_model = model_name if (model_name and "gemini" in model_name) else (config.GEMINI_MODEL or "gemini-2.5-flash")
                parsed = call_gemini_api(g_key, g_model, prompt)
                return parsed, f"Google Gemini ({g_model})"
            except Exception as e:
                print(f"Gemini error: {e}")
                if provider_clean != "auto":
                    raise

    # 2. Groq Provider
    if provider_clean in ["groq", "groq cloud"] or (provider_clean == "auto" and groq_key):
        if groq_key:
            try:
                gr_model = model_name if (model_name and "gemini" not in model_name and "gpt" not in model_name) else (config.GROQ_MODEL or "qwen/qwen3.8-27b")
                parsed = call_groq_api(groq_key, gr_model, prompt)
                return parsed, f"Groq AI ({gr_model})"
            except Exception as e:
                print(f"Groq error: {e}")
                if provider_clean != "auto":
                    raise

    # 3. OpenAI Provider
    if provider_clean in ["openai"] or (provider_clean == "auto" and oa_key):
        if oa_key and OPENAI_AVAILABLE:
            try:
                client = OpenAI(api_key=oa_key)
                oa_model = model_name or config.OPENAI_MODEL or "gpt-4o-mini"
                completion = client.chat.completions.create(
                    model=oa_model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=800,
                    response_format={"type": "json_object"}
                )
                raw_response = completion.choices[0].message.content
                parsed = clean_json_response(raw_response)
                return parsed, f"OpenAI ({oa_model})"
            except Exception:
                pass

    # 4. Fallback Rule-Based Quant Strategy
    parsed = fallback_quant_engine(symbol, current_price, df_m15, df_h4)
    return parsed, "Quantitative Strategy Fusion Engine (TradingLab MACD + DMC + Robbins Orderflow)"

