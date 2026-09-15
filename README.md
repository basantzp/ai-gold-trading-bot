# ⚡ AI Gold Trading Bot — Autonomous MT5 XAUUSD Hedge Fund Engine

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-red.svg)](https://streamlit.io)
[![MT5](https://img.shields.io/badge/Broker-MetaTrader5-brightgreen.svg)](https://metatrader5.com)
[![Zero-API](https://img.shields.io/badge/Antigravity-Zero--API%20Mode-gold.svg)](#)

An end-to-end autonomous algorithmic trading system built for **Gold (XAUUSD)** — inspired by institutional Wall Street hedge funds. Connects to **MetaTrader 5 (MT5)**, fetches multi-timeframe candlestick data, submits market structure to an **AI Brain**, and automatically executes calculated trade orders with institutional Stop Loss (SL) and Take Profit (TP) parameters.

---

## 🥇 Supported Assets

| Asset | Symbol | Source |
|-------|--------|--------|
| **Gold** (default) | `XAUUSD` | MT5 / Yahoo Finance (`GC=F`) |
| Bitcoin | `BTCUSD` | MT5 / Binance |
| Ethereum | `ETHUSD` | MT5 / Binance |
| Forex Pairs | `EURUSD`, `GBPUSD`… | MT5 / Yahoo Finance |
| Any MT5 Symbol | `SYMBOL` | MT5 Live |

---

## 🏛️ Architecture (4 Core Engines)

```mermaid
flowchart TD
    subgraph Data Layer
        A1["MetaTrader 5 Terminal (Windows)"] -->|Candles H4 & M15| B["Data Engine (data_engine.py)"]
        A2["Live Web Feed (Yahoo/Binance Fallback)"] -->|Real-time OHLCV| B
    end

    subgraph Intelligence Layer
        B -->|Multi-Timeframe Market Structure| C["AI Brain (ai_brain.py)"]
        C -->|⚡ Antigravity Zero-API (primary)| D["Quantitative Reasoning & Decision"]
        C -->|Groq / Gemini / OpenAI fallback| D
    end

    subgraph Execution & Monitoring
        D -->|BUY / SELL / HOLD + SL + TP| E["Execution Engine (execution.py)"]
        E -->|order_send| A1
        E -->|Trade History Log| F["Trade Ledger (trade_history.json)"]
        B & D & E --> G["Streamlit Terminal Dashboard (app.py)"]
    end
```

---

## 🧠 AI Brain Providers

| Provider | API Key Required | Quality | Notes |
|----------|:----------------:|---------|-------|
| **⚡ Antigravity AI** | ❌ **Zero-API** | ⭐⭐⭐⭐⭐ | Uses local `agy` CLI session |
| Google Gemini | ✅ (Free) | ⭐⭐⭐⭐⭐ | gemini-2.5-flash |
| Groq Cloud | ✅ (Free) | ⭐⭐⭐⭐ | Llama 3.3 / Qwen 3.8 |
| OpenAI | ✅ (Paid) | ⭐⭐⭐⭐ | GPT-4o-mini |
| **Built-in Quant** | ❌ None | ⭐⭐⭐ | RSI/SMA algorithmic fallback |

### ⚡ Antigravity Zero-API Mode (No API Keys!)
If you have [Antigravity (`agy`)](https://antigravity.ai) installed and authenticated locally, select **"⚡ Antigravity AI (Zero-API / Native)"** in the sidebar — **no API keys or subscription needed**.

---

## 📊 Technical Indicators
- **RSI (14)** — momentum exhaustion & divergence
- **SMA (7) & EMA (14)** — dynamic trend positioning
- **ATR** — volatility-based SL/TP scaling

---

## 📂 Project Structure

```
ai-gold-trading-bot/
├── config.py           # Central configuration (MT5 credentials, API keys, defaults)
├── data_engine.py      # Market data extraction & technical indicator engine
├── ai_brain.py         # Multi-LLM quantitative strategy brain (Antigravity/Gemini/Groq/OpenAI)
├── execution.py        # MT5 trade dispatcher & paper trading simulation
├── app.py              # Streamlit interactive hedge fund terminal
├── test_bot.py         # End-to-end CLI verification test suite
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
└── .env                # Local credentials (git-ignored — never committed)
```

---

## 🚀 Quick Setup

```bash
# 1. Clone
git clone https://github.com/basantzp/ai-gold-trading-bot.git
cd ai-gold-trading-bot

# 2. Create virtual environment
uv venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt

# 3. Configure (copy template)
cp .env.example .env
# Edit .env with your MT5 credentials and optionally API keys

# 4. Launch dashboard
streamlit run app.py
```

> **Zero-API option**: If you have `agy` (Antigravity) installed and logged in, no `.env` changes needed — just select **⚡ Antigravity AI** in the sidebar.

---

## ⚙️ Configuration (`.env`)

```env
# MT5 (Windows only — Linux runs in paper/simulation mode)
MT5_LOGIN=YOUR_ACCOUNT_NUMBER
MT5_PASSWORD=YOUR_PASSWORD
MT5_SERVER=YourBroker-Server

# AI Brain (all optional — Antigravity Zero-API needs none)
GEMINI_API_KEY=
GROQ_API_KEY=

# Trading defaults
DEFAULT_SYMBOL=XAUUSD
DEFAULT_LOT_SIZE=0.01
```

---

## 🎯 AI Decision Output

```json
{
  "decision": "BUY",
  "confidence": 82,
  "suggested_entry": 2650.50,
  "stop_loss": 2638.00,
  "take_profit": 2675.00,
  "risk_reward_ratio": "1:2.0",
  "h4_trend_analysis": "Bullish expansion above key institutional demand zone...",
  "m15_setup_analysis": "RSI oversold rebound at dynamic support...",
  "reasoning": "High-conviction continuation setup with asymmetric R:R..."
}
```

---

## ⚠️ Disclaimer

> This software is for **educational and research purposes only**. It is NOT financial advice. Trading involves substantial risk of loss. Always test in paper/demo mode before using real capital.

---

## 📜 License

MIT License — Free to use, modify, and distribute.
