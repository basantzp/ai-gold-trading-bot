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

import config
from data_engine import (
    initialize_mt5,
    get_market_data,
    MT5_AVAILABLE
)
from ai_brain import analyze_market
from execution import execute_trade, get_trade_history

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
    st.subheader("⚖️ Risk & Execution Controls")
    lot_size = st.number_input("Lot Size", min_value=0.01, max_value=10.0, value=config.DEFAULT_LOT_SIZE, step=0.01)
    auto_execute = st.checkbox("Auto-Execute on MT5 upon Signal", value=True)

    st.caption("Multi-LLM Hedge Fund Core (⚡ Antigravity + Groq + Gemini + MT5)")


# -------------------------------------------------------------
# Main Header & Asset Selection
# -------------------------------------------------------------
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.title("⚡ AI Hedge Fund — MT5 Trading Terminal")
    st.markdown("Multi-timeframe algorithmic analysis (**4H Trend Bias** + **15M Tactical Entry**) powered by Frontier LLM Reasoning.")

with col_h2:
    symbol_list = ["BTCUSD", "ETHUSD", "XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "SOLUSD"]
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


# -------------------------------------------------------------
# Interactive Candlestick Charts (4H vs 15M)
# -------------------------------------------------------------
chart_tab1, chart_tab2 = st.tabs(["📊 15-Minute Execution Setup", "📈 4-Hour Macro Trend"])

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
        # Overbought / Oversold lines
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
# Trigger Button & Orchestration Pipeline
# -------------------------------------------------------------
st.markdown("---")
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
                comment=f"AI-{decision}-{int(confidence)}%"
            )
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
# Historical Trades & Audit Log
# -------------------------------------------------------------
st.markdown("---")
st.subheader("📜 Recent Trade Audit Ledger")
history = get_trade_history()
if history:
    history_df = pd.DataFrame(history)
    display_cols = ["timestamp", "symbol", "action", "volume", "price", "sl", "tp", "mode", "order_id", "status"]
    available_cols = [c for c in display_cols if c in history_df.columns]
    st.dataframe(history_df[available_cols], use_container_width=True)
else:
    st.caption("No trades recorded yet. Click 'Start AI Analysis & Execute Trade' to place your first trade.")
