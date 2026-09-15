"""
Autonomous Trading Engine: Fully automated buy/sell execution loop.
Runs market analysis via Antigravity Bridge, manages $100 starting capital,
monitors TP/SL in real time, and logs every dollar earned or lost.
"""

import os
import sys
import time
import threading
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import config
import portfolio
import strategy_engine
from data_engine import get_market_data
from ai_brain import analyze_market, is_bridge_alive
from execution import execute_trade

logger = logging.getLogger("AutoTrader")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [AUTOTRADER] %(message)s")


class AutonomousTrader:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AutonomousTrader, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.interval = 20  # seconds between cycles
        self.symbol = config.DEFAULT_SYMBOL or "XAUUSD"
        self.lot_size = 0.01  # Fallback base micro lot
        self.min_confidence = getattr(config, "MIN_CONFLUENCE_SCORE", 65)  # Minimum conviction to enter
        self.hyper_compounding = getattr(config, "ENABLE_HYPER_COMPOUNDING", True)
        self.target_equity = getattr(config, "DAILY_TARGET_EQUITY", 10000.0)
        self.last_run_time: Optional[str] = None
        self.last_decision: Optional[str] = None
        self.last_message: str = "AutoTrader initialized with 3 Quantitative Strategies. Ready to launch."
        self.iteration_count = 0
        self.last_error: Optional[str] = None
        self.last_strategy_confluence: Dict[str, Any] = {}
        self.last_compounding_metrics: Dict[str, Any] = {}

    def start(self, interval: int = 20, symbol: str = "XAUUSD") -> Dict[str, Any]:
        """Starts the autonomous trading loop in a background daemon thread."""
        with self._lock:
            if self.is_running and self.thread and self.thread.is_alive():
                return {"success": True, "message": "Autonomous trader is already running."}

            self.interval = max(10, interval)
            self.symbol = symbol
            self.stop_event.clear()
            self.is_running = True
            self.last_message = f"🚀 AutoTrader started on {self.symbol} (Compounding: {'Active' if self.hyper_compounding else 'Fixed'} | interval: {self.interval}s)."

            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            logger.info(f"Started autonomous trading daemon on {self.symbol}")
            return {"success": True, "message": self.last_message}

    def stop(self) -> Dict[str, Any]:
        """Stops the autonomous trading loop."""
        with self._lock:
            if not self.is_running:
                return {"success": True, "message": "Autonomous trader is not running."}

            self.stop_event.set()
            self.is_running = False
            self.last_message = "⏸️ AutoTrader stopped."
            logger.info("Stopped autonomous trading daemon")
            return {"success": True, "message": self.last_message}

    def get_status(self) -> Dict[str, Any]:
        """Returns current operational status and account summary."""
        state = portfolio.get_account_state()
        equity = state.get("equity", 100.0)
        initial_cap = state.get("initial_balance", 100.0)
        target_cap = self.target_equity
        progress_pct = max(0.0, min(100.0, ((equity - initial_cap) / max(target_cap - initial_cap, 1.0)) * 100.0))
        multiplier = round(equity / max(initial_cap, 1.0), 2)

        return {
            "is_running": self.is_running and (self.thread is not None and self.thread.is_alive()),
            "symbol": self.symbol,
            "interval": self.interval,
            "iteration_count": self.iteration_count,
            "last_run_time": self.last_run_time,
            "last_decision": self.last_decision,
            "last_message": self.last_message,
            "last_error": self.last_error,
            "balance": state.get("balance", 100.0),
            "equity": equity,
            "target_equity": target_cap,
            "progress_pct": round(progress_pct, 1),
            "equity_multiplier": multiplier,
            "hyper_compounding": self.hyper_compounding,
            "realized_pnl": state.get("realized_pnl", 0.0),
            "win_rate": state.get("win_rate", 0.0),
            "open_positions_count": len(state.get("open_positions", [])),
            "closed_trades_count": len(state.get("closed_trades", [])),
            "strategy_confluence": self.last_strategy_confluence,
            "compounding_metrics": self.last_compounding_metrics
        }


    def run_cycle_once(self) -> Dict[str, Any]:
        """Executes a single evaluation cycle (used by both loop and manual trigger)."""
        self.iteration_count += 1
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        self.last_run_time = now_str

        try:
            # 1. Fetch live market data
            df_h4, df_m15, current_price, data_source = get_market_data(self.symbol, count=config.CANDLES_COUNT)
            if current_price <= 0:
                msg = f"Failed to get valid price for {self.symbol}"
                self.last_message = msg
                return {"status": "error", "message": msg}

            # 2. Check open positions for TP/SL hits against current price
            closed_events = portfolio.check_and_update_positions(self.symbol, current_price)
            if closed_events:
                for ev in closed_events:
                    logger.info(f"Position closed! {ev['symbol']} {ev['action']} exit at ${ev['exit_price']:.2f} | PnL: ${ev['pnl']:+.2f} ({ev['exit_reason']})")
                self.last_message = f"🎯 Closed {len(closed_events)} position(s)! Latest PnL: ${closed_events[0]['pnl']:+.2f}"

            # 3. Assess current open positions
            state = portfolio.get_account_state()
            open_pos = state.get("open_positions", [])

            # For $100 capital, max 1 concurrent position is permitted to ensure proper margin & risk management
            if len(open_pos) >= 1:
                active = open_pos[0]
                u_pnl = active.get("unrealized_pnl", 0.0)
                msg = f"Holding {active['action']} {active['volume']} lots @ ${active['entry_price']:.2f} (Live: ${current_price:.2f} | PnL: ${u_pnl:+.2f}). Monitoring TP/SL..."
                self.last_message = msg
                self.last_decision = f"HOLD ({active['action']} active)"
                return {"status": "holding", "message": msg, "current_price": current_price}

            # 4. No active position — Run AI Brain Analysis
            provider = "Antigravity"
            decision_data, model_used = analyze_market(
                symbol=self.symbol,
                current_price=current_price,
                df_h4=df_h4,
                df_m15=df_m15,
                provider=provider,
                model_name="Antigravity (Zero-API / Native)"
            )

            decision = (decision_data.get("decision") or "HOLD").upper().strip()
            try:
                confidence = int(decision_data.get("confidence") or 50)
            except (ValueError, TypeError):
                confidence = 50

            try:
                sl = float(decision_data.get("stop_loss") or 0.0)
            except (ValueError, TypeError):
                sl = 0.0

            try:
                tp = float(decision_data.get("take_profit") or 0.0)
            except (ValueError, TypeError):
                tp = 0.0

            self.last_decision = f"{decision} ({confidence}%)"


            if "strategies" in decision_data:
                self.last_strategy_confluence = decision_data.get("strategies", {})

            # 5. Execution decision
            if decision in ["BUY", "SELL"] and confidence >= self.min_confidence:
                # Sanity check SL & TP distances
                if sl == 0.0 or tp == 0.0:
                    atr = float(df_m15["atr"].dropna().iloc[-1]) if (df_m15 is not None and "atr" in df_m15.columns and not df_m15["atr"].dropna().empty) else 8.0
                    if decision == "BUY":
                        sl = current_price - (atr * 1.5)
                        tp = current_price + (atr * 2.5)
                    else:
                        sl = current_price + (atr * 1.5)
                        tp = current_price - (atr * 2.5)

                # Dynamic Hyper-Compounding Lot Calculation ($100 -> $10,000 engine)
                equity = state.get("equity", 100.0)
                if self.hyper_compounding:
                    comp = strategy_engine.calculate_compounded_position_size(
                        account_equity=equity,
                        entry_price=current_price,
                        stop_loss=sl,
                        symbol=self.symbol,
                        confidence=confidence
                    )
                    exec_lot = comp["lot_size"]
                    self.last_compounding_metrics = comp
                else:
                    exec_lot = self.lot_size

                comment = f"AutoTrader-{decision}-{confidence}%-L{exec_lot}"
                result = execute_trade(
                    symbol=self.symbol,
                    decision=decision,
                    lot_size=exec_lot,
                    sl=sl,
                    tp=tp,
                    comment=comment,
                    current_price=current_price
                )

                if result.get("success"):
                    order_id = result.get("order_id", f"POS-{int(time.time()*1000)%10000000}")
                    msg = f"🚀 Executed {decision} {exec_lot} lots @ ${current_price:.2f} | SL: ${sl:.2f} | TP: ${tp:.2f} (Conviction: {confidence}%)"
                    self.last_message = msg
                    logger.info(msg)

                    # Generate visual chart snapshot & record in Trading Journal
                    try:
                        from chart_snapshot import generate_trade_screenshot
                        import journal
                        screenshot_file = generate_trade_screenshot(
                            df=df_m15,
                            symbol=self.symbol,
                            action=decision,
                            entry_price=current_price,
                            sl=sl,
                            tp=tp,
                            position_id=order_id,
                            confidence=confidence
                        )
                        journal.create_journal_entry(
                            trade_id=order_id,
                            symbol=self.symbol,
                            action=decision,
                            entry_price=current_price,
                            volume=exec_lot,
                            sl=sl,
                            tp=tp,
                            confidence=confidence,
                            h4_analysis=decision_data.get("h4_trend_analysis", ""),
                            m15_analysis=decision_data.get("m15_setup_analysis", ""),
                            reasoning=decision_data.get("reasoning", ""),
                            screenshot_path=screenshot_file
                        )
                    except Exception as je:
                        logger.error(f"Failed to generate trade screenshot/journal: {je}")
                else:
                    msg = f"Order failed: {result.get('message')}"
                    self.last_message = msg
            else:
                msg = f"Quantitative Signal: {decision} ({confidence}%). Below {self.min_confidence}% threshold or HOLD. Capital preserved."
                self.last_message = msg

            self.last_error = None
            return {
                "status": "success",
                "decision": decision,
                "confidence": confidence,
                "current_price": current_price,
                "message": self.last_message
            }

        except Exception as e:
            err = f"Cycle error: {str(e)}"
            self.last_error = err
            self.last_message = err
            logger.error(err, exc_info=True)
            return {"status": "error", "error": err}

    def _run_loop(self):
        """Internal background loop running at defined intervals."""
        logger.info(f"AutoTrader background loop active. Checking every {self.interval}s...")
        while not self.stop_event.is_set():
            self.run_cycle_once()
            # Sleep in 1-second chunks to respond quickly to stop_event
            for _ in range(int(self.interval)):
                if self.stop_event.is_set():
                    break
                time.sleep(1)

        self.is_running = False
        logger.info("AutoTrader loop terminated.")


# Module singleton
_trader = AutonomousTrader()


def get_auto_trader() -> AutonomousTrader:
    """Returns the singleton AutonomousTrader instance."""
    return _trader
