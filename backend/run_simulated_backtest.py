"""Simulated Backtesting Script for ICT/SMC Bot.

This script generates simulated Forex data and runs backtests on the ICT/SMC strategy.
Useful for testing the system without requiring live MT5 data.
"""

import sys
import os
from datetime import datetime, timedelta, timezone
import random

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.ict_backtester import IctBacktester, BacktestPhase
from app.ict_risk_manager import IctRiskManager
from app.position_manager import PositionManager
from app.trade_journal import trade_journal


def generate_simulated_candles(
    instrument: str,
    num_candles: int = 1000,
    base_price: float = 1.1000,
    volatility: float = 0.0010,
    timeframe_minutes: int = 15
) -> list[dict]:
    """
    Generate simulated OHLCV candles for backtesting.
    
    Args:
        instrument: Forex instrument
        num_candles: Number of candles to generate
        base_price: Starting price
        volatility: Price volatility per candle
        timeframe_minutes: Timeframe in minutes
    
    Returns:
        List of OHLCV candles
    """
    candles = []
    current_price = base_price
    start_time = datetime.now(timezone.utc) - timedelta(minutes=num_candles * timeframe_minutes)
    
    for i in range(num_candles):
        # Random walk with mean reversion
        change = random.gauss(0, volatility) * base_price
        
        # Add some trend for realism
        trend = 0.0001 * base_price * (i / num_candles)  # Slight upward trend
        change += trend
        
        # Calculate OHLC
        open_price = current_price
        close_price = current_price + change
        
        # Generate high/low with some wicks
        high = max(open_price, close_price) + abs(random.gauss(0, volatility * 0.3 * base_price))
        low = min(open_price, close_price) - abs(random.gauss(0, volatility * 0.3 * base_price))
        
        # Ensure low < high
        if low >= high:
            mid = (low + high) / 2
            low = mid - volatility * base_price
            high = mid + volatility * base_price
        
        # Volume (random)
        volume = random.randint(1000, 10000)
        
        candle_time = start_time + timedelta(minutes=i * timeframe_minutes)
        
        candles.append({
            "time": candle_time,
            "open": round(open_price, 5),
            "high": round(high, 5),
            "low": round(low, 5),
            "close": round(close_price, 5),
            "volume": volume
        })
        
        current_price = close_price
    
    return candles


def run_backtest_with_simulated_data():
    """Run a complete backtest with simulated data."""
    print("=" * 60)
    print("ICT/SMC BACKTESTING WITH SIMULATED DATA")
    print("=" * 60)
    print()
    
    # Initialize instances
    print("Initializing ICT/SMC modules...")
    risk_manager = IctRiskManager(initial_capital=1000.0)  # Increased capital for simulated test
    position_manager = PositionManager(mode="fixed_tp", risk_manager=risk_manager, journal=trade_journal)
    backtester = IctBacktester(initial_capital=1000.0, risk_manager=risk_manager)
    
    # Ensure journal is passed to risk manager
    risk_manager.journal = trade_journal
    
    print("Modules initialized successfully")
    print()
    
    # Generate simulated data for each instrument
    print("Generating simulated data...")
    simulated_data = {}
    
    # EUR/USD
    eurusd_candles = generate_simulated_candles(
        "EURUSD",
        num_candles=2000,
        base_price=1.1000,
        volatility=0.0008,
        timeframe_minutes=15
    )
    simulated_data["EURUSD"] = eurusd_candles
    print(f"  EUR/USD: {len(eurusd_candles)} candles generated")
    
    # GBP/USD
    gbpusd_candles = generate_simulated_candles(
        "GBPUSD",
        num_candles=2000,
        base_price=1.3000,
        volatility=0.0010,
        timeframe_minutes=15
    )
    simulated_data["GBPUSD"] = gbpusd_candles
    print(f"  GBP/USD: {len(gbpusd_candles)} candles generated")
    
    # XAU/USD
    xauusd_candles = generate_simulated_candles(
        "XAUUSD",
        num_candles=2000,
        base_price=2000.0,
        volatility=0.02,
        timeframe_minutes=15
    )
    simulated_data["XAUUSD"] = xauusd_candles
    print(f"  XAU/USD: {len(xauusd_candles)} candles generated")
    print()
    
    # Set backtest period
    start_date = simulated_data["EURUSD"][0]["time"]
    end_date = simulated_data["EURUSD"][-1]["time"]
    print(f"Backtest period: {start_date} to {end_date}")
    print()
    
    # Run backtests
    print("Running backtests...")
    print("-" * 60)
    
    reports = {}
    for instrument in simulated_data:
        print(f"\nBacktesting {instrument}...")
        try:
            report = backtester.run_backtest(
                instrument=instrument,
                candles=simulated_data[instrument],
                start_date=start_date,
                end_date=end_date,
                phase=BacktestPhase.IN_SAMPLE
            )
            reports[instrument] = report
            
            # Print results
            stats = report.statistics
            print(f"  Total trades: {stats.total_trades}")
            print(f"  Win rate: {stats.win_rate:.2%}")
            print(f"  Total P&L: {stats.total_pnl:.2f}€ ({stats.total_pnl_pct:.2%})")
            print(f"  Max drawdown: {stats.max_drawdown_pct:.2%}")
            print(f"  Expectancy: {stats.expectancy:.2f}€")
            print(f"  Result: {report.result.value}")
            
        except Exception as e:
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
    
    print()
    print("-" * 60)
    print("BACKTEST SUMMARY")
    print("-" * 60)
    
    total_trades = 0
    total_pnl = 0.0
    valid_instruments = 0
    
    for instrument, report in reports.items():
        if report.result.value == "valid":
            valid_instruments += 1
        total_trades += report.statistics.total_trades
        total_pnl += report.statistics.total_pnl
        
        print(f"\n{instrument}:")
        print(f"  Status: {report.result.value}")
        print(f"  Trades: {report.statistics.total_trades}")
        print(f"  P&L: {report.statistics.total_pnl:.2f}€")
        print(f"  Win Rate: {report.statistics.win_rate:.2%}")
        print(f"  Drawdown: {report.statistics.max_drawdown_pct:.2%}")
    
    print()
    print("=" * 60)
    print(f"OVERALL RESULTS")
    print(f"  Total trades: {total_trades}")
    print(f"  Total P&L: {total_pnl:.2f}€")
    print(f"  Valid instruments: {valid_instruments}/{len(reports)}")
    print("=" * 60)
    
    # Export journal
    print()
    print("Exporting trade journal...")
    csv_export = trade_journal.export_to_csv(include_rejected=False)
    
    export_path = os.path.join(os.path.dirname(__file__), "backtest_journal.csv")
    with open(export_path, "w") as f:
        f.write(csv_export)
    print(f"Journal exported to: {export_path}")
    
    # Export backtest report
    json_export = trade_journal.export_to_json(include_rejected=False)
    json_path = os.path.join(os.path.dirname(__file__), "backtest_journal.json")
    with open(json_path, "w") as f:
        f.write(json_export)
    print(f"JSON journal exported to: {json_path}")
    
    print()
    print("Backtesting completed successfully!")
    
    return reports


def run_single_instrument_backtest(instrument: str = "EURUSD"):
    """Run backtest for a single instrument."""
    instrument_enum = "EURUSD" if instrument == "EURUSD" else ("GBPUSD" if instrument == "GBPUSD" else "XAUUSD")
    print(f"Running backtest for {instrument}...")
    
    # Initialize
    risk_manager = IctRiskManager(initial_capital=50.0)
    position_manager = PositionManager(mode="fixed_tp", risk_manager=risk_manager, journal=trade_journal)
    backtester = IctBacktester(initial_capital=50.0, risk_manager=risk_manager)
    
    # Generate data
    base_price = 1.1000 if instrument_enum == "EURUSD" else (1.3000 if instrument_enum == "GBPUSD" else 2000.0)
    volatility = 0.0008 if instrument_enum != "XAUUSD" else 0.02
    
    candles = generate_simulated_candles(
        instrument_enum,
        num_candles=2000,
        base_price=base_price,
        volatility=volatility,
        timeframe_minutes=15
    )
    
    # Run backtest
    start_date = candles[0]["time"]
    end_date = candles[-1]["time"]
    
    report = backtester.run_backtest(
        instrument=instrument_enum,
        candles=candles,
        start_date=start_date,
        end_date=end_date,
        phase=BacktestPhase.IN_SAMPLE
    )
    
    print(f"\nResults for {instrument}:")
    print(f"  Status: {report.result.value}")
    print(f"  Total trades: {report.statistics.total_trades}")
    print(f"  Win rate: {report.statistics.win_rate:.2%}")
    print(f"  Total P&L: {report.statistics.total_pnl:.2f}€")
    print(f"  Max drawdown: {report.statistics.max_drawdown_pct:.2%}")
    print(f"  Expectancy: {report.statistics.expectancy:.2f}€")
    
    return report


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run ICT/SMC backtest with simulated data")
    parser.add_argument(
        "--instrument",
        type=str,
        choices=["EURUSD", "GBPUSD", "XAUUSD", "ALL"],
        default="ALL",
        help="Instrument to backtest (default: ALL)"
    )
    
    args = parser.parse_args()
    
    if args.instrument == "ALL":
        run_backtest_with_simulated_data()
    else:
        run_single_instrument_backtest(args.instrument)
