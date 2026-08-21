"""Configuration spécifique EUR/USD pour le bot ICT/SMC.

Instrument prioritaire pour les tests.
Focus: liquidité, BOS, CHoCH, Order Blocks, FVG, retracements zones institutionnelles.
"""

from ..ict_config import InstrumentConfig, SessionName


EURUSD_CONFIG = InstrumentConfig(
    symbol="EURUSD",
    display_name="EUR/USD",
    pip_value=0.0001,
    contract_size=100_000,
    typical_spread_pips=1.0,
    commission_per_lot=7.0,  # $7 round-trip typique
    
    # Volatilité & filtres
    min_atr_pips=30,
    max_atr_pips=200,
    volatility_reduction_pct=0.5,
    
    # Risk management
    risk_per_trade_pct=0.005,      # 0.5%
    max_daily_drawdown_pct=0.02,   # 2%
    max_total_drawdown_pct=0.10,   # 10%
    max_consecutive_losses=3,
    max_trades_per_session=2,
    max_simultaneous_positions=1,
    
    # Ratio Risk/Reward
    min_rr_ratio=1.5,
    target_rr_ratio=2.0,
    
    # Stop-Loss structurel
    sl_atr_multiplier=1.5,
    sl_structure_buffer_pips=5.0,
    
    # Take-Profit structurel
    tp_first_target_r=1.0,
    partial_close_pct=0.5,
    
    # Break-even
    breakeven_trigger_r=1.0,
    breakeven_offset_pips=2.0,
    
    # Trailing structural
    trailing_atr_multiplier=1.5,
    trailing_structure_lookback=20,
    
    # Filtres
    enabled_sessions=["london", "new_york", "overlap"],
    news_filter_enabled=True,
    high_impact_news_window_min=30,
    
    # Détection ICT/SMC
    fvg_min_size_pips=3.0,
    ob_lookback=50,
    sweep_confirmation_candles=2,
    bos_confirmation_candles=2,
    liquidity_lookback=100,
    
    # Backtest
    backtest_slippage_pips=0.5,
    backtest_commission_per_lot=7.0,
)


# Notes spécifiques EUR/USD:
# - Instrument le plus liquide, spreads les plus serrés
# - Sensible aux nouvelles EUR (ECB, CPI, PMI) et USD (NFP, CPI, FOMC)
# - Meilleure performance pendant overlap London/NY (13h-17h UTC)
# - Structure de marché claire, respect des niveaux techniques
# - Éviter session asiatique (faible volatilité, faux signaux)