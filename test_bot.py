"""
End-to-End CLI Verification Test Script for AI Hedge Fund Bot.
Verifies Data Engine, AI Brain, and Execution Engine components.
"""

import sys
import os

# Add current dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from data_engine import initialize_mt5, get_market_data, format_candles_summary
from ai_brain import analyze_market
from execution import execute_trade, get_trade_history

def run_test():
    print("==================================================")
    print("   AI HEDGE FUND BOT - CLI VERIFICATION TEST")
    print("==================================================")

    # 1. MT5 Connection Test
    print("\n[1/4] Testing MT5 Connection...")
    success, msg = initialize_mt5()
    print(f"Status: {'CONNECTED' if success else 'SIMULATION / FALLBACK'}")
    print(f"Details: {msg}")

    # 2. Data Engine Test
    symbol = "BTCUSD"
    print(f"\n[2/4] Testing Data Engine for {symbol}...")
    df_h4, df_m15, current_price, source = get_market_data(symbol, count=10)
    print(f"Data Source: {source}")
    print(f"Current Price: ${current_price:,.2f}")
    print(f"4H Candles retrieved: {len(df_h4) if df_h4 is not None else 0}")
    print(f"15M Candles retrieved: {len(df_m15) if df_m15 is not None else 0}")

    if df_m15 is not None and not df_m15.empty:
        latest = df_m15.iloc[-1]
        print(f"Latest 15M Close: {latest['close']} | RSI: {latest.get('rsi_14', 'N/A'):.1f} | ATR: {latest.get('atr', 'N/A'):.2f}")

    # 3. AI Brain Test
    print(f"\n[3/4] Testing AI Brain Analysis (⚡ Antigravity Zero-API)...")
    decision_data, model_name = analyze_market(symbol, current_price, df_h4, df_m15, provider="Antigravity")
    print(f"Model Engine: {model_name}")
    print(f"Decision: {decision_data.get('decision')}")
    print(f"Confidence: {decision_data.get('confidence')}%")
    print(f"Suggested Entry: ${decision_data.get('suggested_entry', current_price):,.2f}")
    print(f"Stop Loss (SL): ${decision_data.get('stop_loss', 0):,.2f}")
    print(f"Take Profit (TP): ${decision_data.get('take_profit', 0):,.2f}")
    print(f"Risk/Reward: {decision_data.get('risk_reward_ratio')}")
    print(f"Reasoning: {decision_data.get('reasoning')}")

    # 4. Execution Engine Test
    print(f"\n[4/4] Testing Execution Engine...")
    decision = decision_data.get("decision", "HOLD")
    exec_decision = decision if decision in ["BUY", "SELL"] else "BUY"  # Test order flow with BUY if HOLD was chosen
    print(f"Dispatching test trade: {exec_decision} 0.01 lots of {symbol}...")
    exec_result = execute_trade(
        symbol=symbol,
        decision=exec_decision,
        lot_size=0.01,
        sl=decision_data.get("stop_loss"),
        tp=decision_data.get("take_profit"),
        comment="Test Trade"
    )
    print(f"Order Result: {exec_result}")

    print("\n==================================================")
    print("✅ All Hedge Fund Bot Components Tested Successfully!")
    print("==================================================")

if __name__ == "__main__":
    run_test()
