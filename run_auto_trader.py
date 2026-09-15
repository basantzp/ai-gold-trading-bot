#!/usr/bin/env python3
"""
Autonomous Trading Daemon Launcher:
Runs the autonomous trading engine in a continuous background process.
Analyzes XAUUSD using Antigravity AI, executes paper trades with $100 capital,
and monitors positions for Take Profit / Stop Loss hits.
"""

import sys
import time
import signal
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

import portfolio
from auto_trader import get_auto_trader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [AUTOTRADER] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/tmp/auto_trader.log", mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger("AutoTraderDaemon")

def handle_exit(signum, frame):
    logger.info("Termination signal received. Stopping trader...")
    trader = get_auto_trader()
    trader.stop()
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    logger.info("Initializing Autonomous Trading Engine with $100 Capital...")
    state = portfolio.get_account_state()
    logger.info(f"Current Account State: Balance: ${state.get('balance', 100.0):.2f} | Equity: ${state.get('equity', 100.0):.2f} | Realized PnL: ${state.get('realized_pnl', 0.0):+.2f}")

    trader = get_auto_trader()
    trader.start(interval=20, symbol="XAUUSD")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        handle_exit(None, None)

if __name__ == "__main__":
    main()
