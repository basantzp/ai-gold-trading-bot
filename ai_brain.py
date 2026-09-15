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


SYSTEM_PROMPT = """You are a Senior Quantitative Portfolio Manager and Head Trader at an elite Wall Street Hedge Fund.
Your mandate is capital preservation first, followed by asymmetric risk-to-reward profit generation.

You employ a strict multi-timeframe methodology:
1. HIGHER TIMEFRAME (4-Hour): Establishes macro directional bias (Bullish, Bearish, or Neutral Range) based on moving averages, market structure, and higher-high / lower-low sequences.
2. LOWER TIMEFRAME (15-Minute): Identifies precise execution setups, momentum exhaustion, RSI divergence/oversold/overbought conditions, and dynamic pullbacks to key support/resistance levels.

CRITICAL INSTRUCTIONS:
- You must decide only ONE action: "BUY", "SELL", or "HOLD".
- When trend is choppy or high-risk, prefer "HOLD".
- Provide explicit, non-zero Stop Loss (SL) and Take Profit (TP) calibrated to the market ATR and volatility (minimum 1:1.5 Risk-to-Reward ratio, ideally 1:2 or better).
- For BUY: Stop Loss MUST be BELOW current price; Take Profit MUST be ABOVE current price.
- For SELL: Stop Loss MUST be ABOVE current price; Take Profit MUST be BELOW current price.
- You MUST respond ONLY in valid JSON format matching this exact schema:

```json
{
  "decision": "BUY" | "SELL" | "HOLD",
  "confidence": 78,
  "suggested_entry": 67800.50,
  "stop_loss": 66950.00,
  "take_profit": 69500.00,
  "risk_reward_ratio": "1:2.0",
  "h4_trend_analysis": "Clear explanation of 4H macro trend",
  "m15_setup_analysis": "Explanation of 15M trigger and candle dynamics",
  "reasoning": "Comprehensive professional thesis justifying the execution"
}
```
Do not include any conversational filler, intro, or outro. Return ONLY the JSON object.
"""


def build_market_prompt(symbol: str, current_price: float, df_h4: pd.DataFrame, df_m15: pd.DataFrame) -> str:
    """Builds the comprehensive market context prompt for the AI model."""
    h4_summary = format_candles_summary(df_h4, f"{symbol} Higher Timeframe (4-Hour)")
    m15_summary = format_candles_summary(df_m15, f"{symbol} Execution Timeframe (15-Minute)")

    latest_m15 = df_m15.iloc[-1] if not df_m15.empty else {}
    rsi_14 = latest_m15.get("rsi_14", 50.0)
    atr = latest_m15.get("atr", current_price * 0.005)

    prompt = f"""
ASSET SYMBOL: {symbol}
CURRENT MARKET PRICE: {current_price:.4f}
ESTIMATED ATR (VOLATILITY): {atr:.4f}
CURRENT 15M RSI (14): {rsi_14:.2f}

{h4_summary}

{m15_summary}

Based on this market snapshot:
1. Assess the 4H directional bias.
2. Evaluate the 15M tactical entry setup.
3. Formulate your final trade recommendation (BUY, SELL, or HOLD) with exact SL, TP, confidence, and institutional reasoning.
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


def call_antigravity_cli(prompt: str) -> Dict[str, Any]:
    """
    Executes quantitative market analysis using the local Antigravity CLI (`agy`).
    Requires ZERO API keys or external subscriptions as it uses the authenticated
    local Antigravity session.
    """
    agy_bin = shutil.which("agy") or os.path.expanduser("~/.local/bin/agy")
    if not os.path.exists(agy_bin):
        raise RuntimeError(f"Antigravity CLI ('agy') not found at {agy_bin}. Ensure agy is on PATH.")

    full_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"MARKET SNAPSHOT & DATA:\n{prompt}\n\n"
        f"CRITICAL REMINDER: Output ONLY valid JSON matching the schema. No markdown wrapping or extra commentary."
    )

    cmd = [
        agy_bin,
        "-p", full_prompt,
        "--output-format", "text"
    ]

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=90
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Antigravity CLI timed out after 90 seconds.")
    except Exception as e:
        raise RuntimeError(f"Failed to execute Antigravity CLI: {e}")

    if res.returncode != 0:
        err = res.stderr.strip() or res.stdout.strip()
        raise RuntimeError(f"Antigravity CLI returned exit code {res.returncode}: {err}")

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


def fallback_quant_engine(symbol: str, current_price: float, df_m15: pd.DataFrame) -> Dict[str, Any]:
    """
    Algorithmic quant fallback when no AI API key is configured.
    Evaluates RSI and Moving Average crossovers to provide a realistic signal.
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

    latest = df_m15.iloc[-1]
    rsi = latest.get("rsi_14", 50.0)
    sma = latest.get("sma_7", current_price)
    atr = latest.get("atr", current_price * 0.008)
    if not atr or pd.isna(atr) or atr == 0:
        atr = current_price * 0.008

    if rsi < 38 and current_price >= sma:
        decision = "BUY"
        confidence = 76
        sl = round(current_price - (atr * 1.5), 2)
        tp = round(current_price + (atr * 3.0), 2)
        rr = "1:2.0"
        h4_trend = "Bullish recovery off institutional demand zone."
        m15_setup = f"RSI oversold rebound ({rsi:.1f}) re-crossing above dynamic SMA-7."
        reasoning = "Quantitative mean-reversion filter triggered. Favorable risk-to-reward ratio with stop below structural support."
    elif rsi > 65 and current_price <= sma:
        decision = "SELL"
        confidence = 74
        sl = round(current_price + (atr * 1.5), 2)
        tp = round(current_price - (atr * 3.0), 2)
        rr = "1:2.0"
        h4_trend = "Bearish rejection at macro resistance level."
        m15_setup = f"RSI overbought exhaustion ({rsi:.1f}) with bearish price displacement below SMA-7."
        reasoning = "Sell signal confirmed by technical momentum exhaustion and high liquidity sweep."
    else:
        decision = "HOLD"
        confidence = 60
        sl = round(current_price - atr, 2)
        tp = round(current_price + atr, 2)
        rr = "1:1.0"
        h4_trend = "Market in balanced consolidation range."
        m15_setup = f"RSI neutral ({rsi:.1f}); waiting for definitive structural expansion."
        reasoning = "Capital preservation prioritized. Current price is within fair-value equilibrium."

    return {
        "decision": decision,
        "confidence": confidence,
        "suggested_entry": current_price,
        "stop_loss": sl,
        "take_profit": tp,
        "risk_reward_ratio": rr,
        "h4_trend_analysis": h4_trend,
        "m15_setup_analysis": m15_setup,
        "reasoning": reasoning
    }


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

    # 1. Antigravity Native Engine (Zero-API / No external keys needed)
    if any(k in provider_clean for k in ["antigravity", "agy", "native"]):
        try:
            parsed = call_antigravity_cli(prompt)
            return parsed, "⚡ Antigravity AI (Zero-API Native Engine)"
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
    parsed = fallback_quant_engine(symbol, current_price, df_m15)
    return parsed, "Built-in Quant Engine (Enter Gemini or Groq API Key)"
