# Configuration for AI Hedge Fund MT5 Trading Bot
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project directory
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# ==========================================
# 1. MetaTrader 5 (MT5) Configuration
# ==========================================
# Enter your MT5 account credentials below or in .env
MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))  # Replace with your MT5 account number
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")  # Replace with your MT5 password
MT5_SERVER = os.getenv("MT5_SERVER", "")      # Replace with your broker server (e.g., 'MetaQuotes-Demo', 'Exness-Real', etc.)

# Default MT5 Windows terminal installation path
# e.g., r"C:\Program Files\MetaTrader 5\terminal64.exe"
MT5_PATH = os.getenv("MT5_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")

# ==========================================
# 2. AI Brain (Antigravity Zero-API, Gemini, Groq & OpenAI) Configuration
# ==========================================
# Native Antigravity CLI (Zero-API: Uses local authenticated agy session, no external API keys needed)
ANTIGRAVITY_ENABLED = os.getenv("ANTIGRAVITY_ENABLED", "true").lower() in ("true", "1", "yes")
ANTIGRAVITY_BIN = os.getenv("ANTIGRAVITY_BIN", "agy")

# Google Gemini API key: Get free API key from https://aistudio.google.com/app/apikey
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Groq API key: Get free API key from https://console.groq.com/keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

# Optional: OpenAI API fallback
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ==========================================
# 3. Trading & Risk Management Parameters
# ==========================================
DEFAULT_SYMBOL = os.getenv("DEFAULT_SYMBOL", "XAUUSD")
DEFAULT_LOT_SIZE = float(os.getenv("DEFAULT_LOT_SIZE", "0.01"))
SLIPPAGE_DEVIATION = int(os.getenv("SLIPPAGE_DEVIATION", "20"))
MAGIC_NUMBER = int(os.getenv("MAGIC_NUMBER", "998877"))

# Timeframes for multi-timeframe analysis
TIMEFRAME_HTF = "H4"   # Higher Timeframe: 4-Hour trend analysis
TIMEFRAME_LTF = "M15"  # Lower Timeframe: 15-Minute entry confirmation
CANDLES_COUNT = int(os.getenv("CANDLES_COUNT", "15"))

# Allow Paper/Simulation mode if MT5 is not running or on Linux/Mac
SIMULATION_MODE = os.getenv("SIMULATION_MODE", "auto")
