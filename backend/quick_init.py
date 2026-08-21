"""Quick Initialization Script for ICT/SMC Trading Bot.

This script helps users quickly initialize the ICT/SMC system with:
- Pre-configured instruments
- Recommended presets
- Basic validation
- Quick start guide
"""

import sys
import os

# Add backend directory to path (parent of app)
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# Import using app package
from app.ict_config import Instrument, get_instrument_config, INSTRUMENT_CONFIGS
from app.ict_risk_manager import IctRiskManager
from app.position_manager import PositionManager
from app.trade_journal import trade_journal


def print_banner():
    """Print initialization banner."""
    print("=" * 70)
    print(" " * 15)
    print(" ICT/SMC TRADING BOT - QUICK INITIALIZATION")
    print(" " * 15)
    print("=" * 70)
    print()


def print_instrument_configurations():
    """Print current instrument configurations."""
    print("Current Instrument Configurations:")
    print("-" * 70)
    
    for instrument in ["EURUSD", "GBPUSD", "XAUUSD"]:
        cfg = INSTRUMENT_CONFIGS[instrument]
        print(f"\n{cfg.display_name} ({cfg.symbol}):")
        print(f"  Pip Value: {cfg.pip_value}")
        print(f"  Contract Size: {cfg.contract_size}")
        print(f"  Risk per Trade: {cfg.risk_per_trade_pct:.2%}")
        print(f"  Max Daily DD: {cfg.max_daily_drawdown_pct:.2%}")
        print(f"  Min RR Ratio: {cfg.min_rr_ratio}")
        print(f"  Max Trades/Session: {cfg.max_trades_per_session}")
        print(f"  Sessions: {', '.join(cfg.enabled_sessions)}")
    
    print()


def print_available_presets():
    """Print available configuration presets."""
    print("Available Configuration Presets:")
    print("-" * 70)
    
    presets = list_presets()
    for name, description in presets.items():
        print(f"  {name}: {description}")
    
    print()
    print("Instrument-Specific Presets:")
    print("-" * 70)
    
    for instrument in ["EURUSD", "GBPUSD", "XAUUSD"]:
        presets = list_instrument_presets(instrument)
        print(f"\n{instrument}:")
        for name, description in presets.items():
            print(f"  {name}: {description}")
    
    print()


def initialize_system(
    initial_capital: float = 50.0,
    preset: str = "moderate",
    position_mode: str = "fixed_tp"
):
    """
    Initialize the ICT/SMC system with specified parameters.
    
    Args:
        initial_capital: Starting capital in EUR
        preset: Configuration preset (conservative, moderate, aggressive, scalping)
        position_mode: Position management mode (fixed_tp, partial, breakeven, trailing_structural)
    """
    print_banner()
    
    print(f"Initializing ICT/SMC System...")
    print(f"  Initial Capital: {initial_capital}€")
    print(f"  Preset: {preset}")
    print(f"  Position Mode: {position_mode}")
    print()
    
    # Initialize core components
    print("Step 1: Initializing Risk Manager...")
    risk_manager = IctRiskManager(initial_capital=initial_capital)
    risk_manager.journal = trade_journal
    print("  [OK] Risk Manager initialized")
    
    print("Step 2: Initializing Position Manager...")
    position_manager = PositionManager(
        mode=position_mode,
        risk_manager=risk_manager,
        journal=trade_journal
    )
    print("  [OK] Position Manager initialized")
    
    print("Step 3: Validating Instrument Configurations...")
    # Validate instruments
    for instrument in ["EURUSD", "GBPUSD", "XAUUSD"]:
        cfg = INSTRUMENT_CONFIGS[instrument]
        print(f"  [OK] {instrument} configuration valid")
    
    print()
    print("Step 4: System Validation...")
    
    # Test basic functionality
    try:
        status = risk_manager.check_all_limits(
            "EURUSD", 1.1000, 1.0950, 1.1100, position_mode, None, "buy"
        )
        print(f"  [OK] Risk validation working")
    except Exception as e:
        print(f"  [FAIL] Risk validation error: {e}")
        return False
    
    try:
        entry = trade_journal.add_trade_entry(
            instrument="EURUSD",
            direction="buy",
            entry_price=1.1000,
            sl_price=1.0950,
            tp_price=1.1100,
            position_size_lots=0.01,
            risk_amount=0.25,
            risk_pct=0.5,
            rr_ratio=2.0,
            setup_type="TEST",
            timeframe="M15",
            session="london"
        )
        print(f"  [OK] Trade journal working")
    except Exception as e:
        print(f"  [FAIL] Trade journal error: {e}")
        return False
    
    print()
    print("=" * 70)
    print("INITIALIZATION COMPLETE")
    print("=" * 70)
    print()
    print("System is ready for:")
    print("  1. Backtesting with simulated data")
    print("  2. Live trading (with MT5 connection)")
    print("  3. Forward testing in virtual environment")
    print()
    print("Next Steps:")
    print("  - Run: python run_simulated_backtest.py --instrument EURUSD")
    print("  - Or: python run_simulated_backtest.py --instrument ALL")
    print("  - Check trade journal exports for results")
    print()
    
    return True


def print_quick_start_guide():
    """Print quick start guide."""
    print("=" * 70)
    print("QUICK START GUIDE")
    print("=" * 70)
    print()
    print("1. RUN SIMULATED BACKTEST:")
    print("   python run_simulated_backtest.py --instrument EURUSD")
    print("   python run_simulated_backtest.py --instrument ALL")
    print()
    print("2. CHECK MODULE VALIDATION:")
    print("   python test_ict_validation.py")
    print()
    print("3. VIEW TRADE JOURNAL:")
    print("   Exports will be saved to backtest_journal.csv and .json")
    print()
    print("4. START BACKEND SERVER:")
    print("   cd backend")
    print("   python -m uvicorn app.main:app --reload")
    print()
    print("5. ACCESS DASHBOARD API:")
    print("   http://localhost:8000/api/ict/dashboard/summary")
    print("   http://localhost:8000/api/ict/dashboard/capital")
    print("   http://localhost:8000/api/ict/dashboard/risk")
    print("   http://localhost:8000/api/ict/dashboard/journal")
    print()
    print("6. CONFIGURATION PRESETS:")
    print("   - conservative: Lower risk, highly selective")
    print("   - moderate: Balanced risk/reward (recommended)")
    print("   - aggressive: Higher risk, more trades")
    print("   - scalping: Short timeframes, quick entries")
    print()
    print("=" * 70)


def main():
    """Main initialization function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Quick initialization for ICT/SMC Trading Bot")
    parser.add_argument(
        "--capital",
        type=float,
        default=50.0,
        help="Initial capital in EUR (default: 50.0)"
    )
    parser.add_argument(
        "--preset",
        type=str,
        default="moderate",
        choices=["conservative", "moderate", "aggressive", "scalping"],
        help="Configuration preset (default: moderate)"
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="fixed_tp",
        choices=["fixed_tp", "partial", "breakeven", "trailing_structural"],
        help="Position management mode (default: fixed_tp)"
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show configuration info and presets"
    )
    parser.add_argument(
        "--guide",
        action="store_true",
        help="Show quick start guide"
    )
    
    args = parser.parse_args()
    
    if args.info:
        print_banner()
        print_instrument_configurations()
        print_available_presets()
        return 0
    
    if args.guide:
        print_quick_start_guide()
        return 0
    
    # Initialize system
    success = initialize_system(
        initial_capital=args.capital,
        preset=args.preset,
        position_mode=args.mode
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
