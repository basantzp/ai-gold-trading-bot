"""
Chart Snapshot Engine: Generates professional dark-mode TradingView-style
candlestick chart screenshots with trade entry markers, TP, SL, and RSI indicators.
"""

import os
from pathlib import Path
from typing import Optional
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Non-interactive background rendering
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle

SCREENSHOTS_DIR = Path(__file__).parent / "trade_screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)


def generate_trade_screenshot(
    df: pd.DataFrame,
    symbol: str,
    action: str,
    entry_price: float,
    sl: float,
    tp: float,
    position_id: str,
    confidence: int = 70
) -> Optional[str]:
    """
    Renders a high-resolution dark-mode candlestick chart with trade overlays
    and saves it to trade_screenshots/{position_id}.png.

    Returns the file path of the generated screenshot.
    """
    if df is None or df.empty or len(df) < 5:
        return None

    try:
        df = df.copy().tail(40).reset_index(drop=True)
        filename = f"{position_id}.png"
        filepath = SCREENSHOTS_DIR / filename

        # Styling
        plt.style.use("dark_background")
        fig, (ax_main, ax_rsi) = plt.subplots(
            2, 1,
            figsize=(11, 6),
            gridspec_kw={"height_ratios": [3, 1]},
            facecolor="#131722"
        )
        ax_main.set_facecolor("#131722")
        ax_rsi.set_facecolor("#131722")

        # Plot Candlesticks
        green_candle = "#26a69a"
        red_candle = "#ef5350"
        indices = list(range(len(df)))

        for i in indices:
            row = df.iloc[i]
            open_p, high_p, low_p, close_p = row["open"], row["high"], row["low"], row["close"]
            color = green_candle if close_p >= open_p else red_candle

            # High-Low Wick
            ax_main.vlines(i, low_p, high_p, color=color, linewidth=1.2, alpha=0.9)
            # Body
            body_bottom = min(open_p, close_p)
            body_height = max(abs(close_p - open_p), 0.2)
            rect = Rectangle((i - 0.35, body_bottom), 0.7, body_height, color=color, alpha=0.95)
            ax_main.add_patch(rect)

        # Plot Moving Averages if available
        if "sma_7" in df.columns:
            ax_main.plot(indices, df["sma_7"], color="#38bdf8", linewidth=1.1, label="SMA 7", alpha=0.8)
        if "ema_14" in df.columns:
            ax_main.plot(indices, df["ema_14"], color="#fbbf24", linewidth=1.1, label="EMA 14", alpha=0.8)

        # Plot Trade Levels
        last_x = indices[-1]
        x_span = [indices[0], last_x + 3]

        # Entry Line
        ax_main.axhline(y=entry_price, color="#38bdf8", linestyle="-.", linewidth=1.5, alpha=0.85)
        ax_main.text(
            last_x + 0.5, entry_price,
            f"  ENTRY: ${entry_price:,.2f}",
            color="#38bdf8", fontsize=9, va="center", fontweight="bold"
        )

        # Take Profit Line
        if tp and tp > 0:
            ax_main.axhline(y=tp, color="#10b981", linestyle="--", linewidth=1.5, alpha=0.85)
            ax_main.text(
                last_x + 0.5, tp,
                f"  TP: ${tp:,.2f} (+Target)",
                color="#10b981", fontsize=9, va="center", fontweight="bold"
            )

        # Stop Loss Line
        if sl and sl > 0:
            ax_main.axhline(y=sl, color="#ef4444", linestyle="--", linewidth=1.5, alpha=0.85)
            ax_main.text(
                last_x + 0.5, sl,
                f"  SL: ${sl:,.2f} (-Risk)",
                color="#ef4444", fontsize=9, va="center", fontweight="bold"
            )

        # Trade Direction Marker Arrow at entry candle
        arrow_color = "#10b981" if action.upper() == "BUY" else "#ef4444"
        arrow_symbol = "▲ BUY" if action.upper() == "BUY" else "▼ SELL"
        offset = (df["high"].max() - df["low"].min()) * 0.04
        marker_y = entry_price - offset if action.upper() == "BUY" else entry_price + offset
        ax_main.annotate(
            f"{arrow_symbol} ({confidence}%)",
            xy=(last_x, entry_price),
            xytext=(last_x - 3, marker_y),
            arrowprops=dict(facecolor=arrow_color, edgecolor=arrow_color, arrowstyle="->", lw=2),
            color=arrow_color,
            fontweight="bold",
            fontsize=10,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#1e222d", edgecolor=arrow_color, alpha=0.9)
        )

        ax_main.set_title(
            f"⚡ [TRADE SNAPSHOT] {symbol} — {action.upper()} @ ${entry_price:,.2f} | Conviction: {confidence}%",
            color="#f8fafc", fontsize=12, fontweight="bold", pad=12
        )
        ax_main.set_xlim(indices[0] - 1, last_x + 5)
        ax_main.grid(True, color="#1e222d", linestyle="--", linewidth=0.5)
        ax_main.set_ylabel("Price (USD)", color="#94a3b8", fontsize=9)
        ax_main.tick_params(colors="#94a3b8")
        ax_main.legend(loc="upper left", facecolor="#1e222d", edgecolor="#334155", fontsize=8)

        # RSI Panel
        if "rsi_14" in df.columns:
            ax_rsi.plot(indices, df["rsi_14"], color="#a78bfa", linewidth=1.2, label="RSI 14")
            ax_rsi.axhline(70, color="#ef4444", linestyle=":", linewidth=0.8, alpha=0.7)
            ax_rsi.axhline(30, color="#10b981", linestyle=":", linewidth=0.8, alpha=0.7)
            ax_rsi.fill_between(indices, 70, df["rsi_14"], where=(df["rsi_14"] >= 70), color="#ef4444", alpha=0.2)
            ax_rsi.fill_between(indices, 30, df["rsi_14"], where=(df["rsi_14"] <= 30), color="#10b981", alpha=0.2)
            ax_rsi.set_ylim(10, 90)
            ax_rsi.set_ylabel("RSI (14)", color="#94a3b8", fontsize=8)
        else:
            ax_rsi.text(0.5, 0.5, "RSI Computing...", color="#64748b", ha="center", va="center")

        ax_rsi.set_xlim(indices[0] - 1, last_x + 5)
        ax_rsi.grid(True, color="#1e222d", linestyle="--", linewidth=0.5)
        ax_rsi.tick_params(colors="#94a3b8")

        # Time labels on bottom x-axis
        if "time" in df.columns:
            step = max(1, len(df) // 6)
            ticks = indices[::step]
            labels = [str(df.iloc[t]["time"])[-8:-3] for t in ticks]
            ax_rsi.set_xticks(ticks)
            ax_rsi.set_xticklabels(labels, rotation=0, fontsize=8)

        plt.tight_layout()
        fig.savefig(filepath, dpi=120, facecolor=fig.get_facecolor(), edgecolor="none")
        plt.close(fig)
        return str(filepath)

    except Exception as e:
        print(f"[CHART_SNAPSHOT] Error generating screenshot: {e}")
        return None
