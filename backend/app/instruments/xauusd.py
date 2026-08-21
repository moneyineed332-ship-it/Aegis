"""Configuration spécifique XAU/USD (Gold) pour le bot ICT/SMC.

Instrument à volatilité potentiellement plus élevée.
Filtre de risque spécifique - ne pas utiliser les mêmes paramètres que Forex.
"""

from ..ict_config import InstrumentConfig, SessionName


XAUUSD_CONFIG = InstrumentConfig(
    symbol="XAUUSD",
    display_name="XAU/USD (Gold)",
    pip_value=0.01,          # 1 pip = 0.01 sur XAUUSD
    contract_size=100,       # 1 lot = 100 oz
    typical_spread_pips=30,  # ~30 pips = $0.30
    commission_per_lot=10.0,
    
    # Volatilité & filtres (beaucoup plus large)
    min_atr_pips=100,        # ATR min 100 pips ($1)
    max_atr_pips=1000,       # ATR max 1000 pips ($10)
    volatility_reduction_pct=0.3,
    
    # Risk management (plus conservateur)
    risk_per_trade_pct=0.005,
    max_daily_drawdown_pct=0.03,   # 3% (plus tolérant pour Gold)
    max_total_drawdown_pct=0.15,   # 15%
    max_consecutive_losses=3,
    max_trades_per_session=1,      # Max 1 trade/session sur Gold
    max_simultaneous_positions=1,
    
    # Ratio Risk/Reward
    min_rr_ratio=1.5,
    target_rr_ratio=2.0,
    
    # Stop-Loss structurel (plus large pour Gold)
    sl_atr_multiplier=2.0,         # SL plus large
    sl_structure_buffer_pips=50.0,
    
    # Take-Profit structurel
    tp_first_target_r=1.0,
    partial_close_pct=0.5,
    
    # Break-even
    breakeven_trigger_r=1.0,
    breakeven_offset_pips=20.0,
    
    # Trailing structural
    trailing_atr_multiplier=2.0,
    trailing_structure_lookback=20,
    
    # Filtres
    enabled_sessions=["london", "new_york", "overlap"],
    news_filter_enabled=True,
    high_impact_news_window_min=60,  # Fenêtre plus large pour Gold
    
    # Détection ICT/SMC (seuils plus élevés)
    fvg_min_size_pips=20.0,
    ob_lookback=50,
    sweep_confirmation_candles=3,
    bos_confirmation_candles=3,
    liquidity_lookback=100,
    
    # Backtest
    backtest_slippage_pips=5.0,
    backtest_commission_per_lot=10.0,
)


# Notes spécifiques XAU/USD:
# - Volatilité bien supérieure au Forex (mouvements de $10-20/jour courants)
# - Spread plus large (30-50 pips = $0.30-$0.50)
# - Sensible aux USD (taux, inflation, emploi) + géopolitique + taux réels
# - Corrélation inverse avec USD et taux réels US
# - Sessions critiques: London open (8h), NY open (13h), Overlap (13h-17h)
# - Éviter absolument pendant NFP, CPI, FOMC, discours Fed
# - Mouvements rapides, slippage possible - prévoir marge
# - Structure de marché respectée mais avec plus de "noise"
# - Niveaux psychologiques importants: $1800, $1900, $2000, $2050, $2100
# - Attention aux gaps du week-end (ouverture dimanche soir)