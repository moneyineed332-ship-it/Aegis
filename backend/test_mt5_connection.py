"""Test script for MT5 Forex connectivity.

This script tests the MT5 connector and verifies:
1. MT5 installation and connection
2. Symbol availability
3. OHLCV data fetching
4. Tick data fetching
"""

import sys
import logging
from datetime import datetime, timezone, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_mt5_connection():
    """Test MT5 connection and basic functionality."""
    try:
        from app.mt5_connector import (
            mt5_connector, 
            is_mt5_available, 
            initialize_mt5, 
            get_available_symbols,
            fetch_forex_ohlcv,
            fetch_forex_tick
        )
    except ImportError as e:
        logger.error(f"Failed to import MT5 connector: {e}")
        logger.info("Install MetaTrader5 with: pip install MetaTrader5")
        return False
    
    logger.info("=" * 60)
    logger.info("MT5 CONNECTION TEST")
    logger.info("=" * 60)
    
    # Test 1: Check availability
    logger.info("\n[TEST 1] Checking MT5 availability...")
    if not is_mt5_available():
        logger.error("MetaTrader5 is not available or not installed")
        return False
    logger.info("✓ MetaTrader5 is available")
    
    # Test 2: Initialize connection
    logger.info("\n[TEST 2] Initializing MT5 connection...")
    if not initialize_mt5():
        logger.error("Failed to initialize MT5 connection")
        logger.info("Make sure MetaTrader 5 terminal is running")
        return False
    logger.info("✓ MT5 connection initialized successfully")
    
    # Test 3: Check available symbols
    logger.info("\n[TEST 3] Checking available Forex symbols...")
    available_symbols = get_available_symbols()
    if not available_symbols:
        logger.warning("No Forex symbols available")
        logger.info("This might be normal if your MT5 terminal doesn't have Forex data")
    else:
        logger.info(f"✓ Available symbols: {available_symbols}")
    
    # Test 4: Test symbol info
    logger.info("\n[TEST 4] Testing symbol information...")
    test_symbol = available_symbols[0] if available_symbols else "EURUSD"
    try:
        symbol_info = mt5_connector.get_symbol_info(test_symbol)
        if symbol_info:
            logger.info(f"✓ {test_symbol} info: {symbol_info}")
        else:
            logger.warning(f"No symbol info for {test_symbol}")
    except Exception as e:
        logger.error(f"Error getting symbol info: {e}")
    
    # Test 5: Test OHLCV data fetching
    logger.info("\n[TEST 5] Testing OHLCV data fetching...")
    try:
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=7)
        
        candles = fetch_forex_ohlcv(
            symbol=test_symbol,
            timeframe="H1",
            limit=10,
            start_date=start_date,
            end_date=end_date
        )
        
        if candles:
            logger.info(f"✓ Fetched {len(candles)} OHLCV candles for {test_symbol} H1")
            logger.info(f"  Latest candle: {candles[-1]}")
        else:
            logger.warning(f"No OHLCV data fetched for {test_symbol}")
    except Exception as e:
        logger.error(f"Error fetching OHLCV: {e}")
    
    # Test 6: Test tick data
    logger.info("\n[TEST 6] Testing tick data fetching...")
    try:
        tick = fetch_forex_tick(test_symbol)
        if tick:
            logger.info(f"✓ Current tick for {test_symbol}: {tick}")
        else:
            logger.warning(f"No tick data for {test_symbol}")
    except Exception as e:
        logger.error(f"Error fetching tick: {e}")
    
    # Test 7: Test multiple timeframes
    logger.info("\n[TEST 7] Testing multiple timeframes...")
    timeframes = ["M5", "M15", "H1", "H4"]
    for tf in timeframes:
        try:
            candles = fetch_forex_ohlcv(test_symbol, tf, limit=5)
            if candles:
                logger.info(f"✓ {tf}: {len(candles)} candles")
            else:
                logger.warning(f"  {tf}: No data")
        except Exception as e:
            logger.error(f"  {tf}: Error - {e}")
    
    # Cleanup
    logger.info("\n[CLEANUP] Shutting down MT5 connection...")
    mt5_connector.shutdown()
    logger.info("✓ MT5 connection closed")
    
    logger.info("\n" + "=" * 60)
    logger.info("MT5 CONNECTION TEST COMPLETED")
    logger.info("=" * 60)
    
    return True


def test_market_data_integration():
    """Test integration with market_data module."""
    logger.info("\n" + "=" * 60)
    logger.info("MARKET DATA INTEGRATION TEST")
    logger.info("=" * 60)
    
    try:
        from app import market_data
        from app.config import config
        
        # Test if Forex symbols are recognized
        logger.info("\n[TEST] Checking Forex symbol recognition...")
        forex_symbols = ["EURUSD", "GBPUSD", "XAUUSD"]
        for symbol in forex_symbols:
            is_forex = market_data._is_forex_symbol(symbol)
            logger.info(f"  {symbol}: {'✓ Forex' if is_forex else '✗ Not Forex'}")
        
        # Test OHLCV fetching with routing
        logger.info("\n[TEST] Testing OHLCV routing...")
        test_symbol = "EURUSD"
        try:
            candles = market_data.fetch_ohlcv(test_symbol, "H1", limit=5)
            if candles:
                logger.info(f"✓ Fetched {len(candles)} candles for {test_symbol}")
                source = candles[0].get("source", "unknown")
                logger.info(f"  Data source: {source}")
            else:
                logger.warning(f"No data for {test_symbol}")
        except Exception as e:
            logger.error(f"Error: {e}")
        
        logger.info("\n" + "=" * 60)
        logger.info("MARKET DATA INTEGRATION TEST COMPLETED")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = test_mt5_connection()
    
    if success:
        logger.info("\nMT5 basic tests passed. Testing integration...")
        test_market_data_integration()
    else:
        logger.error("\nMT5 tests failed. Skipping integration tests.")
        sys.exit(1)
