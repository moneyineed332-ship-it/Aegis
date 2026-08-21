"""Configuration centralisée pour le bot ICT/SMC multi-instruments.

Ce module définit tous les paramètres configurables pour EUR/USD, GBP/USD, XAU/USD.
Basé sur le cahier des charges v2 - Architecture modulaire par instrument.
Intégration avec forex_indicators pour calculs spécifiques Forex.
"""

from dataclasses import dataclass, field
from typing import Literal
from . import config as aegis_config


# ============================================================
# TYPES & ENUMS
# ============================================================

Instrument = Literal["EURUSD", "GBPUSD", "XAUUSD"]
SessionName = Literal["asian", "london", "new_york", "overlap"]
Timeframe = Literal["M5", "M15", "H1", "H4", "D1"]
PositionMode = Literal["fixed_tp", "partial", "breakeven", "trailing_structural"]
Direction = Literal["buy", "sell", "neutral"]


# ============================================================
# CONFIGURATION DES SESSIONS (UTC)
# ============================================================

TRADING_SESSIONS: dict[SessionName, dict[str, str]] = {
    "asian": {"open": "00:00", "close": "09:00"},
    "london": {"open": "08:00", "close": "17:00"},
    "new_york": {"open": "13:00", "close": "22:00"},
    "overlap": {"open": "13:00", "close": "17:00"},  # London/NY overlap
}

# Sessions autorisées par instrument (configurable)
DEFAULT_ENABLED_SESSIONS: dict[Instrument, list[SessionName]] = {
    "EURUSD": ["london", "new_york", "overlap"],
    "GBPUSD": ["london", "new_york", "overlap"],
    "XAUUSD": ["london", "new_york", "overlap"],
}


# ============================================================
# TIMEFRAMES MULTI-TF
# ============================================================

# Hiérarchie timeframes pour l'analyse multi-TF (selon cahier des charges)
MTF_HIERARCHY: dict[str, list[Timeframe]] = {
    "context": ["H4", "H1"],           # Contexte global + structure (tendance principale)
    "setup": ["M15"],                   # Structure et setup (zones d'intérêt ICT/SMC)
    "confirmation": ["M5"],             # Confirmation d'entrée
}

# Timeframes requis pour chaque instrument (format standard MT5)
REQUIRED_TIMEFRAMES: list[Timeframe] = ["M5", "M15", "H1", "H4"]

# Mapping timeframes pour compatibilité avec différents formats
TIMEFRAME_MAPPING: dict[str, str] = {
    "M5": "5m",
    "M15": "15m", 
    "H1": "1h",
    "H4": "4h",
    "D1": "1d"
}


# ============================================================
# PARAMÈTRES PAR INSTRUMENT
# ============================================================

@dataclass
class InstrumentConfig:
    """Configuration complète pour un instrument."""
    symbol: Instrument
    display_name: str
    pip_value: float                    # Valeur d'un pip (ex: 0.0001 pour EURUSD)
    contract_size: float                # Taille contrat (1 lot = 100,000 unités)
    typical_spread_pips: float          # Spread typique en pips
    commission_per_lot: float           # Commission par lot (aller-retour)
    
    # Volatilité & filtres
    min_atr_pips: float                 # ATR minimum pour trader
    max_atr_pips: float                 # ATR maximum (volatilité excessive)
    volatility_reduction_pct: float     # Réduction risque si volatilité haute
    
    # Risk management
    risk_per_trade_pct: float           # Risque par trade (% capital)
    max_daily_drawdown_pct: float       # Drawdown journalier max
    max_total_drawdown_pct: float       # Drawdown total max
    max_consecutive_losses: int         # Pertes consécutives max
    max_trades_per_session: int         # Trades max par session
    max_simultaneous_positions: int     # Positions simultanées max
    
    # Ratio Risk/Reward
    min_rr_ratio: float                 # R:R minimum acceptable
    target_rr_ratio: float              # R:R cible
    
    # Stop-Loss structurel
    sl_atr_multiplier: float            # Multiplicateur ATR pour SL initial
    sl_structure_buffer_pips: float     # Buffer au-delà structure (pips)
    
    # Take-Profit structurel
    tp_first_target_r: float            # Premier TP en R (pour mode partial)
    partial_close_pct: float            # % position fermée au TP1
    
    # Break-even
    breakeven_trigger_r: float          # Déclenchement BE (en R)
    breakeven_offset_pips: float        # Offset BE au-delà entry (pips)
    
    # Trailing structural
    trailing_atr_multiplier: float      # Multiplicateur ATR pour trailing
    trailing_structure_lookback: int    # Bougies pour structure trailing
    
    # Filtres
    enabled_sessions: list[SessionName] = field(default_factory=list)
    news_filter_enabled: bool = True
    high_impact_news_window_min: int = 30
    
    # Détection ICT/SMC
    fvg_min_size_pips: float = 5.0
    ob_lookback: int = 50
    sweep_confirmation_candles: int = 2
    bos_confirmation_candles: int = 2
    liquidity_lookback: int = 100
    
    # Backtest
    backtest_slippage_pips: float = 1.0
    backtest_commission_per_lot: float = None  # None = utilise commission_per_lot


# --- Configurations par défaut ---

INSTRUMENT_CONFIGS: dict[Instrument, InstrumentConfig] = {
    "EURUSD": InstrumentConfig(
        symbol="EURUSD",
        display_name="EUR/USD",
        pip_value=0.0001,
        contract_size=100_000,
        typical_spread_pips=1.0,
        commission_per_lot=7.0,  # $7 round-trip typique
        
        min_atr_pips=30,
        max_atr_pips=200,
        volatility_reduction_pct=0.5,
        
        risk_per_trade_pct=0.005,      # 0.5%
        max_daily_drawdown_pct=0.02,   # 2%
        max_total_drawdown_pct=0.10,   # 10%
        max_consecutive_losses=3,
        max_trades_per_session=2,
        max_simultaneous_positions=1,
        
        min_rr_ratio=1.5,
        target_rr_ratio=2.0,
        
        sl_atr_multiplier=1.5,
        sl_structure_buffer_pips=5.0,
        
        tp_first_target_r=1.0,
        partial_close_pct=0.5,
        
        breakeven_trigger_r=1.0,
        breakeven_offset_pips=2.0,
        
        trailing_atr_multiplier=1.5,
        trailing_structure_lookback=20,
        
        enabled_sessions=["london", "new_york", "overlap"],
        news_filter_enabled=True,
        high_impact_news_window_min=30,
        
        fvg_min_size_pips=3.0,
        ob_lookback=50,
        sweep_confirmation_candles=2,
        bos_confirmation_candles=2,
        liquidity_lookback=100,
        
        backtest_slippage_pips=0.5,
        backtest_commission_per_lot=7.0,
    ),
    
    "GBPUSD": InstrumentConfig(
        symbol="GBPUSD",
        display_name="GBP/USD",
        pip_value=0.0001,
        contract_size=100_000,
        typical_spread_pips=1.5,
        commission_per_lot=7.0,
        
        min_atr_pips=40,
        max_atr_pips=300,
        volatility_reduction_pct=0.5,
        
        risk_per_trade_pct=0.005,
        max_daily_drawdown_pct=0.02,
        max_total_drawdown_pct=0.10,
        max_consecutive_losses=3,
        max_trades_per_session=2,
        max_simultaneous_positions=1,
        
        min_rr_ratio=1.5,
        target_rr_ratio=2.0,
        
        sl_atr_multiplier=1.5,
        sl_structure_buffer_pips=8.0,
        
        tp_first_target_r=1.0,
        partial_close_pct=0.5,
        
        breakeven_trigger_r=1.0,
        breakeven_offset_pips=3.0,
        
        trailing_atr_multiplier=1.5,
        trailing_structure_lookback=20,
        
        enabled_sessions=["london", "new_york", "overlap"],
        news_filter_enabled=True,
        high_impact_news_window_min=30,
        
        fvg_min_size_pips=5.0,
        ob_lookback=50,
        sweep_confirmation_candles=2,
        bos_confirmation_candles=2,
        liquidity_lookback=100,
        
        backtest_slippage_pips=1.0,
        backtest_commission_per_lot=7.0,
    ),
    
    "XAUUSD": InstrumentConfig(
        symbol="XAUUSD",
        display_name="XAU/USD (Gold)",
        pip_value=0.01,          # 1 pip = 0.01 sur XAUUSD
        contract_size=100,       # 1 lot = 100 oz
        typical_spread_pips=30,  # ~30 pips = $0.30
        commission_per_lot=10.0,
        
        min_atr_pips=100,        # ATR min 100 pips ($1)
        max_atr_pips=1000,       # ATR max 1000 pips ($10)
        volatility_reduction_pct=0.3,
        
        risk_per_trade_pct=0.005,
        max_daily_drawdown_pct=0.03,   # 3% (plus tolérant pour Gold)
        max_total_drawdown_pct=0.15,   # 15%
        max_consecutive_losses=3,
        max_trades_per_session=1,      # Max 1 trade/session sur Gold
        max_simultaneous_positions=1,
        
        min_rr_ratio=1.5,
        target_rr_ratio=2.0,
        
        sl_atr_multiplier=2.0,         # SL plus large pour Gold
        sl_structure_buffer_pips=50.0,
        
        tp_first_target_r=1.0,
        partial_close_pct=0.5,
        
        breakeven_trigger_r=1.0,
        breakeven_offset_pips=20.0,
        
        trailing_atr_multiplier=2.0,
        trailing_structure_lookback=20,
        
        enabled_sessions=["london", "new_york", "overlap"],
        news_filter_enabled=True,
        high_impact_news_window_min=60,  # Fenêtre plus large pour Gold
        
        fvg_min_size_pips=20.0,
        ob_lookback=50,
        sweep_confirmation_candles=3,
        bos_confirmation_candles=3,
        liquidity_lookback=100,
        
        backtest_slippage_pips=5.0,
        backtest_commission_per_lot=10.0,
    ),
}


# ============================================================
# CONFIGURATION GLOBALE DU BOT
# ============================================================

@dataclass
class ICTBotConfig:
    """Configuration globale du bot ICT/SMC."""
    # Capital de référence
    initial_capital: float = 50.0
    
    # Instruments actifs - Priorité: EUR/USD principal, puis GBP/USD, XAU/USD
    active_instruments: list[Instrument] = field(default_factory=lambda: ["EURUSD", "GBPUSD", "XAUUSD"])
    
    # Instrument prioritaire pour les tests (selon cahier des charges)
    primary_instrument: Instrument = "EURUSD"
    
    # Mode position (testable séparément)
    position_mode: PositionMode = "fixed_tp"
    
    # Backtest
    backtest_start_date: str = "2023-01-01"
    backtest_end_date: str = "2024-12-31"
    backtest_timeframes: list[Timeframe] = field(default_factory=lambda: ["M5", "M15", "H1", "H4"])
    
    # Data source
    data_source: Literal["mt5", "csv", "api"] = "mt5"
    data_path: str = "./data/historical"
    
    # Logging
    log_level: str = "INFO"
    log_trades: bool = True
    log_signals: bool = True
    log_rejections: bool = True
    
    # Risk Manager centralisé (ne peut pas être contourné)
    risk_manager_enabled: bool = True
    strict_risk_enforcement: bool = True
    
    # News filter (global)
    global_news_filter: bool = True
    news_api_provider: Literal["forexfactory", "investing", "custom"] = "forexfactory"
    news_cache_hours: int = 24


# Instance globale par défaut
DEFAULT_BOT_CONFIG = ICTBotConfig()


# ============================================================
# HELPERS
# ============================================================

def get_instrument_config(symbol: Instrument) -> InstrumentConfig:
    """Récupère la configuration pour un instrument."""
    return INSTRUMENT_CONFIGS[symbol]


def get_pip_value(symbol: Instrument) -> float:
    """Valeur d'un pip pour l'instrument."""
    return INSTRUMENT_CONFIGS[symbol].pip_value


def get_contract_size(symbol: Instrument) -> float:
    """Taille du contrat pour l'instrument."""
    return INSTRUMENT_CONFIGS[symbol].contract_size


def pips_to_price(symbol: Instrument, pips: float) -> float:
    """Convertit des pips en prix pour l'instrument."""
    return pips * INSTRUMENT_CONFIGS[symbol].pip_value


def price_to_pips(symbol: Instrument, price_diff: float) -> float:
    """Convertit une différence de prix en pips."""
    return price_diff / INSTRUMENT_CONFIGS[symbol].pip_value


def calculate_position_size(
    symbol: Instrument,
    account_equity: float,
    entry_price: float,
    sl_price: float,
    risk_pct: float | None = None
) -> float:
    """
    Calcule la taille de position basée sur le risque % et la distance SL.
    Utilise forex_indicators pour calculs précis Forex.
    
    Returns:
        Taille en lots (arrondi à 0.01)
    """
    cfg = get_instrument_config(symbol)
    try:
        from .forex_indicators import calculate_forex_position_size
        result = calculate_forex_position_size(symbol, account_equity, risk_pct or cfg.risk_per_trade_pct, entry_price, sl_price)
        return result["lots"]
    except ImportError:
        # Fallback to original calculation if forex_indicators not available
        risk = risk_pct or cfg.risk_per_trade_pct
        
        risk_amount = account_equity * risk
        sl_distance_pips = abs(entry_price - sl_price) / cfg.pip_value
        
        if sl_distance_pips <= 0:
            return 0.0
        
        # Valeur d'un pip pour 1 lot
        pip_value_per_lot = cfg.contract_size * cfg.pip_value
        
        # Lots = risque / (distance_SL_pips * valeur_pip_par_lot)
        lots = risk_amount / (sl_distance_pips * pip_value_per_lot)
        
        # Arrondi à 0.01 lot (standard MT5)
        return round(lots, 2)


def calculate_rr_ratio(
    symbol: Instrument,
    entry: float,
    sl: float,
    tp: float
) -> float:
    """Calcule le ratio Risk/Reward avec calculs Forex précis."""
    try:
        from .forex_indicators import calculate_rr_ratio_forex
        result = calculate_rr_ratio_forex(symbol, entry, sl, tp)
        return result["rr_ratio"]
    except ImportError:
        # Fallback to original calculation
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        return reward / risk if risk > 0 else 0.0


def validate_rr_ratio(symbol: Instrument, rr: float) -> bool:
    """Valide si le R:R respecte le minimum configuré."""
    cfg = get_instrument_config(symbol)
    return rr >= cfg.min_rr_ratio