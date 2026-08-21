"""Configuration spécifique GBP/USD pour le bot ICT/SMC.

Mêmes principes qu'EUR/USD mais volatilité supérieure potentielle.
Attention particulière à la volatilité et aux mouvements plus amples.
"""

from ..ict_config import InstrumentConfig, SessionName


GBPUSD_CONFIG = InstrumentConfig(
    symbol="GBPUSD",
    display_name="GBP/USD",
    pip_value=0.0001,
    contract_size=100_000,
    typical_spread_pips=1.5,
    commission_per_lot=7.0,
    
    # Volatilité & filtres (plus large qu'EUR/USD)
    min_atr_pips=40,
    max_atr_pips=300,
    volatility_reduction_pct=0.5,
    
    # Risk management
    risk_per_trade_pct=0.005,
    max_daily_drawdown_pct=0.02,
    max_total_drawdown_pct=0.10,
    max_consecutive_losses=3,
    max_trades_per_session=2,
    max_simultaneous_positions=1,
    
    # Ratio Risk/Reward
    min_rr_ratio=1.5,
    target_rr_ratio=2.0,
    
    # Stop-Loss structurel (buffer plus large pour GBP)
    sl_atr_multiplier=1.5,
    sl_structure_buffer_pips=8.0,
    
    # Take-Profit structurel
    tp_first_target_r=1.0,
    partial_close_pct=0.5,
    
    # Break-even
    breakeven_trigger_r=1.0,
    breakeven_offset_pips=3.0,
    
    # Trailing structural
    trailing_atr_multiplier=1.5,
    trailing_structure_lookback=20,
    
    # Filtres
    enabled_sessions=["london", "new_york", "overlap"],
    news_filter_enabled=True,
    high_impact_news_window_min=30,
    
    # Détection ICT/SMC
    fvg_min_size_pips=5.0,
    ob_lookback=50,
    sweep_confirmation_candles=2,
    bos_confirmation_candles=2,
    liquidity_lookback=100,
    
    # Backtest
    backtest_slippage_pips=1.0,
    backtest_commission_per_lot=7.0,
)


# Notes spécifiques GBP/USD:
# - Volatilité supérieure à EUR/USD (~20-30% plus large)
# - Spreads plus larges (1.5-2 pips typique)
# - Sensible aux nouvelles GBP (BOE, CPI, GDP, Emploi) + USD
# - Mouvements plus amples, faux cassures plus fréquentes
# - Session Londres critique (ouvre à 8h UTC)
# - Attention aux "fakeouts" sur les niveaux psychologiques (1.2000, 1.2500, etc.)
# - Corrélation partielle avec EUR/USD (éviter positions opposées simultanées)