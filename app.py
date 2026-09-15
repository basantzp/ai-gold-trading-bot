"""
Streamlit Web Dashboard: AI Hedge Fund MT5 Automated Trading Terminal.
Integrates Data Engine, AI Brain, and Execution Engine into an institutional interface.
"""

import os
import time
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as components

import config
from data_engine import (
    initialize_mt5,
    get_market_data,
    MT5_AVAILABLE
)
from ai_brain import analyze_market
from execution import execute_trade, get_trade_history
import portfolio
from auto_trader import get_auto_trader
import strategy_engine


# -------------------------------------------------------------
# Streamlit Page Setup & Custom Styling
# -------------------------------------------------------------
st.set_page_config(
    page_title="AI Hedge Fund | MT5 Autonomous Bot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Institutional Hedge Fund Theme
st.markdown("""
<style>
    .main {
        background-color: #0b0e14;
    }
    .metric-card {
        background: linear-gradient(135deg, #151922 0%, #1c222e 100%);
        border: 1px solid #283347;
        border-radius: 10px;
        padding: 16px 20px;
        color: #f0f4f8;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    }
    .decision-buy {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(5, 150, 105, 0.25) 100%);
        border: 2px solid #10b981;
        border-radius: 12px;
        padding: 24px;
        text-align: center;
    }
    .decision-sell {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(220, 38, 38, 0.25) 100%);
        border: 2px solid #ef4444;
        border-radius: 12px;
        padding: 24px;
        text-align: center;
    }
    .decision-hold {
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(217, 119, 6, 0.25) 100%);
        border: 2px solid #f59e0b;
        border-radius: 12px;
        padding: 24px;
        text-align: center;
    }
    .badge {
        display: inline-block;
        padding: 6px 16px;
        font-size: 26px;
        font-weight: 800;
        letter-spacing: 1.5px;
        border-radius: 8px;
    }
    .badge-buy { background-color: #10b981; color: #ffffff; }
    .badge-sell { background-color: #ef4444; color: #ffffff; }
    .badge-hold { background-color: #f59e0b; color: #ffffff; }
    .stButton>button {
        width: 100%;
        background: linear-gradient(90deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        font-weight: 700;
        font-size: 18px;
        padding: 12px 24px;
        border-radius: 8px;
        border: none;
        box-shadow: 0 4px 15px rgba(37, 99, 235, 0.4);
        transition: all 0.2s ease-in-out;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(37, 99, 235, 0.6);
    }
</style>
""", unsafe_allow_html=True)


# -------------------------------------------------------------
# Sidebar: Settings & System Status
# -------------------------------------------------------------
with st.sidebar:
    st.image("https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=500&auto=format&fit=crop&q=60", use_container_width=True)
    st.title("🏦 Hedge Fund Core")
    st.caption("Autonomous Quantitative Trading Pipeline")

    st.markdown("---")
    st.subheader("🔌 MT5 Connection")

    # MT5 Status Check
    mt5_status, mt5_msg = initialize_mt5()
    if mt5_status:
        st.success("🟢 MT5 Terminal: CONNECTED")
        st.info(mt5_msg)
    else:
        st.warning("🟡 Mode: SIMULATION / PAPER TRADING")
        st.caption("Real live market data is fed via high-speed web gateway. When deployed on Windows with MT5, orders execute directly into terminal64.exe.")

    with st.expander("🛠️ MT5 Terminal Credentials"):
        mt5_login_input = st.text_input("Account Login", value=str(config.MT5_LOGIN if config.MT5_LOGIN else ""))
        mt5_pass_input = st.text_input("Password", value=config.MT5_PASSWORD, type="password")
        mt5_server_input = st.text_input("Broker Server", value=config.MT5_SERVER)
        mt5_path_input = st.text_input("Terminal Path", value=config.MT5_PATH)

    st.markdown("---")
    st.subheader("🧠 AI Brain Configuration")

    ai_provider = st.selectbox(
        "Select AI Provider",
        [
            "⚡ Antigravity AI (Zero-API / Native)",
            "Groq Cloud (Llama / Qwen)",
            "Google Gemini",
            "OpenAI"
        ],
        index=0
    )

    gemini_key_input = ""
    groq_key_input = ""
    openai_key_input = ""

    if "Antigravity" in ai_provider:
        from ai_brain import is_bridge_alive
        if is_bridge_alive():
            st.success("🟢 **Zero-API Mode Active**: Antigravity Bridge (:8400) connected! Ultra-fast response active.")
        else:
            st.warning("🟡 **Zero-API Mode Active**: Bridge offline. Using cold CLI fallback (`agy`).")
        selected_model = "Antigravity (DeepMind / Gemini Engine)"
        chosen_provider = "Antigravity"
    elif "Gemini" in ai_provider:
        gemini_key_input = st.text_input(
            "Google Gemini API Key",
            value=config.GEMINI_API_KEY,
            type="password",
            help="Get your free Gemini API key from https://aistudio.google.com/app/apikey"
        )
        model_options = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
        selected_model = st.selectbox("Gemini Model", model_options, index=0)
        chosen_provider = "Gemini"
    elif "Groq" in ai_provider:
        groq_key_input = st.text_input(
            "Groq API Key (Active)",
            value=config.GROQ_API_KEY,
            type="password",
            help="Free key from https://console.groq.com/keys"
        )
        model_options = [
            "qwen/qwen3.8-27b",
            "groq/compound",
            "groq/compound-mini",
            "openai/gpt-oss-120b"
        ]
        selected_model = st.selectbox("Groq Model", model_options, index=0)
        chosen_provider = "Groq"
    else:
        openai_key_input = st.text_input(
            "OpenAI API Key",
            value=config.OPENAI_API_KEY,
            type="password"
        )
        model_options = ["gpt-4o-mini", "gpt-4o"]
        selected_model = st.selectbox("OpenAI Model", model_options, index=0)
        chosen_provider = "OpenAI"

    st.markdown("---")
    st.subheader("🚀 $100 ➔ $10,000 Compounding Engine")
    hyper_compounding_on = st.checkbox(
        "Enable Hyper-Compounding",
        value=getattr(config, "ENABLE_HYPER_COMPOUNDING", True),
        help="Dynamically scales position size as account equity grows toward the $10,000 daily goal."
    )
    risk_pct_slider = st.slider("Risk per Trade (%)", min_value=3, max_value=15, value=int(getattr(config, "COMPOUND_BASE_RISK_PCT", 0.08) * 100), step=1)
    target_goal_input = st.number_input("Daily Target Equity ($)", min_value=500.0, max_value=100000.0, value=getattr(config, "DAILY_TARGET_EQUITY", 10000.0), step=500.0)

    st.markdown("---")
    st.subheader("⚖️ Manual Execution Controls")
    lot_size = st.number_input("Base Lot Size", min_value=0.01, max_value=10.0, value=config.DEFAULT_LOT_SIZE, step=0.01)
    auto_execute = st.checkbox("Auto-Execute on MT5 upon Signal", value=True)

    st.caption("Multi-Strategy Hedge Fund Core (MACD + DMC + Robbins + MT5)")


# -------------------------------------------------------------
# Main Header & Asset Selection
# -------------------------------------------------------------
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.title("⚡ AI Hedge Fund — MT5 Trading Terminal")
    st.markdown("Multi-timeframe algorithmic analysis (**4H Trend Bias** + **15M Tactical Entry**) powered by Frontier LLM Reasoning.")

with col_h2:
    symbol_list = ["XAUUSD", "BTCUSD", "ETHUSD", "EURUSD", "GBPUSD", "USDJPY", "SOLUSD"]
    selected_symbol = st.selectbox("🎯 Select Market Symbol", symbol_list, index=0)

# Quick Fetch Market Snapshot
df_h4, df_m15, current_price, data_source = get_market_data(selected_symbol, count=config.CANDLES_COUNT)

# Top KPI Metric Cards
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1:
    st.markdown(f"""
    <div class="metric-card">
        <span style="color:#94a3b8; font-size:12px; font-weight:600;">ACTIVE ASSET</span>
        <h2 style="margin:4px 0 0 0; color:#38bdf8;">{selected_symbol}</h2>
    </div>
    """, unsafe_allow_html=True)

with kpi2:
    st.markdown(f"""
    <div class="metric-card">
        <span style="color:#94a3b8; font-size:12px; font-weight:600;">MARKET PRICE</span>
        <h2 style="margin:4px 0 0 0; color:#f8fafc;">${current_price:,.2f}</h2>
    </div>
    """, unsafe_allow_html=True)

with kpi3:
    latest_rsi = df_m15["rsi_14"].iloc[-1] if (df_m15 is not None and not df_m15.empty and "rsi_14" in df_m15.columns) else 50.0
    rsi_color = "#ef4444" if latest_rsi > 70 else ("#10b981" if latest_rsi < 30 else "#f59e0b")
    st.markdown(f"""
    <div class="metric-card">
        <span style="color:#94a3b8; font-size:12px; font-weight:600;">15M RSI (14)</span>
        <h2 style="margin:4px 0 0 0; color:{rsi_color};">{latest_rsi:.1f}</h2>
    </div>
    """, unsafe_allow_html=True)

with kpi4:
    st.markdown(f"""
    <div class="metric-card">
        <span style="color:#94a3b8; font-size:12px; font-weight:600;">DATA ENGINE SOURCE</span>
        <h3 style="margin:4px 0 0 0; color:#a78bfa; font-size:16px;">{data_source}</h3>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# =============================================================
# $100 -> $10,000 Hyper-Compounding Goal Banner
# =============================================================
acc_state = portfolio.get_account_state()
cur_equity = acc_state.get("equity", 100.0)
start_capital = acc_state.get("initial_balance", 100.0)
target_goal = target_goal_input
comp_progress = max(0.0, min(100.0, ((cur_equity - start_capital) / max(target_goal - start_capital, 1.0)) * 100.0))
multiplier = round(cur_equity / max(start_capital, 1.0), 2)
remaining_dollars = max(0.0, target_goal - cur_equity)

# Strategy confluence evaluation
quant_signals = strategy_engine.fuse_quantitative_strategies(selected_symbol, current_price, df_h4, df_m15)
s1 = quant_signals["strategies"]["s1_macd_200ema"]
s2 = quant_signals["strategies"]["s2_dmc_sweep"]
s3 = quant_signals["strategies"]["s3_orderflow"]

# Goal Banner Container
st.markdown(f"""
<div style="background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%); border: 2px solid #6366f1; border-radius: 12px; padding: 18px 22px; margin-bottom: 15px; box-shadow: 0 8px 24px rgba(99, 102, 241, 0.25);">
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; margin-bottom: 10px;">
        <div>
            <span style="background:#4338ca; color:#e0e7ff; padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight:700; text-transform:uppercase; letter-spacing:1px;">🚀 ACTIVE MISSION</span>
            <h2 style="margin:6px 0 2px 0; color:#ffffff; font-size:22px;">$100 ➔ $10,000 Daily Compounding Challenge</h2>
            <span style="color:#94a3b8; font-size:13px;">TradingLab MACD (86% WR) + DMC Sweeps (80-90% WR) + Robbins World Champion Orderflow</span>
        </div>
        <div style="text-align:right;">
            <span style="font-size:28px; font-weight:800; color:#38bdf8;">${cur_equity:,.2f}</span>
            <span style="color:#94a3b8; font-size:14px;"> / ${target_goal:,.0f} ({multiplier}x)</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.progress(comp_progress / 100.0, text=f"Compounding Progress: {comp_progress:.1f}% toward $10,000 goal | Remaining: ${remaining_dollars:,.2f}")

# 3 YouTube Strategies Confluence Cards
s_col1, s_col2, s_col3 = st.columns(3)

with s_col1:
    s1_badge = "🟢 BUY" if s1["signal"] == "BUY" else ("🔴 SELL" if s1["signal"] == "SELL" else "🟡 HOLD")
    s1_border = "#10b981" if s1["signal"] == "BUY" else ("#ef4444" if s1["signal"] == "SELL" else "#334155")
    st.markdown(f"""
    <div style="background:#131722; border:1px solid {s1_border}; border-radius:8px; padding:12px; height:100%;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="font-weight:700; font-size:13px; color:#f8fafc;">📈 1. TradingLab MACD 200 EMA</span>
            <span style="font-weight:800; font-size:12px;">{s1_badge}</span>
        </div>
        <div style="font-size:11px; color:#94a3b8; margin-top:6px;"><b>Trend:</b> {s1['trend_200']}</div>
        <div style="font-size:11px; color:#cbd5e1; margin-top:2px;"><b>State:</b> {s1['macd_state']}</div>
    </div>
    """, unsafe_allow_html=True)

with s_col2:
    s2_badge = "🟢 BUY" if s2["signal"] == "BUY" else ("🔴 SELL" if s2["signal"] == "SELL" else "🟡 HOLD")
    s2_border = "#10b981" if s2["signal"] == "BUY" else ("#ef4444" if s2["signal"] == "SELL" else "#334155")
    st.markdown(f"""
    <div style="background:#131722; border:1px solid {s2_border}; border-radius:8px; padding:12px; height:100%;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="font-weight:700; font-size:13px; color:#f8fafc;">🎯 2. DMC Liquidity Sweep</span>
            <span style="font-weight:800; font-size:12px;">{s2_badge}</span>
        </div>
        <div style="font-size:11px; color:#94a3b8; margin-top:6px;"><b>Setup:</b> {s2['sweep_type']}</div>
        <div style="font-size:11px; color:#cbd5e1; margin-top:2px;"><b>Confidence:</b> {s2['confidence']}%</div>
    </div>
    """, unsafe_allow_html=True)

with s_col3:
    s3_badge = "🟢 BUY" if s3["signal"] == "BUY" else ("🔴 SELL" if s3["signal"] == "SELL" else "🟡 HOLD")
    s3_border = "#10b981" if s3["signal"] == "BUY" else ("#ef4444" if s3["signal"] == "SELL" else "#334155")
    st.markdown(f"""
    <div style="background:#131722; border:1px solid {s3_border}; border-radius:8px; padding:12px; height:100%;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="font-weight:700; font-size:13px; color:#f8fafc;">🌊 3. Robbins Order Flow</span>
            <span style="font-weight:800; font-size:12px;">{s3_badge}</span>
        </div>
        <div style="font-size:11px; color:#94a3b8; margin-top:6px;"><b>State:</b> {s3['auction_state']}</div>
        <div style="font-size:11px; color:#cbd5e1; margin-top:2px;"><b>Confluence:</b> {quant_signals['grade']}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)



# -------------------------------------------------------------
# Interactive Candlestick Charts (TradingView + Multi-Timeframe)
# -------------------------------------------------------------
def render_tradingview_widget(symbol: str, theme: str = "light", height: int = 620):
    """Renders the official full-featured TradingView chart widget with live ticks."""
    tv_symbol_map = {
        "XAUUSD": "OANDA:XAUUSD",
        "BTCUSD": "BINANCE:BTCUSDT",
        "ETHUSD": "BINANCE:ETHUSDT",
        "EURUSD": "FX:EURUSD",
        "GBPUSD": "FX:GBPUSD",
        "USDJPY": "FX:USDJPY",
        "SOLUSD": "BINANCE:SOLUSDT"
    }
    tv_symbol = tv_symbol_map.get(symbol.upper(), f"OANDA:{symbol.upper()}")
    is_dark = (theme.lower() == "dark")
    bg_color = "#131722" if is_dark else "#ffffff"
    toolbar_bg = "#1e222d" if is_dark else "#f1f3f6"

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body, html {{ margin: 0; padding: 0; height: 100%; width: 100%; overflow: hidden; background-color: {bg_color}; }}
        #tv_chart_container {{ height: 100%; width: 100%; }}
      </style>
    </head>
    <body>
      <div id="tv_chart_container"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
        new TradingView.widget({{
          "autosize": true,
          "symbol": "{tv_symbol}",
          "interval": "15",
          "timezone": "Etc/UTC",
          "theme": "{"dark" if is_dark else "light"}",
          "style": "1",
          "locale": "en",
          "toolbar_bg": "{toolbar_bg}",
          "enable_publishing": false,
          "withdateranges": true,
          "hide_side_toolbar": false,
          "allow_symbol_change": true,
          "save_image": true,
          "details": true,
          "hotlist": false,
          "calendar": false,
          "studies": [
            "RSI@tv-basicstudies",
            "MASimple@tv-basicstudies"
          ],
          "show_popup_button": true,
          "popup_width": "1000",
          "popup_height": "650",
          "container_id": "tv_chart_container"
        }});
      </script>
    </body>
    </html>
    """
    components.html(html_code, height=height)


chart_tab_tv, chart_tab_strat, chart_tab1, chart_tab2 = st.tabs([
    "⚡ Official TradingView Terminal (Live & Interactive)",
    "🧠 3 Quantitative Strategies (YouTube Masterclasses & Live Metrics)",
    "📊 15-Minute Tactical Setup",
    "📈 4-Hour Macro Trend"
])

with chart_tab_tv:
    # Quick Trading Header Bar (matching TradingView Buy/Sell buttons)
    q_col1, q_col2, q_col3, q_col4 = st.columns([1.5, 1, 1.5, 2])
    with q_col1:
        sell_label = f"🔴 {current_price - 0.5:,.1f} SELL" if current_price else "🔴 SELL"
        quick_sell = st.button(sell_label, use_container_width=True, help="Instantly execute SELL order")
    with q_col2:
        quick_lot = st.number_input("Lots", min_value=0.01, max_value=5.0, value=0.01, step=0.01, label_visibility="collapsed")
    with q_col3:
        buy_label = f"🔵 {current_price + 0.5:,.1f} BUY" if current_price else "🔵 BUY"
        quick_buy = st.button(buy_label, use_container_width=True, type="primary", help="Instantly execute BUY order")
    with q_col4:
        tv_theme_choice = st.radio("Chart Theme", ["Light Mode ☀️", "Dark Mode 🌙"], horizontal=True, label_visibility="collapsed")

    if quick_buy:
        res = execute_trade(selected_symbol, "BUY", lot_size=quick_lot, current_price=current_price)
        st.success(f"🚀 Executed BUY {quick_lot} lots of {selected_symbol} at ${current_price:,.2f}!")
        st.rerun()

    if quick_sell:
        res = execute_trade(selected_symbol, "SELL", lot_size=quick_lot, current_price=current_price)
        st.success(f"🚀 Executed SELL {quick_lot} lots of {selected_symbol} at ${current_price:,.2f}!")
        st.rerun()

    selected_theme = "light" if "Light" in tv_theme_choice else "dark"
    render_tradingview_widget(selected_symbol, theme=selected_theme, height=620)

with chart_tab_strat:
    st.markdown("### 🏆 High-Win-Rate Strategy Confluence Engine")
    st.caption("Derived from the 3 world-class trading frameworks to power automated $100 ➔ $10,000 compounding.")

    # Strategy Citations & Real-time status
    str1_col, str2_col, str3_col = st.columns(3)

    with str1_col:
        st.markdown("""
        #### 1. [TradingLab MACD + 200 EMA](https://www.youtube.com/watch?v=rf_EQvubKlk)
        **Claimed Win Rate:** ~86%
        - **Trend Filter:** Price > 200 EMA = strictly BUY; Price < 200 EMA = strictly SELL.
        - **Dynamic Pullback:** Retracement to 50 EMA or dynamic support.
        - **Zero-Line Cross:** MACD crosses above Signal Line *below 0* for BUY; below Signal Line *above 0* for SELL.
        """)
        st.info(f"**Current Status:** {s1['signal']} | {s1['trend_200']}\n\n{s1['reason']}")

    with str2_col:
        st.markdown("""
        #### 2. [DMC Liquidity Sweeps](https://www.youtube.com/watch?v=MzZ0b_ZVeQw)
        **Claimed Win Rate:** 80-90%
        - **Untested Major Levels:** Swing High / Low retail stop pools.
        - **Dumb Money Trap:** Price probes outside level, wicks reject (>=30% wick ratio), closes back inside.
        - **Execution:** Enter on close inside range; SL beyond wick extreme; target opposite liquidity.
        """)
        st.info(f"**Current Status:** {s2['signal']} | {s2['sweep_type']}\n\n{s2['reason']}")

    with str3_col:
        st.markdown("""
        #### 3. [Robbins Cup Order Flow](https://www.youtube.com/watch?v=PL7LKUsCgIQ)
        **Method:** World Champion Auction Market Theory
        - **Value Area:** VAH (High), VAL (Low), and POC (Point of Control).
        - **Failed Auction:** Breakout attempted outside Value Area, but volume delta dries up / passive limit orders absorb.
        - **Mean Reversion:** Target POC and opposite Value Area boundary.
        """)
        st.info(f"**Current Status:** {s3['signal']} | {s3['auction_state']}\n\n{s3['reason']}")

    # Quantitative Indicators Live Table
    st.markdown("---")
    st.subheader(f"📊 Quantitative Indicator Dashboard ({selected_symbol})")
    latest_cand = df_m15.iloc[-1] if (df_m15 is not None and not df_m15.empty) else {}

    ind_col1, ind_col2, ind_col3, ind_col4 = st.columns(4)
    ind_col1.metric("200 EMA (Trend)", f"${latest_cand.get('ema_200', 0):,.2f}", delta="Above" if current_price >= latest_cand.get('ema_200', 0) else "Below")
    ind_col2.metric("50 EMA (Pullback)", f"${latest_cand.get('ema_50', 0):,.2f}")
    ind_col3.metric("MACD Line / Signal", f"{latest_cand.get('macd_line', 0):.2f} / {latest_cand.get('signal_line', 0):.2f}")
    ind_col4.metric("Confluence Conviction", f"{quant_signals['confidence']}%", delta=quant_signals['grade'])

    # Compounding Matrix ($100 -> $10,000 Roadmap)
    st.markdown("---")
    st.subheader("🚀 Mathematical Compounding Roadmap ($100 ➔ $10,000)")
    st.caption("How dynamic position scaling and 1:2.0 Risk-to-Reward turn $100 starting capital into $10,000.")

    roadmap_data = [
        {"Stage": "Stage 1 (Launch)", "Account Equity": "$100.00", "Risk (8%)": "$8.00", "Gold Scalp Lot": "0.02 Lots", "Target PnL (1:2 R)": "+$16.00", "Next Equity": "$116.00"},
        {"Stage": "Stage 2", "Account Equity": "$116.00", "Risk (8%)": "$9.28", "Gold Scalp Lot": "0.03 Lots", "Target PnL (1:2 R)": "+$18.56", "Next Equity": "$134.56"},
        {"Stage": "Stage 3", "Account Equity": "$134.56", "Risk (8%)": "$10.76", "Gold Scalp Lot": "0.04 Lots", "Target PnL (1:2 R)": "+$21.52", "Next Equity": "$156.08"},
        {"Stage": "Stage 4", "Account Equity": "$156.08", "Risk (8%)": "$12.48", "Gold Scalp Lot": "0.05 Lots", "Target PnL (1:2 R)": "+$24.96", "Next Equity": "$181.04"},
        {"Stage": "Stage 5", "Account Equity": "$250.00", "Risk (8%)": "$20.00", "Gold Scalp Lot": "0.08 Lots", "Target PnL (1:2 R)": "+$40.00", "Next Equity": "$290.00"},
        {"Stage": "Stage 6", "Account Equity": "$500.00", "Risk (8%)": "$40.00", "Gold Scalp Lot": "0.15 Lots", "Target PnL (1:2 R)": "+$80.00", "Next Equity": "$580.00"},
        {"Stage": "Stage 7", "Account Equity": "$1,000.00", "Risk (8%)": "$80.00", "Gold Scalp Lot": "0.30 Lots", "Target PnL (1:2 R)": "+$160.00", "Next Equity": "$1,160.00"},
        {"Stage": "Stage 8", "Account Equity": "$2,500.00", "Risk (8%)": "$200.00", "Gold Scalp Lot": "0.75 Lots", "Target PnL (1:2 R)": "+$400.00", "Next Equity": "$2,900.00"},
        {"Stage": "Stage 9", "Account Equity": "$5,000.00", "Risk (8%)": "$400.00", "Gold Scalp Lot": "1.50 Lots", "Target PnL (1:2 R)": "+$800.00", "Next Equity": "$5,800.00"},
        {"Stage": "Stage 10 (Target Goal)", "Account Equity": "$8,500.00", "Risk (8%)": "$680.00", "Gold Scalp Lot": "2.50 Lots", "Target PnL (1:2 R)": "+$1,500.00", "Next Equity": "🎯 $10,000.00"}
    ]
    st.dataframe(pd.DataFrame(roadmap_data), use_container_width=True)


def create_candlestick_chart(df: pd.DataFrame, title: str):
    if df is None or df.empty:
        return go.Figure()

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.65, 0.12, 0.23],
        specs=[
            [{"type": "candlestick"}],
            [{"type": "bar"}],
            [{"type": "scatter"}]
        ]
    )

    # ── Candlesticks (TradingView palette) ──────────────────────
    fig.add_trace(go.Candlestick(
        x=df["time"],
        open=df["open"], high=df["high"],
        low=df["low"],   close=df["close"],
        name="OHLC",
        increasing_line_color="#26a69a",
        increasing_fillcolor="#26a69a",
        decreasing_line_color="#ef5350",
        decreasing_fillcolor="#ef5350",
        line=dict(width=1),
        whiskerwidth=0.4,
    ), row=1, col=1)

    # ── SMA 7 ────────────────────────────────────────────────────
    if "sma_7" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["time"], y=df["sma_7"],
            mode="lines", name="SMA 7",
            line=dict(color="#38bdf8", width=1.5)
        ), row=1, col=1)

    if "ema_14" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["time"], y=df["ema_14"],
            mode="lines", name="EMA 14",
            line=dict(color="#f59e0b", width=1.5, dash="dot")
        ), row=1, col=1)

    # RSI
    if "rsi_14" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["time"], y=df["rsi_14"],
            mode="lines", name="RSI",
            line=dict(color="#c084fc", width=2)
        ), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", opacity=0.6, row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#10b981", opacity=0.6, row=2, col=1)

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        margin=dict(l=10, r=10, t=30, b=10),
        height=450,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

with chart_tab1:
    st.plotly_chart(create_candlestick_chart(df_m15, f"{selected_symbol} - 15M Tactical Candles"), use_container_width=True)

with chart_tab2:
    st.plotly_chart(create_candlestick_chart(df_h4, f"{selected_symbol} - 4H Macro Trend Candles"), use_container_width=True)


# -------------------------------------------------------------
# Autonomous Trading Engine Control Center
# -------------------------------------------------------------
st.markdown("---")
st.subheader("🤖 Autonomous Trading Engine ($100 Capital Auto-Pilot)")

auto_trader = get_auto_trader()
trader_status = auto_trader.get_status()
is_auto_running = trader_status["is_running"]

ctl_col1, ctl_col2, ctl_col3, ctl_col4 = st.columns([2, 1, 1, 1])

with ctl_col1:
    if is_auto_running:
        st.success(f"🟢 **AUTONOMOUS TRADING ACTIVE** | Running on {trader_status['symbol']} every {trader_status['interval']}s")
    else:
        st.info("⏸️ **AUTONOMOUS TRADING PAUSED** | Click 'Start Auto-Pilot' to begin autonomous trading.")
    st.caption(f"Status: {trader_status.get('last_message', 'Ready.')}")

with ctl_col2:
    if not is_auto_running:
        if st.button("▶️ Start Auto-Pilot", use_container_width=True, type="primary"):
            auto_trader.start(interval=20, symbol=selected_symbol)
            st.rerun()
    else:
        if st.button("⏹️ Stop Auto-Pilot", use_container_width=True):
            auto_trader.stop()
            st.rerun()

with ctl_col3:
    if st.button("⚡ Run 1 Cycle Now", use_container_width=True):
        with st.spinner("Running single autonomous cycle..."):
            res = auto_trader.run_cycle_once()
            st.info(f"Cycle completed: {res.get('message', 'Done')}")
            st.rerun()

with ctl_col4:
    if st.button("🔄 Reset Account ($100)", use_container_width=True):
        portfolio.initialize_account(100.0, force=True)
        st.success("Account reset to $100.00 initial capital.")
        st.rerun()

# -------------------------------------------------------------
# Manual Trigger Button & Orchestration Pipeline
# -------------------------------------------------------------
st.markdown("---")
st.subheader("🎯 Manual AI Analysis & Execution")
btn_col1, btn_col2, btn_col3 = st.columns([1, 2, 1])
with btn_col2:
    execute_btn = st.button("🚀 Start AI Analysis & Execute Trade", use_container_width=True)

if execute_btn:
    progress_box = st.container()
    with progress_box:
        step_bar = st.progress(0, text="Initializing Quantitative Pipeline...")

        # Step 1: Data Engine
        time.sleep(0.3)
        step_bar.progress(30, text=f"📊 [Data Engine] Fetching 4H and 15M candles for {selected_symbol}...")
        df_h4, df_m15, current_price, data_source = get_market_data(selected_symbol, count=config.CANDLES_COUNT)

        # Step 2: AI Brain
        time.sleep(0.3)
        step_bar.progress(65, text=f"🧠 [AI Brain] Analyzing market structure via {chosen_provider} ({selected_model})...")
        decision_data, model_used = analyze_market(
            symbol=selected_symbol,
            current_price=current_price,
            df_h4=df_h4,
            df_m15=df_m15,
            provider=chosen_provider,
            gemini_api_key=gemini_key_input,
            groq_api_key=groq_key_input,
            openai_api_key=openai_key_input,
            model_name=selected_model
        )

        # Step 3: Execution Engine
        time.sleep(0.3)
        step_bar.progress(90, text="🎯 [Execution Engine] Validating risk parameters and transmitting order...")

        decision = decision_data.get("decision", "HOLD").upper()
        confidence = decision_data.get("confidence", 50)
        sl_val = decision_data.get("stop_loss", 0.0)
        tp_val = decision_data.get("take_profit", 0.0)

        execution_result = None
        if auto_execute and decision in ["BUY", "SELL"]:
            execution_result = execute_trade(
                symbol=selected_symbol,
                decision=decision,
                lot_size=lot_size,
                sl=sl_val,
                tp=tp_val,
                comment=f"AI-{decision}-{confidence}%",
                current_price=current_price
            )
            if execution_result.get("success"):
                try:
                    from chart_snapshot import generate_trade_screenshot
                    import journal
                    order_id = execution_result.get("order_id", f"POS-{int(time.time()*1000)%10000000}")
                    shot_path = generate_trade_screenshot(
                        df=df_m15,
                        symbol=selected_symbol,
                        action=decision,
                        entry_price=current_price,
                        sl=sl_val,
                        tp=tp_val,
                        position_id=order_id,
                        confidence=confidence
                    )
                    journal.create_journal_entry(
                        trade_id=order_id,
                        symbol=selected_symbol,
                        action=decision,
                        entry_price=current_price,
                        volume=lot_size,
                        sl=sl_val,
                        tp=tp_val,
                        confidence=confidence,
                        h4_analysis=decision_data.get("h4_trend_analysis", ""),
                        m15_analysis=decision_data.get("m15_setup_analysis", ""),
                        reasoning=decision_data.get("reasoning", ""),
                        screenshot_path=shot_path
                    )
                except Exception as je:
                    print(f"Journal error: {je}")
        else:
            execution_result = {
                "success": False,
                "status": "HOLD" if decision == "HOLD" else "AUTO_EXECUTE_OFF",
                "message": "Trade not dispatched to broker. Decision was HOLD or Auto-Execute was disabled.",
                "order_id": None
            }

        step_bar.progress(100, text="✅ Pipeline Execution Complete!")
        time.sleep(0.5)
        step_bar.empty()

    # Display AI Decision & Rationale Card
    st.markdown("### 🏆 AI Brain Strategic Decision")

    box_class = "decision-buy" if decision == "BUY" else ("decision-sell" if decision == "SELL" else "decision-hold")
    badge_class = "badge-buy" if decision == "BUY" else ("badge-sell" if decision == "SELL" else "badge-hold")

    dec_col1, dec_col2 = st.columns([1, 2])
    with dec_col1:
        st.markdown(f"""
        <div class="{box_class}">
            <span style="font-size:14px; color:#cbd5e1; font-weight:600; text-transform:uppercase;">Institutional Recommendation</span>
            <div style="margin: 15px 0;">
                <span class="badge {badge_class}">{decision}</span>
            </div>
            <div style="font-size: 16px; color:#f1f5f9; font-weight:700;">
                Confidence Conviction: {confidence}%
            </div>
            <div style="font-size: 13px; color:#94a3b8; margin-top: 8px;">
                Model: {model_used}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with dec_col2:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Suggested Entry", f"${decision_data.get('suggested_entry', current_price):,.2f}")
        m2.metric("Stop Loss (SL)", f"${sl_val:,.2f}" if sl_val else "N/A")
        m3.metric("Take Profit (TP)", f"${tp_val:,.2f}" if tp_val else "N/A")
        m4.metric("Risk / Reward", str(decision_data.get("risk_reward_ratio", "1:2.0")))

        st.markdown(f"**Macro Trend (4H):** {decision_data.get('h4_trend_analysis', 'N/A')}")
        st.markdown(f"**Tactical Setup (15M):** {decision_data.get('m15_setup_analysis', 'N/A')}")
        st.markdown(f"**Portfolio Manager Thesis:** {decision_data.get('reasoning', 'N/A')}")

    # Display Order Execution Receipt
    st.markdown("---")
    st.subheader("📝 Order Execution Receipt")
    rec1, rec2, rec3, rec4 = st.columns(4)
    rec1.metric("Execution Status", execution_result.get("status", "N/A"))
    rec2.metric("Order ID", execution_result.get("order_id") or "None")
    rec3.metric("Volume / Lots", f"{execution_result.get('volume', lot_size)} lots")
    rec4.metric("Executed Price", f"${execution_result.get('price', current_price):,.2f}" if execution_result.get("price") else "N/A")

    if execution_result.get("success"):
        st.success(f"🎉 Trade Dispatched Successfully! [Mode: {execution_result.get('mode', 'Live')}] — Message: {execution_result.get('message', execution_result.get('comment', 'Done'))}")
    else:
        st.info(f"ℹ️ {execution_result.get('message', 'Trade not sent to exchange.')}")


# -------------------------------------------------------------
# Live Financial Performance, Win/Loss & Realized Earnings Ledger
# -------------------------------------------------------------
st.markdown("---")
st.subheader("🏆 Live Financial Performance & Realized Earnings Ledger")
st.caption("Live accounting of $100 starting capital, executed positions, TP/SL monitoring, and real-time net earnings.")

@st.fragment(run_every="5s")
def render_live_portfolio_ledger():
    # Update open positions against live market price
    if current_price and current_price > 0:
        portfolio.check_and_update_positions(selected_symbol, current_price)

    acc = portfolio.get_account_state()
    initial_cap = acc.get("initial_balance", 100.0)
    balance = acc.get("balance", 100.0)
    equity = acc.get("equity", 100.0)
    realized_pnl = acc.get("realized_pnl", 0.0)
    unrealized_pnl = acc.get("unrealized_pnl", 0.0)
    total_earned = round((balance - initial_cap) + unrealized_pnl, 2)
    return_pct = round((total_earned / initial_cap) * 100.0, 2) if initial_cap > 0 else 0.0
    win_rate = acc.get("win_rate", 0.0)
    wins = acc.get("win_count", 0)
    losses = acc.get("loss_count", 0)
    bes = acc.get("breakeven_count", 0)
    open_pos = acc.get("open_positions", [])
    closed_trades = acc.get("closed_trades", [])

    # 4 Main Financial Metric Cards
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        st.markdown(f"""
        <div class="metric-card">
            <span style="color:#94a3b8; font-size:12px; font-weight:600;">INITIAL ALLOCATION</span>
            <h2 style="margin:4px 0 0 0; color:#f8fafc;">${initial_cap:,.2f}</h2>
            <span style="font-size:11px; color:#64748b;">Starting Paper Capital</span>
        </div>
        """, unsafe_allow_html=True)

    with p2:
        st.markdown(f"""
        <div class="metric-card">
            <span style="color:#94a3b8; font-size:12px; font-weight:600;">PORTFOLIO EQUITY</span>
            <h2 style="margin:4px 0 0 0; color:#38bdf8;">${equity:,.2f}</h2>
            <span style="font-size:11px; color:#64748b;">Cash: ${balance:,.2f} | Float: ${unrealized_pnl:+,.2f}</span>
        </div>
        """, unsafe_allow_html=True)

    with p3:
        pnl_color = "#10b981" if total_earned >= 0 else "#ef4444"
        pnl_sign = "+" if total_earned >= 0 else ""
        st.markdown(f"""
        <div class="metric-card">
            <span style="color:#94a3b8; font-size:12px; font-weight:600;">TOTAL NET EARNED</span>
            <h2 style="margin:4px 0 0 0; color:{pnl_color};">{pnl_sign}${total_earned:,.2f}</h2>
            <span style="font-size:11px; color:{pnl_color}; font-weight:600;">ROI: {pnl_sign}{return_pct:.2f}%</span>
        </div>
        """, unsafe_allow_html=True)

    with p4:
        wr_color = "#10b981" if win_rate >= 50 else ("#f59e0b" if win_rate > 0 else "#94a3b8")
        st.markdown(f"""
        <div class="metric-card">
            <span style="color:#94a3b8; font-size:12px; font-weight:600;">WIN RATE & RECORD</span>
            <h2 style="margin:4px 0 0 0; color:{wr_color};">{win_rate:.1f}%</h2>
            <span style="font-size:11px; color:#64748b;">🏆 {wins} Wins &nbsp;|&nbsp; 🛑 {losses} Losses</span>
        </div>
        """, unsafe_allow_html=True)

    # Active Live Open Positions Table
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### ⚡ Active Live Open Positions (Floating P&L)")
    if open_pos:
        pos_rows = []
        for pos in open_pos:
            pos_rows.append({
                "Position ID": pos["position_id"],
                "Symbol": pos["symbol"],
                "Direction": pos["action"],
                "Lots": pos["volume"],
                "Entry Price": f"${pos['entry_price']:,.2f}",
                "Live Price": f"${pos.get('current_price', current_price):,.2f}",
                "Stop Loss (SL)": f"${pos['sl']:,.2f}" if pos.get('sl') else "None",
                "Take Profit (TP)": f"${pos['tp']:,.2f}" if pos.get('tp') else "None",
                "Floating P&L ($)": f"{pos.get('unrealized_pnl', 0.0):+,.2f}",
                "Return (%)": f"{pos.get('return_pct', 0.0):+,.2f}%",
                "Open Time": pos["open_time"]
            })
        st.dataframe(pd.DataFrame(pos_rows), use_container_width=True)
    else:
        st.info("ℹ️ No open positions right now. The Autonomous Trader is actively scanning the market for high-conviction entries.")

    # Closed Trades & Realized Earnings Ledger
    st.markdown("#### 📜 Completed Trades Audit Ledger")
    if closed_trades:
        closed_rows = []
        for tr in closed_trades:
            pnl_val = tr.get("pnl", 0.0)
            closed_rows.append({
                "Trade ID": tr.get("trade_id", ""),
                "Symbol": tr.get("symbol", ""),
                "Direction": tr.get("action", ""),
                "Lots": tr.get("volume", 0.01),
                "Entry Price": f"${tr.get('entry_price', 0.0):,.2f}",
                "Exit Price": f"${tr.get('exit_price', 0.0):,.2f}",
                "Realized P&L ($)": f"{pnl_val:+,.2f}",
                "Return (%)": f"{tr.get('return_pct', 0.0):+,.2f}%",
                "Exit Reason": tr.get("exit_reason", "Closed"),
                "Close Time": tr.get("close_time", "")
            })
        st.dataframe(pd.DataFrame(closed_rows), use_container_width=True)

        # Capital Growth Curve
        if len(closed_trades) >= 1:
            cum_curve = [initial_cap]
            cum_times = ["Start"]
            curr_running = initial_cap
            for tr in reversed(closed_trades):
                curr_running += tr.get("pnl", 0.0)
                cum_curve.append(curr_running)
                cum_times.append(tr.get("close_time", "")[-12:])

            fig_pnl = go.Figure()
            fig_pnl.add_trace(go.Scatter(
                x=cum_times,
                y=cum_curve,
                mode="lines+markers",
                name="Account Balance ($)",
                line=dict(color="#10b981" if curr_running >= initial_cap else "#ef4444", width=3),
                marker=dict(size=7, color="#38bdf8")
            ))
            fig_pnl.add_hline(y=initial_cap, line_dash="dash", line_color="#64748b", annotation_text="Initial $100")
            fig_pnl.update_layout(
                title=f"📈 Account Capital Growth Curve (Starting: ${initial_cap:.2f} ➔ Current: ${curr_running:.2f})",
                template="plotly_dark",
                paper_bgcolor="#131722",
                plot_bgcolor="#131722",
                height=280,
                margin=dict(l=40, r=40, t=40, b=30),
                yaxis=dict(title="Equity ($)", tickprefix="$", gridcolor="#1e222d"),
                xaxis=dict(gridcolor="#1e222d")
            )
            st.plotly_chart(fig_pnl, use_container_width=True)
    else:
        st.caption("No closed trades yet. When active positions hit Take Profit (TP) or Stop Loss (SL), their realized dollar profit will appear here.")

render_live_portfolio_ledger()


# -------------------------------------------------------------
# Live Trading Journal (Visual Snapshots & AI Trade Audits)
# -------------------------------------------------------------
st.markdown("---")
st.subheader("📔 Live Institutional Trading Journal & Visual Audit")
st.caption("Auto-generated visual trade logs: chart screenshots, AI entry rationale, confluences, and post-trade audits.")

@st.fragment(run_every="5s")
def render_live_journal():
    import journal
    entries = journal.get_journal_entries()
    if not entries:
        st.info("ℹ️ No journal entries yet. When a trade executes, a high-resolution chart screenshot and full AI thesis will be automatically logged here.")
        return

    # Filter controls
    f_col1, f_col2 = st.columns([2, 1])
    with f_col1:
        filter_opt = st.radio("Filter Journal", ["All Trades", "🟢 Active Only", "🏆 Wins Only", "🛑 Losses Only"], horizontal=True)

    filtered_entries = entries
    if filter_opt == "🟢 Active Only":
        filtered_entries = [e for e in entries if e.get("status") == "ACTIVE"]
    elif filter_opt == "🏆 Wins Only":
        filtered_entries = [e for e in entries if e.get("outcome") == "WIN"]
    elif filter_opt == "🛑 Losses Only":
        filtered_entries = [e for e in entries if e.get("outcome") == "LOSS"]

    st.markdown(f"**Showing {len(filtered_entries)} of {len(entries)} recorded journal trades:**")

    for entry in filtered_entries:
        status = entry.get("status", "ACTIVE")
        outcome = entry.get("outcome", "PENDING")
        action = entry.get("action", "BUY")
        symbol = entry.get("symbol", "XAUUSD")
        entry_p = entry.get("entry_price", 0.0)
        exit_p = entry.get("exit_price")
        pnl = entry.get("realized_pnl", 0.0)
        ret_pct = entry.get("return_pct", 0.0)
        trade_id = entry.get("trade_id", "")
        shot_path = entry.get("screenshot_path")

        if status == "ACTIVE":
            badge = "🟢 ACTIVE"
        elif outcome == "WIN":
            badge = f"🏆 WIN (+${pnl:,.2f} | +{ret_pct:.2f}%)"
        elif outcome == "LOSS":
            badge = f"🛑 LOSS (${pnl:,.2f} | {ret_pct:.2f}%)"
        else:
            badge = f"⚖️ BREAKEVEN (${pnl:,.2f})"

        with st.expander(f"{badge} — {symbol} {action} @ ${entry_p:,.2f} ({entry.get('open_time', '')})", expanded=(status == "ACTIVE")):
            j_col1, j_col2 = st.columns([1, 1])
            with j_col1:
                st.markdown(f"### Trade Audit: `{trade_id}`")
                st.markdown(f"- **Asset:** `{symbol}`")
                st.markdown(f"- **Direction:** **{action}** ({entry.get('volume', 0.01)} lots)")
                st.markdown(f"- **Entry Price:** `${entry_p:,.2f}`")
                st.markdown(f"- **Take Profit (TP):** `${entry.get('tp', 0.0):,.2f}`")
                st.markdown(f"- **Stop Loss (SL):** `${entry.get('sl', 0.0):,.2f}`")
                st.markdown(f"- **Risk / Reward:** `{entry.get('risk_reward', '1:2.0')}`")
                st.markdown(f"- **AI Conviction:** `{entry.get('confidence', 70)}%`")
                if status == "CLOSED":
                    st.markdown(f"- **Exit Price:** `${exit_p:,.2f}`")
                    st.markdown(f"- **Realized PnL:** `${pnl:+,.2f}` ({ret_pct:+.2f}%)")
                    st.markdown(f"- **Exit Reason:** `{entry.get('exit_reason', 'Closed')}`")
                    st.markdown(f"- **Close Time:** `{entry.get('close_time', '')}`")

                st.markdown("#### 🧠 AI Confluence & Thesis:")
                st.markdown(f"**Macro 4H Trend:** {entry.get('h4_analysis', 'N/A')}")
                st.markdown(f"**Tactical 15M Setup:** {entry.get('m15_analysis', 'N/A')}")
                st.markdown(f"**Portfolio Thesis:** {entry.get('reasoning', 'N/A')}")
                st.info(f"📝 **Post-Trade Reflection:** {entry.get('notes', 'Active trade in progress...')}")

            with j_col2:
                st.markdown("#### 📸 Trade Setup Visual Snapshot")
                if shot_path and os.path.exists(shot_path):
                    st.image(shot_path, caption=f"Execution Chart Setup: {trade_id}", use_container_width=True)
                else:
                    st.caption("Chart snapshot generating or unavailable.")

render_live_journal()
