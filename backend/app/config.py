"""Centralized configuration — all env vars with safe defaults.

Every configurable value in AEGIS lives here. Modules import from this
file instead of calling os.getenv() directly.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# --- Load .env ---
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


def _decrypt_env(value: str) -> str:
    """Decrypt ENV values that start with ENC: prefix."""
    if not value.startswith("ENC:"):
        return value
    try:
        from .secrets_crypto import decrypt_value, get_key
        key = get_key()
        if key:
            return decrypt_value(value, key)
    except Exception:
        pass
    return value

# --- Mode ---
MODE = os.getenv("AEGIS_MODE", "paper")  # "paper" | "live"
ADMIN_TOKEN = _decrypt_env(os.getenv("AEGIS_ADMIN_TOKEN", ""))
CORS_ORIGINS = os.getenv("AEGIS_CORS_ORIGINS", "http://localhost:5173").split(",")
PAPER_CAPITAL = float(os.getenv("AEGIS_INITIAL_CAPITAL", "20"))

# --- ICT/SMC Bot Capital ---
ICT_PAPER_CAPITAL = float(os.getenv("AEGIS_ICT_CAPITAL", "50"))  # 50€ pour le bot ICT/SMC

# --- Database ---
DB_PATH = os.getenv("AEGIS_DB_PATH", str(Path(__file__).resolve().parent.parent / "data" / "aegis.db"))

# --- Supabase (optional — used for cloud deployment) ---
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)

# --- Ports ---
API_HOST = os.getenv("AEGIS_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("AEGIS_API_PORT", "8000"))
WEB_PORT = int(os.getenv("AEGIS_WEB_PORT", "80"))

# --- Trading Limits ---
MAX_ORDER_NOTIONAL = float(os.getenv("AEGIS_MAX_ORDER_NOTIONAL", "18"))
MAX_TOTAL_EXPOSURE = float(os.getenv("AEGIS_MAX_TOTAL_EXPOSURE", "20"))

# --- Execution Defaults ---
DEFAULT_FEE_BPS = float(os.getenv("AEGIS_DEFAULT_FEE_BPS", "10"))
DEFAULT_SLIPPAGE_BPS = float(os.getenv("AEGIS_DEFAULT_SLIPPAGE_BPS", "5"))
DEFAULT_CHUNKS = int(os.getenv("AEGIS_DEFAULT_CHUNKS", "3"))
DEFAULT_DELAY_MS = int(os.getenv("AEGIS_DEFAULT_DELAY_MS", "500"))

# --- Timeouts (seconds) ---
HTTP_TIMEOUT = int(os.getenv("AEGIS_HTTP_TIMEOUT", "15"))
AI_TIMEOUT = int(os.getenv("AEGIS_AI_TIMEOUT", "30"))
WS_PROXY_TIMEOUT = int(os.getenv("AEGIS_WS_PROXY_TIMEOUT", "86400"))

# --- AI / OpenCode Zen (primary) ---
OPENCODE_API_KEY = _decrypt_env(os.getenv("OPENCODE_API_KEY", ""))
OPENCODE_MODEL = os.getenv("AEGIS_OPENCODE_MODEL", "nemotron-3-ultra-free")
OPENCODE_BASE_URL = os.getenv("AEGIS_OPENCODE_BASE_URL", "https://opencode.ai/zen/v1")
OPENCODE_TEMPERATURE = float(os.getenv("AEGIS_OPENCODE_TEMPERATURE", "0.3"))
OPENCODE_MAX_TOKENS = int(os.getenv("AEGIS_OPENCODE_MAX_TOKENS", "2048"))

# --- AI / OpenRouter (fallback gratuit) ---
OPENROUTER_API_KEY = _decrypt_env(os.getenv("OPENROUTER_API_KEY", ""))
OPENROUTER_MODEL = os.getenv("AEGIS_OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
OPENROUTER_BASE_URL = os.getenv("AEGIS_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_TEMPERATURE = float(os.getenv("AEGIS_OPENROUTER_TEMPERATURE", "0.3"))
OPENROUTER_MAX_TOKENS = int(os.getenv("AEGIS_OPENROUTER_MAX_TOKENS", "2048"))

# --- CCXT Exchange ---
CCXT_EXCHANGE_ID = os.getenv("AEGIS_CCXT_EXCHANGE_ID", "binance")
CCXT_TESTNET = os.getenv("AEGIS_CCXT_TESTNET", "true").lower() == "true"

# --- Live Exchange Credentials (paper mode ignores these) ---
LIVE_EXCHANGE_ID = os.getenv("AEGIS_LIVE_EXCHANGE_ID", "binance")
LIVE_API_KEY = _decrypt_env(os.getenv("AEGIS_LIVE_API_KEY", ""))
LIVE_API_SECRET = _decrypt_env(os.getenv("AEGIS_LIVE_API_SECRET", ""))
LIVE_TESTNET = os.getenv("AEGIS_LIVE_TESTNET", "true").lower() == "true"
LIVE_EXCHANGE_OPTIONS = os.getenv("AEGIS_LIVE_EXCHANGE_OPTIONS", "{}")  # JSON dict of extra options

# --- Order Execution ---
ORDER_RETRY_ATTEMPTS = int(os.getenv("AEGIS_ORDER_RETRY_ATTEMPTS", "3"))
ORDER_RETRY_DELAY = float(os.getenv("AEGIS_ORDER_RETRY_DELAY", "1.0"))  # seconds
ORDER_TIMEOUT = int(os.getenv("AEGIS_ORDER_TIMEOUT", "30"))  # seconds
ORDER_MIN_NOTIONAL = float(os.getenv("AEGIS_ORDER_MIN_NOTIONAL", "10"))  # min order value
ORDER_MAX_SLIPPAGE_BPS = float(os.getenv("AEGIS_ORDER_MAX_SLIPPAGE_BPS", "50"))  # abort if > 0.5%

# --- Binance ---
BINANCE_TESTNET_API_KEY = _decrypt_env(os.getenv("BINANCE_TESTNET_API_KEY", ""))
BINANCE_TESTNET_API_SECRET = _decrypt_env(os.getenv("BINANCE_TESTNET_API_SECRET", ""))
BINANCE_SPOT_URL = os.getenv("AEGIS_BINANCE_SPOT_URL", "https://api.binance.com/api/v3")
BINANCE_FUTURES_URL = os.getenv("AEGIS_BINANCE_FUTURES_URL", "https://fapi.binance.com/fapi/v1")
BINANCE_TESTNET_SPOT_URL = os.getenv("AEGIS_TESTNET_SPOT_URL", "https://testnet.binance.vision/api/v3")
BINANCE_TESTNET_FUTURES_URL = os.getenv("AEGIS_TESTNET_FUTURES_URL", "https://testnet.binancefuture.com/fapi/v1")
BINANCE_TESTNET_SPOT_WS = os.getenv("AEGIS_TESTNET_SPOT_WS", "wss://testnet.binance.vision/ws")
BINANCE_TESTNET_FUTURES_WS = os.getenv("AEGIS_TESTNET_FUTURES_WS", "wss://testnet.binancefuture.com/ws")

# --- Free API URLs ---
COINGECKO_URL = os.getenv("AEGIS_COINGECKO_URL", "https://api.coingecko.com/api/v3")
DEFILLAMA_URL = os.getenv("AEGIS_DEFILLAMA_URL", "https://api.llama.fi")
DEFILLAMA_YIELDS_URL = os.getenv("AEGIS_DEFILLAMA_YIELDS_URL", "https://yields.llama.fi")
PERPFINDER_URL = os.getenv("AEGIS_PERPFINDER_URL", "https://api.perpfinder.com")
MEMPOOL_URL = os.getenv("AEGIS_MEMPOOL_URL", "https://mempool.space/api")
DEXSCREENER_URL = os.getenv("AEGIS_DEXSCREENER_URL", "https://api.dexscreener.com")
COINPAPRIKA_URL = os.getenv("AEGIS_COINPAPRIKA_URL", "https://api.coinpaprika.com")
FRANKFURTER_URL = os.getenv("AEGIS_FRANKFURTER_URL", "https://api.frankfurter.app")
POLYMARKET_URL = os.getenv("AEGIS_POLYMARKET_URL", "https://gamma-api.polymarket.com")
COINLORE_URL = os.getenv("AEGIS_COINLORE_URL", "https://api.coinlore.net")
TERMINALFEED_URL = os.getenv("AEGIS_TERMINALFEED_URL", "https://terminalfeed.io")
BLOCKSTREAM_URL = os.getenv("AEGIS_BLOCKSTREAM_URL", "https://blockstream.info/api")
FEAR_GREED_URL = os.getenv("AEGIS_FEAR_GREED_URL", "https://api.alternative.me/fng/?limit=1&format=json")
TWELVEDATA_URL = os.getenv("AEGIS_TWELVEDATA_URL", "https://api.twelvedata.com")
YAHOO_FINANCE_URL = os.getenv("AEGIS_YAHOO_FINANCE_URL", "https://query1.finance.yahoo.com/v8/finance/chart")
FOREX_API_URL = os.getenv("AEGIS_FOREX_API_URL", "https://open.er-api.com/v6/latest")
FINNHUB_URL = os.getenv("AEGIS_FINNHUB_URL", "https://finnhub.io/api/v1")
FINNHUB_API_KEY = _decrypt_env(os.getenv("FINNHUB_API_KEY", ""))

# --- Telegram ---
TELEGRAM_BOT_TOKEN = _decrypt_env(os.getenv("TELEGRAM_BOT_TOKEN", ""))
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Thread Pool ---
FREE_API_WORKERS = int(os.getenv("AEGIS_FREE_API_WORKERS", "6"))

# --- Symbols ---
SYMBOLS = os.getenv("AEGIS_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT").split(",")

# --- ICT/SMC Bot Configuration (Forex Instruments) ---
# Configuration spécifique pour le bot ICT/SMC avec instruments Forex
ICT_SYMBOLS = os.getenv("AEGIS_ICT_SYMBOLS", "EURUSD,GBPUSD,XAUUSD").split(",")
ICT_PRIMARY_INSTRUMENT = os.getenv("AEGIS_ICT_PRIMARY", "EURUSD")

# --- Focused Single-Strategy Mode (Phase 1) ---
# AEGIS is reduced to ONE trade type: Donchian Breakout on a maximum of
# 3 symbols. All 15 modules collaborate for this single strategy.
FOCUSED_MODE = os.getenv("AEGIS_FOCUSED_MODE", "true").lower() == "true"
FOCUSED_STRATEGY = os.getenv("AEGIS_FOCUSED_STRATEGY", "donchian_breakout_long_flat")
FOCUSED_SYMBOLS = os.getenv("AEGIS_FOCUSED_SYMBOLS", "PAXGUSDT,BTCUSDT,ETHUSDT").split(",")
if FOCUSED_SYMBOLS == [""]:
    FOCUSED_SYMBOLS = SYMBOLS
MAX_POSITIONS = int(os.getenv("AEGIS_MAX_POSITIONS", "3"))
DONCHIAN_PARAMS = {
    "breakout_period": int(os.getenv("AEGIS_DONCHIAN_BREAKOUT_PERIOD", "20")),
    "exit_period": int(os.getenv("AEGIS_DONCHIAN_EXIT_PERIOD", "10")),
}

# --- ICT/SMC Mode (Cahier des charges) ---
# When enabled, the engine uses the full ICT/SMC pipeline:
# multi-TF analysis → signal generator → risk manager → position manager.
# Instruments: EUR/USD, GBP/USD, XAU/USD with 50€ capital.
ICT_MODE = os.getenv("AEGIS_ICT_MODE", "false").lower() == "true"

# --- Alert Thresholds ---
ALERT_MAX_DRAWDOWN_PCT = float(os.getenv("AEGIS_ALERT_MAX_DRAWDOWN_PCT", "15"))
ALERT_VAR_95_PCT = float(os.getenv("AEGIS_ALERT_VAR_95_PCT", "5"))
ALERT_RSI_OVERBOUGHT = float(os.getenv("AEGIS_ALERT_RSI_OVERBOUGHT", "75"))
ALERT_RSI_OVERSOLD = float(os.getenv("AEGIS_ALERT_RSI_OVERSOLD", "25"))
ALERT_VOLATILITY_SPIKE = float(os.getenv("AEGIS_ALERT_VOLATILITY_SPIKE", "0.05"))
ALERT_POSITION_LIMIT_PCT = float(os.getenv("AEGIS_ALERT_POSITION_LIMIT_PCT", "80"))
ALERT_FUNDING_RATE_EXTREME = float(os.getenv("AEGIS_ALERT_FUNDING_RATE_EXTREME", "0.001"))
ALERT_HISTORY_LIMIT = int(os.getenv("AEGIS_ALERT_HISTORY_LIMIT", "500"))

# --- Deployment Stage Thresholds ---
DEPLOYMENT_STAGES = {
    "backtest": {
        "min_sharpe": float(os.getenv("AEGIS_DEPLOY_BACKTEST_MIN_SHARPE", "0.0")),
        "min_trades": int(os.getenv("AEGIS_DEPLOY_BACKTEST_MIN_TRADES", "5")),
    },
    "walk_forward": {
        "min_sharpe": float(os.getenv("AEGIS_DEPLOY_WF_MIN_SHARPE", "0.3")),
        "min_trades": int(os.getenv("AEGIS_DEPLOY_WF_MIN_TRADES", "10")),
        "max_drawdown": float(os.getenv("AEGIS_DEPLOY_WF_MAX_DRAWDOWN", "-0.20")),
    },
    "paper_trading": {
        "min_sharpe": float(os.getenv("AEGIS_DEPLOY_PAPER_MIN_SHARPE", "0.5")),
        "min_trades": int(os.getenv("AEGIS_DEPLOY_PAPER_MIN_TRADES", "20")),
        "max_drawdown": float(os.getenv("AEGIS_DEPLOY_PAPER_MAX_DRAWDOWN", "-0.15")),
    },
    "validation": {
        "min_sharpe": float(os.getenv("AEGIS_DEPLOY_VALID_MIN_SHARPE", "0.7")),
        "min_trades": int(os.getenv("AEGIS_DEPLOY_VALID_MIN_TRADES", "30")),
        "max_drawdown": float(os.getenv("AEGIS_DEPLOY_VALID_MAX_DRAWDOWN", "-0.12")),
    },
}

# --- Autonomous Engine ---
ENGINE_ENABLED = os.getenv("AEGIS_ENGINE_ENABLED", "true").lower() == "true"
ENGINE_INTERVAL_PRICES = int(os.getenv("AEGIS_ENGINE_INTERVAL_PRICES", "60"))       # seconds
ENGINE_INTERVAL_ANALYSIS = int(os.getenv("AEGIS_ENGINE_INTERVAL_ANALYSIS", "300"))  # seconds
ENGINE_INTERVAL_SIGNALS = int(os.getenv("AEGIS_ENGINE_INTERVAL_SIGNALS", "600"))    # seconds
ENGINE_INTERVAL_OPTIMIZE = int(os.getenv("AEGIS_ENGINE_INTERVAL_OPTIMIZE", "3600")) # seconds
ENGINE_INTERVAL_DAILY_REPORT = int(os.getenv("AEGIS_ENGINE_INTERVAL_DAILY_REPORT", "86400"))  # seconds
ENGINE_INTERVAL_TRAILING_STOPS = int(os.getenv("AEGIS_ENGINE_INTERVAL_TRAILING", "10"))  # seconds
ENGINE_MAX_CONSECUTIVE_ERRORS = int(os.getenv("AEGIS_ENGINE_MAX_ERRORS", "5"))
ENGINE_ERROR_BACKOFF = int(os.getenv("AEGIS_ENGINE_ERROR_BACKOFF", "30"))  # seconds

# --- Position Monitoring ---
POSITION_MAX_LOSS_PCT = float(os.getenv("AEGIS_POSITION_MAX_LOSS_PCT", "0.10"))
POSITION_MAX_DRAWDOWN_PCT = float(os.getenv("AEGIS_POSITION_MAX_DRAWDOWN_PCT", "0.15"))
PORTFOLIO_MAX_DRAWDOWN_PCT = float(os.getenv("AEGIS_PORTFOLIO_MAX_DRAWDOWN_PCT", "0.20"))
ENGINE_INTERVAL_POSITIONS = int(os.getenv("AEGIS_ENGINE_INTERVAL_POSITIONS", "15"))
