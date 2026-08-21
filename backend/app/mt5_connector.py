"""MetaTrader 5 connector for Forex data.

This module provides functionality to connect to MT5 terminal and fetch
historical OHLCV data for Forex instruments (EURUSD, GBPUSD, XAUUSD).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Literal
import sys

logger = logging.getLogger(__name__)

# Try to import MetaTrader5, provide helpful error if not available
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 not installed. Install with: pip install MetaTrader5")


# ============================================================
# TYPES
# ============================================================

ForexSymbol = Literal["EURUSD", "GBPUSD", "XAUUSD"]
MT5Timeframe = Literal["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"]

# Mapping from our timeframe notation to MT5 constants
TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1 if MT5_AVAILABLE else None,
    "M5": mt5.TIMEFRAME_M5 if MT5_AVAILABLE else None,
    "M15": mt5.TIMEFRAME_M15 if MT5_AVAILABLE else None,
    "M30": mt5.TIMEFRAME_M30 if MT5_AVAILABLE else None,
    "H1": mt5.TIMEFRAME_H1 if MT5_AVAILABLE else None,
    "H4": mt5.TIMEFRAME_H4 if MT5_AVAILABLE else None,
    "D1": mt5.TIMEFRAME_D1 if MT5_AVAILABLE else None,
    "W1": mt5.TIMEFRAME_W1 if MT5_AVAILABLE else None,
    "MN1": mt5.TIMEFRAME_MN1 if MT5_AVAILABLE else None,
}

# Mapping from standard format to MT5 format
STANDARD_TO_MT5 = {
    "1m": "M1", "5m": "M5", "15m": "M15", "30m": "M30",
    "1h": "H1", "4h": "H4", "1d": "D1", "1w": "W1", "1M": "MN1"
}


# ============================================================
# MT5 CONNECTOR CLASS
# ============================================================

class MT5Connector:
    """
    Connector for MetaTrader 5 terminal.
    
    Provides methods to:
    - Connect to MT5 terminal
    - Fetch historical OHLCV data
    - Get current tick data
    - Check connection status
    """
    
    def __init__(self):
        self._connected = False
        self._initialized = False
    
    def initialize(self) -> bool:
        """
        Initialize MT5 connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        if not MT5_AVAILABLE:
            logger.error("MetaTrader5 not available. Install with: pip install MetaTrader5")
            return False
        
        if self._initialized and self._connected:
            return True
        
        try:
            if not mt5.initialize():
                logger.error(f"MT5 initialize failed: {mt5.last_error()}")
                return False
            
            self._initialized = True
            self._connected = True
            logger.info("MT5 connection established successfully")
            return True
            
        except Exception as e:
            logger.error(f"MT5 initialization error: {e}")
            return False
    
    def shutdown(self) -> bool:
        """
        Shutdown MT5 connection.
        
        Returns:
            True if shutdown successful
        """
        if not self._initialized:
            return True
        
        try:
            mt5.shutdown()
            self._connected = False
            self._initialized = False
            logger.info("MT5 connection closed")
            return True
        except Exception as e:
            logger.error(f"MT5 shutdown error: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if MT5 is connected."""
        if not MT5_AVAILABLE or not self._initialized:
            return False
        
        try:
            # Try to get terminal info to verify connection
            terminal_info = mt5.terminal_info()
            if terminal_info is None:
                return False
            return terminal_info.connected
        except Exception:
            return False
    
    def fetch_ohlcv(
        self,
        symbol: ForexSymbol,
        timeframe: str,
        limit: int = 500,
        start_date: datetime | None = None,
        end_date: datetime | None = None
    ) -> list[dict]:
        """
        Fetch OHLCV data from MT5.
        
        Args:
            symbol: Forex symbol (EURUSD, GBPUSD, XAUUSD)
            timeframe: Timeframe in standard format (1h, 4h, etc.) or MT5 format (H1, H4, etc.)
            limit: Number of candles to fetch
            start_date: Start date for data fetch (optional)
            end_date: End date for data fetch (optional)
        
        Returns:
            List of OHLCV candles with keys: time, open, high, low, close, volume
        """
        if not self.initialize():
            logger.error("Cannot fetch OHLCV: MT5 not connected")
            return []
        
        # Convert timeframe to MT5 format
        mt5_tf = self._convert_timeframe(timeframe)
        if mt5_tf is None:
            logger.error(f"Invalid timeframe: {timeframe}")
            return []
        
        try:
            # Set date range
            if start_date is None:
                start_date = datetime.now(timezone.utc) - timedelta(days=365)
            if end_date is None:
                end_date = datetime.now(timezone.utc)
            
            # Fetch data from MT5
            rates = mt5.copy_rates_range(
                symbol,
                mt5_tf,
                start_date,
                end_date
            )
            
            if rates is None or len(rates) == 0:
                logger.warning(f"No data returned for {symbol} {timeframe}")
                return []
            
            # Convert to list of dicts (most recent first)
            candles = []
            for rate in rates[-limit:]:  # Get last N candles
                candles.append({
                    "time": datetime.fromtimestamp(rate["time"], tz=timezone.utc).isoformat(),
                    "open": float(rate["open"]),
                    "high": float(rate["high"]),
                    "low": float(rate["low"]),
                    "close": float(rate["close"]),
                    "volume": int(rate["tick_volume"]),  # Use tick_volume for forex
                })
            
            logger.debug(f"Fetched {len(candles)} candles for {symbol} {timeframe}")
            return candles
            
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol} {timeframe}: {e}")
            return []
    
    def fetch_tick(self, symbol: ForexSymbol) -> dict | None:
        """
        Fetch current tick data for a symbol.
        
        Args:
            symbol: Forex symbol
        
        Returns:
            Tick data dict or None if failed
        """
        if not self.initialize():
            return None
        
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                logger.warning(f"No tick data for {symbol}")
                return None
            
            return {
                "symbol": symbol,
                "bid": float(tick.bid),
                "ask": float(tick.ask),
                "spread": float(tick.ask - tick.bid),
                "time": datetime.fromtimestamp(tick.time, tz=timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error(f"Error fetching tick for {symbol}: {e}")
            return None
    
    def get_symbol_info(self, symbol: ForexSymbol) -> dict | None:
        """
        Get symbol information from MT5.
        
        Args:
            symbol: Forex symbol
        
        Returns:
            Symbol info dict or None if failed
        """
        if not self.initialize():
            return None
        
        try:
            info = mt5.symbol_info(symbol)
            if info is None:
                logger.warning(f"No symbol info for {symbol}")
                return None
            
            return {
                "symbol": symbol,
                "description": info.description,
                "point": float(info.point),
                "digits": int(info.digits),
                "spread": float(info.spread),
                "trade_tick_size": float(info.trade_tick_size),
                "trade_contract_size": float(info.trade_contract_size),
            }
        except Exception as e:
            logger.error(f"Error getting symbol info for {symbol}: {e}")
            return None
    
    def _convert_timeframe(self, timeframe: str) -> int | None:
        """Convert timeframe string to MT5 constant."""
        # Try standard format first (1h, 4h, etc.)
        if timeframe in STANDARD_TO_MT5:
            mt5_tf = STANDARD_TO_MT5[timeframe]
            return TIMEFRAME_MAP.get(mt5_tf)
        
        # Try MT5 format directly (H1, H4, etc.)
        return TIMEFRAME_MAP.get(timeframe)
    
    def check_symbol_available(self, symbol: ForexSymbol) -> bool:
        """
        Check if a symbol is available in MT5.
        
        Args:
            symbol: Forex symbol
        
        Returns:
            True if symbol is available
        """
        if not self.initialize():
            return False
        
        try:
            info = mt5.symbol_info(symbol)
            return info is not None and info.visible
        except Exception:
            return False


# ============================================================
# GLOBAL INSTANCE
# ============================================================

mt5_connector = MT5Connector()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def fetch_forex_ohlcv(
    symbol: ForexSymbol,
    timeframe: str,
    limit: int = 500,
    start_date: datetime | None = None,
    end_date: datetime | None = None
) -> list[dict]:
    """
    Convenience function to fetch Forex OHLCV data.
    
    Args:
        symbol: Forex symbol (EURUSD, GBPUSD, XAUUSD)
        timeframe: Timeframe (1h, 4h, M15, etc.)
        limit: Number of candles
        start_date: Optional start date
        end_date: Optional end date
    
    Returns:
        List of OHLCV candles
    """
    return mt5_connector.fetch_ohlcv(symbol, timeframe, limit, start_date, end_date)


def fetch_forex_tick(symbol: ForexSymbol) -> dict | None:
    """
    Convenience function to fetch current Forex tick.
    
    Args:
        symbol: Forex symbol
    
    Returns:
        Tick data or None
    """
    return mt5_connector.fetch_tick(symbol)


def initialize_mt5() -> bool:
    """Initialize MT5 connection."""
    return mt5_connector.initialize()


def shutdown_mt5() -> bool:
    """Shutdown MT5 connection."""
    return mt5_connector.shutdown()


def is_mt5_available() -> bool:
    """Check if MT5 is available and connected."""
    return MT5_AVAILABLE and mt5_connector.is_connected()


def get_available_symbols() -> list[ForexSymbol]:
    """
    Get list of available Forex symbols in MT5.
    
    Returns:
        List of available symbols
    """
    if not mt5_connector.initialize():
        return []
    
    forex_symbols = []
    for symbol in ["EURUSD", "GBPUSD", "XAUUSD"]:
        if mt5_connector.check_symbol_available(symbol):
            forex_symbols.append(symbol)
    
    return forex_symbols
