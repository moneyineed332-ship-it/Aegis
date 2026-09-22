"""Risk Manager centralisé pour le bot ICT/SMC.

Module prioritaire - aucune stratégie ne peut contourner ce gestionnaire.
Vérifie toutes les limites avant d'autoriser un trade.
"""

import logging
from datetime import datetime, date, timezone
from dataclasses import dataclass, field
from typing import Literal
from threading import RLock

from .ict_config import (
    Instrument,
    PositionMode,
    get_instrument_config,
    calculate_position_size,
    calculate_rr_ratio,
    validate_rr_ratio,
)
from .session_filter import is_trading_allowed, get_session_status
from .news_filter import is_news_blocking, get_news_status

# Optional import to avoid circular dependency
try:
    from .trade_journal import (
        TradeJournal, TradeJournalEntry, ConfluenceFactor, ConfluenceType,
        TradeRejectionReason, trade_journal
    )
    TRADE_JOURNAL_AVAILABLE = True
except ImportError:
    TRADE_JOURNAL_AVAILABLE = False
    # Create stub for import compatibility
    trade_journal = None
    
    # Fallback TradeRejectionReason enum
    from enum import Enum
    class TradeRejectionReason(Enum):
        RR_INSUFFICIENT = "rr_insufficient"
        DRAWDOWN_LIMIT = "drawdown_limit"
        CONSECUTIVE_LOSSES = "consecutive_losses"
        SESSION_FILTER = "session_filter"
        NEWS_FILTER = "news_filter"
        VOLATILITY_FILTER = "volatility_filter"
        RISK_LIMIT = "risk_limit"
        MARTINGALE_BLOCKED = "martingale_blocked"
        POSITION_SIZE_INVALID = "position_size_invalid"
        SL_PLACEMENT_INVALID = "sl_placement_invalid"
        NO_CONFLUENCE = "no_confluence"
        STRUCTURE_NOT_CONFIRMED = "structure_not_confirmed"
        LIQUIDITY_NOT_SWEPT = "liquidity_not_swept"

logger = logging.getLogger(__name__)


# ============================================================
# TYPES
# ============================================================

TradeResult = Literal["win", "loss", "breakeven", "open"]


@dataclass
class TradeRecord:
    """Enregistrement d'un trade pour le journal."""
    id: str
    instrument: Instrument
    direction: Literal["buy", "sell"]
    entry_price: float
    sl_price: float
    tp_price: float
    position_size: float       # lots
    risk_amount: float         # montant risqué
    risk_pct: float            # % capital
    rr_ratio: float
    entry_time: datetime
    exit_time: datetime | None = None
    exit_price: float | None = None
    result: TradeResult = "open"
    pnl: float = 0.0
    pnl_pct: float = 0.0
    r_multiple: float = 0.0
    session: str = ""
    setup_type: str = ""
    mode: PositionMode = "fixed_tp"
    notes: str = ""


@dataclass
class RiskLimits:
    """Limites de risque pour un instrument."""
    max_risk_per_trade_pct: float
    max_daily_drawdown_pct: float
    max_total_drawdown_pct: float
    max_consecutive_losses: int
    max_trades_per_session: int
    max_simultaneous_positions: int
    min_rr_ratio: float


@dataclass
class RiskStatus:
    """Status actuel du risk manager pour un instrument."""
    instrument: Instrument
    can_trade: bool
    blocking_reasons: list[str]
    
    # Métriques actuelles
    current_equity: float
    initial_capital: float
    daily_pnl: float
    daily_pnl_pct: float
    total_drawdown_pct: float
    consecutive_losses: int
    trades_today: int
    open_positions: int
    
    # Limites
    limits: RiskLimits
    
    # Filtres
    session_allowed: bool
    session_reason: str
    news_blocked: bool
    news_reason: str
    volatility_ok: bool
    volatility_reason: str
    volatility_reduction: float = 1.0  # 1.0 = no reduction, 0.5 = 50% reduced


# ============================================================
# RISK MANAGER
# ============================================================

class IctRiskManager:
    """
    Risk Manager centralisé pour le bot ICT/SMC.
    
    RÈGLE FONDAMENTALE (Cahier des charges §7): Aucune stratégie ne peut contourner ce gestionnaire.
    Avant toute position, le Risk Manager vérifie TOUTES les limites.
    
    INTERDICTIONS STRICTES (Cahier des charges §7):
    - MARTINGALE: Jamais augmenter automatiquement le risque après une perte
    - REVENGE TRADING: Jamais multiplier les positions pour récupérer une perte
    - AUGMENTATION AUTOMATIQUE: Jamais augmenter automatiquement le lot après série de pertes
    
    Si une condition est négative → TRADE REFUSÉ.
    """
    
    def __init__(
        self,
        initial_capital: float = 50.0,
        custom_limits: dict[Instrument, RiskLimits] | None = None,
        journal: TradeJournal | None = None,
    ):
        self.initial_capital = initial_capital
        self.current_equity = initial_capital
        self._lock = RLock()
        self.journal = journal if TRADE_JOURNAL_AVAILABLE else None  # Trade journal integration
        
        # État quotidien (reset à minuit UTC)
        self._daily_pnl = 0.0
        self._trades_today = 0
        self._consecutive_losses = 0
        self._last_reset_date = date.today()
        self._session_start_equity = initial_capital
        
        # Historique trades
        self._trade_history: list[TradeRecord] = []
        self._open_trades: dict[str, TradeRecord] = {}
        
        # Limites par instrument (depuis config ou custom)
        self._limits: dict[Instrument, RiskLimits] = custom_limits or {}
        self._init_default_limits()
        
        # Peak equity pour drawdown total
        self._peak_equity = initial_capital
        
        # ANTI-MARTINGALE & ANTI-REVENGE TRACKING
        self._last_trade_was_loss = False
        self._loss_increase_detected = False
        self._position_size_locked = False
        self._locked_position_size: dict[Instrument, float] = {}
        self._revenge_trading_blocked = False
        self._last_loss_amount = 0.0
        self._current_position_size_multiplier = 1.0
    
    def _init_default_limits(self) -> None:
        """Initialise les limites depuis la config par instrument."""
        for symbol in ["EURUSD", "GBPUSD", "XAUUSD"]:
            if symbol not in self._limits:
                cfg = get_instrument_config(symbol)
                
                # LIMITES SPÉCIFIQUES XAU/USD (Cahier des charges §7)
                # XAU/USD a des paramètres plus conservateurs
                if symbol == "XAUUSD":
                    max_risk_pct = cfg.risk_per_trade_pct * 0.8  # 20% moins de risque
                    max_daily_dd = cfg.max_daily_drawdown_pct * 0.8  # DD plus strict
                    max_trades = cfg.max_trades_per_session - 1  # Moins de trades
                    max_simultaneous = 1  # MAX 1 position simultanée pour XAU/USD
                else:
                    max_risk_pct = cfg.risk_per_trade_pct
                    max_daily_dd = cfg.max_daily_drawdown_pct
                    max_trades = cfg.max_trades_per_session
                    max_simultaneous = cfg.max_simultaneous_positions
                
                self._limits[symbol] = RiskLimits(
                    max_risk_per_trade_pct=max_risk_pct,
                    max_daily_drawdown_pct=max_daily_dd,
                    max_total_drawdown_pct=cfg.max_total_drawdown_pct,
                    max_consecutive_losses=cfg.max_consecutive_losses,
                    max_trades_per_session=max_trades,
                    max_simultaneous_positions=max_simultaneous,
                    min_rr_ratio=cfg.min_rr_ratio,
                )
    
    # --------------------------------------------------------
    # RESET QUOTIDIEN AUTOMATIQUE
    # --------------------------------------------------------
    
    def _check_daily_reset(self) -> None:
        """Reset automatique à minuit UTC."""
        today = date.today()
        if today != self._last_reset_date:
            logger.info("Daily reset: new trading day")
            self._daily_pnl = 0.0
            self._trades_today = 0
            self._consecutive_losses = 0
            self._last_reset_date = today
            self._session_start_equity = self.current_equity
    
    # --------------------------------------------------------
    # VÉRIFICATIONS PRINCIPALES (Cahier des charges §18)
    # --------------------------------------------------------
    
    def check_all_limits(
        self,
        instrument: Instrument,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        position_mode: PositionMode = "fixed_tp",
        current_atr_pips: float | None = None,
        direction: Literal["buy", "sell"] = "buy",  # Add direction parameter
    ) -> RiskStatus:
        """
        Vérification COMPLÈTE avant d'autoriser un trade.
        
        Cahier des charges §18 - Le Risk Manager vérifie :
        1. limite de risque
        2. drawdown
        3. nombre de trades
        4. pertes consécutives
        5. taille théorique
        6. distance du SL
        7. ratio Risk/Reward
        8. filtre économique
        9. filtre de volatilité
        
        Returns:
            RiskStatus avec can_trade et raisons de blocage
        """
        with self._lock:
            self._check_daily_reset()
            
            cfg = get_instrument_config(instrument)
            limits = self._limits[instrument]
            blocking_reasons = []
            
            # 1. LIMITE DE RISQUE PAR TRADE
            risk_amount = self.current_equity * limits.max_risk_per_trade_pct
            sl_distance_pips = abs(entry_price - sl_price) / cfg.pip_value
            pip_value_per_lot = cfg.contract_size * cfg.pip_value
            theoretical_lots = risk_amount / (sl_distance_pips * pip_value_per_lot) if sl_distance_pips > 0 else 0
            
            if theoretical_lots < 0.01:
                blocking_reasons.append(f"Position size trop petite ({theoretical_lots:.4f} lots < 0.01)")
            
            # 2. DRAWDOWN JOURNALIER (losses only — gains must not block)
            daily_dd_pct = max(0.0, -self._daily_pnl) / self._session_start_equity if self._session_start_equity > 0 else 0
            if daily_dd_pct >= limits.max_daily_drawdown_pct:
                blocking_reasons.append(f"Daily drawdown limit: {daily_dd_pct:.1%} >= {limits.max_daily_drawdown_pct:.1%}")
            
            # 3. DRAWDOWN TOTAL
            total_dd_pct = (self._peak_equity - self.current_equity) / self._peak_equity if self._peak_equity > 0 else 0
            if total_dd_pct >= limits.max_total_drawdown_pct:
                blocking_reasons.append(f"Total drawdown limit: {total_dd_pct:.1%} >= {limits.max_total_drawdown_pct:.1%}")
            
            # 4. NOMBRE DE TRADES PAR SESSION
            if self._trades_today >= limits.max_trades_per_session:
                blocking_reasons.append(f"Max trades/session reached: {self._trades_today}/{limits.max_trades_per_session}")
            
            # 5. PERTES CONSÉCUTIVES
            if self._consecutive_losses >= limits.max_consecutive_losses:
                blocking_reasons.append(f"Max consecutive losses: {self._consecutive_losses}/{limits.max_consecutive_losses}")
            
            # 6. POSITIONS SIMULTANÉES
            open_count = len([t for t in self._open_trades.values() if t.instrument == instrument])
            if open_count >= limits.max_simultaneous_positions:
                blocking_reasons.append(f"Max simultaneous positions: {open_count}/{limits.max_simultaneous_positions}")
            
            # 7. DISTANCE SL (vérifier que SL n'est pas trop large)
            max_sl_pips = cfg.max_atr_pips * cfg.sl_atr_multiplier * 2  # Marge de sécurité
            if sl_distance_pips > max_sl_pips:
                blocking_reasons.append(f"SL trop large: {sl_distance_pips:.0f} pips > max {max_sl_pips:.0f}")
            
            # 8. RATIO RISK/REWARD
            rr = calculate_rr_ratio(instrument, entry_price, sl_price, tp_price)
            if not validate_rr_ratio(instrument, rr):
                blocking_reasons.append(f"R:R insuffisant: {rr:.2f} < {limits.min_rr_ratio:.2f}")
            
            # 9. FILTRE SESSION HORAIRE
            session_allowed = is_trading_allowed(instrument)
            session_status = get_session_status(instrument)
            session_reason = "OK" if session_allowed else f"Hors session (prochaine dans {session_status.get('time_until_next_session_seconds', 0)/60:.0f}min)"
            if not session_allowed:
                blocking_reasons.append(session_reason)
            
            # 10. FILTRE NEWS ÉCONOMIQUE
            news_blocked = is_news_blocking(instrument)
            news_status = get_news_status(instrument)
            news_reason = "OK" if not news_blocked else news_status.get("block_reason", "News bloquante")
            if news_blocked:
                blocking_reasons.append(news_reason)
            
            # 11. FILTRE VOLATILITÉ (Cahier des charges §11)
            # XAU/USD a des seuils spécifiques et réduit le risque si volatilité haute
            volatility_ok = True
            volatility_reason = "OK"
            volatility_reduction = 1.0  # No reduction by default
            if current_atr_pips is not None:
                if current_atr_pips < cfg.min_atr_pips:
                    volatility_ok = False
                    volatility_reason = f"Volatilité trop faible: ATR {current_atr_pips:.0f} < min {cfg.min_atr_pips:.0f} pips"
                    blocking_reasons.append(volatility_reason)
                elif current_atr_pips > cfg.max_atr_pips:
                    volatility_ok = False
                    volatility_reason = f"Volatilité excessive: ATR {current_atr_pips:.0f} > max {cfg.max_atr_pips:.0f} pips"
                    blocking_reasons.append(volatility_reason)
                elif current_atr_pips > cfg.min_atr_pips * 2:
                    # High volatility but within limits → reduce risk (§11)
                    volatility_reduction = cfg.volatility_reduction_pct
                    volatility_reason = (
                        f"Volatilité élevée: ATR {current_atr_pips:.0f} pips — "
                        f"risque réduit de {(1 - volatility_reduction) * 100:.0f}%"
                    )
            
            # 12. ANTI-MARTINGALE & ANTI-REVENGE TRADING (Cahier des charges §7)
            if self._revenge_trading_blocked:
                blocking_reasons.append("Revenge trading bloqué après perte significative")
            
            if self._position_size_locked and instrument in self._locked_position_size:
                blocking_reasons.append(f"Position size verrouillée à {self._locked_position_size[instrument]:.2f} lots après perte")
            
            # Vérifier tentative d'augmentation de taille après perte
            if self._last_trade_was_loss and not self._position_size_locked:
                # Détecter si le user essaie d'augmenter la taille
                current_size_multiplier = self._current_position_size_multiplier
                if current_size_multiplier > 1.0:
                    blocking_reasons.append(f"Tentative d'augmentation de taille ({current_size_multiplier:.1f}x) après perte détectée")
            
            can_trade = len(blocking_reasons) == 0
            
            if not can_trade:
                logger.warning("TRADE REFUSÉ %s: %s", instrument, "; ".join(blocking_reasons))
                
                # Auto-log rejected trade to journal (Cahier des charges §20)
                if self.journal and TRADE_JOURNAL_AVAILABLE:
                    rejection_reason = self._map_blocking_reason_to_enum(blocking_reasons[0])
                    self.journal.add_rejected_trade(
                        instrument=instrument,
                        direction=direction,
                        entry_price=entry_price,
                        sl_price=sl_price,
                        tp_price=tp_price,
                        rejection_reason=rejection_reason,
                        rejection_details="; ".join(blocking_reasons),
                        setup_type="ICT_SMC",
                        timeframe="M15"
                    )
            
            return RiskStatus(
                instrument=instrument,
                can_trade=can_trade,
                blocking_reasons=blocking_reasons,
                current_equity=self.current_equity,
                initial_capital=self.initial_capital,
                daily_pnl=self._daily_pnl,
                daily_pnl_pct=daily_dd_pct,
                total_drawdown_pct=total_dd_pct,
                consecutive_losses=self._consecutive_losses,
                trades_today=self._trades_today,
                open_positions=open_count,
                limits=limits,
                session_allowed=session_allowed,
                session_reason=session_reason,
                news_blocked=news_blocked,
                news_reason=news_reason,
                volatility_ok=volatility_ok,
                volatility_reason=volatility_reason,
                volatility_reduction=volatility_reduction,
            )
    
    # --------------------------------------------------------
    # CALCUL POSITION SIZE (après validation)
    # --------------------------------------------------------
    
    def calculate_position_size(
        self,
        instrument: Instrument,
        entry_price: float,
        sl_price: float,
        risk_pct: float | None = None,
        volatility_reduction: float = 1.0,
    ) -> float:
        """
        Calcule la taille de position après validation des limites.
        Utilise le risque configuré pour l'instrument.
        Applique la réduction de volatilité si nécessaire (§11).
        """
        cfg = get_instrument_config(instrument)
        risk = (risk_pct or cfg.risk_per_trade_pct) * volatility_reduction
        return calculate_position_size(instrument, self.current_equity, entry_price, sl_price, risk)
    
    # --------------------------------------------------------
    # ENREGISTREMENT TRADES
    # --------------------------------------------------------
    
    def register_trade_entry(
        self,
        trade_id: str,
        instrument: Instrument,
        direction: Literal["buy", "sell"],
        entry_price: float,
        sl_price: float,
        tp_price: float,
        position_size: float,
        risk_amount: float,
        risk_pct: float,
        rr_ratio: float,
        session: str,
        setup_type: str,
        mode: PositionMode = "fixed_tp",
    ) -> TradeRecord:
        """Enregistre l'ouverture d'un trade."""
        with self._lock:
            trade = TradeRecord(
                id=trade_id,
                instrument=instrument,
                direction=direction,
                entry_price=entry_price,
                sl_price=sl_price,
                tp_price=tp_price,
                position_size=position_size,
                risk_amount=risk_amount,
                risk_pct=risk_pct,
                rr_ratio=rr_ratio,
                entry_time=datetime.now(timezone.utc),
                session=session,
                setup_type=setup_type,
                mode=mode,
            )
            self._open_trades[trade_id] = trade
            self._trade_history.append(trade)
            self._trades_today += 1
            logger.info("Trade opened: %s %s @ %.5f (SL: %.5f, TP: %.5f, Size: %.2f lots)",
                       instrument, direction, entry_price, sl_price, tp_price, position_size)
            return trade
    
    def register_trade_exit(
        self,
        trade_id: str,
        exit_price: float,
        exit_time: datetime | None = None,
    ) -> TradeRecord | None:
        """Enregistre la fermeture d'un trade et met à jour les métriques."""
        with self._lock:
            trade = self._open_trades.pop(trade_id, None)
            if not trade:
                logger.warning("Trade not found for exit: %s", trade_id)
                return None
            
            exit_time = exit_time or datetime.now(timezone.utc)
            
            # Calcul PnL
            if trade.direction == "buy":
                pnl_pips = (exit_price - trade.entry_price) / get_instrument_config(trade.instrument).pip_value
            else:
                pnl_pips = (trade.entry_price - exit_price) / get_instrument_config(trade.instrument).pip_value
            
            pip_value = get_instrument_config(trade.instrument).contract_size * get_instrument_config(trade.instrument).pip_value
            pnl = pnl_pips * pip_value * trade.position_size
            pnl_pct = pnl / self.current_equity if self.current_equity > 0 else 0
            r_multiple = pnl / trade.risk_amount if trade.risk_amount > 0 else 0
            
            # Déterminer résultat
            if pnl > 0:
                result: TradeResult = "win"
                self._consecutive_losses = 0
                self._last_trade_was_loss = False
                self._current_position_size_multiplier = 1.0  # Reset multiplier after win
            elif pnl < 0:
                result = "loss"
                self._consecutive_losses += 1
                self._last_trade_was_loss = True
                self._last_loss_amount = abs(pnl)
                
                # DÉTECTION REVENGE TRADING (Cahier des charges §7)
                # Si perte significative ou série de pertes, bloquer temporarily
                if self._consecutive_losses >= 2 or abs(pnl) > (self.current_equity * 0.05):  # 5% de perte
                    self._revenge_trading_blocked = True
                    logger.warning("Revenge trading détecté - position size verrouillée")
                
                # VERROUILLAGE TAILLE POSITION (Cahier des charges §7)
                # Ne pas augmenter automatiquement le lot après perte
                if self._consecutive_losses >= 3:
                    self._position_size_locked = True
                    self._locked_position_size[trade.instrument] = trade.position_size
                    self._current_position_size_multiplier = 0.5  # Réduire de 50%
                    logger.warning(f"Position size verrouillée à {trade.position_size:.2f} lots après 3 pertes consécutives")
            else:
                result = "breakeven"
                self._last_trade_was_loss = False
            
            # Mettre à jour equity
            self.current_equity += pnl
            self._daily_pnl += pnl
            self._peak_equity = max(self._peak_equity, self.current_equity)
            
            # Mettre à jour trade
            trade.exit_time = exit_time
            trade.exit_price = exit_price
            trade.result = result
            trade.pnl = round(pnl, 2)
            trade.pnl_pct = round(pnl_pct, 4)
            trade.r_multiple = round(r_multiple, 2)
            
            logger.info("Trade closed: %s %s @ %.5f | PnL: $%.2f (%.2f%%) | R: %.2f | Result: %s",
                       trade.instrument, trade.direction, exit_price, pnl, pnl_pct*100, r_multiple, result)
            
            return trade
    
    # --------------------------------------------------------
    # GESTION POSITIONS OUVERTES (Break-even, Trailing)
    # --------------------------------------------------------
    
    def check_breakeven_trigger(
        self,
        trade_id: str,
        current_price: float,
    ) -> tuple[bool, float | None]:
        """
        Vérifie si le break-even doit être déclenché.
        Returns: (should_trigger, new_sl_price)
        """
        trade = self._open_trades.get(trade_id)
        if not trade:
            return False, None
        
        cfg = get_instrument_config(trade.instrument)
        trigger_r = cfg.breakeven_trigger_r
        offset_pips = cfg.breakeven_offset_pips
        
        # Calculer R actuel
        if trade.direction == "buy":
            current_r = (current_price - trade.entry_price) / abs(trade.entry_price - trade.sl_price)
        else:
            current_r = (trade.entry_price - current_price) / abs(trade.entry_price - trade.sl_price)
        
        if current_r >= trigger_r:
            # Nouveau SL = entry + offset
            if trade.direction == "buy":
                new_sl = trade.entry_price + (offset_pips * cfg.pip_value)
            else:
                new_sl = trade.entry_price - (offset_pips * cfg.pip_value)
            
            # Ne déplacer SL que dans le sens favorable
            if trade.direction == "buy" and new_sl > trade.sl_price:
                return True, new_sl
            elif trade.direction == "sell" and new_sl < trade.sl_price:
                return True, new_sl
        
        return False, None
    
    # --------------------------------------------------------
    # ANTI-MARTINGALE & ANTI-REVENGE VALIDATION
    # --------------------------------------------------------
    
    def check_martingale_pattern(
        self,
        instrument: Instrument,
        requested_position_size: float,
        recent_trades: list[TradeRecord]
    ) -> tuple[bool, str]:
        """
        Détecte et bloque les patterns de martingale.
        
        Cahier des charges §7:
        - INTERDICTION MARTINGALE: Jamais augmenter automatiquement le risque après une perte
        - INTERDICTION REVENGE TRADING: Jamais multiplier les positions pour récupérer une perte
        - INTERDICTION AUGMENTATION: Jamais augmenter automatiquement le lot après série de pertes
        
        Returns:
            (is_allowed, reason)
        """
        with self._lock:
            cfg = get_instrument_config(instrument)
            
            # 1. Vérifier si position size est verrouillée
            if self._position_size_locked and instrument in self._locked_position_size:
                max_allowed = self._locked_position_size[instrument]
                if requested_position_size > max_allowed:
                    return False, f"Position size verrouillée à {max_allowed:.2f} lots (anti-martingale)"
            
            # 2. Détecter pattern d'augmentation de taille après pertes
            if self._last_trade_was_loss and self._consecutive_losses >= 1:
                # Après perte, limiter la taille à 80% de la normale
                base_size = calculate_position_size(
                    instrument, self.current_equity, 
                    0.0,  # Entry fictif pour calcul
                    cfg.sl_atr_multiplier * 20 * cfg.pip_value,  # SL fictif
                    cfg.risk_per_trade_pct
                )
                max_after_loss = base_size * 0.8
                if requested_position_size > max_after_loss:
                    return False, f"Taille réduite à {max_after_loss:.2f} lots après perte (anti-revenge)"
            
            # 3. Détecter pattern de multiplication des positions
            if len(recent_trades) >= 2:
                recent_sizes = [t.position_size for t in recent_trades[-3:]]
                if len(recent_sizes) >= 2:
                    # Vérifier si pattern d'augmentation détecté
                    if recent_sizes[-1] > recent_sizes[-2] * 1.2:  # 20% d'augmentation
                        return False, "Pattern d'augmentation de taille détecté (anti-martingale)"
            
            # 4. Détecter nombre excessif de positions simultanées
            open_positions = len([t for t in self._open_trades.values() if t.instrument == instrument])
            if open_positions >= 2:  # Déjà plusieurs positions
                return False, f"Positions simultanées limitées à 2 (martingale prevention)"
            
            return True, "OK"
    
    def check_position_size_increase(
        self,
        instrument: Instrument,
        current_size: float,
        new_size: float
    ) -> tuple[bool, str]:
        """
        Vérifie si une augmentation de taille de position est autorisée.
        
        Returns:
            (is_allowed, reason)
        """
        with self._lock:
            # Toujours interdit après perte
            if self._last_trade_was_loss:
                return False, "Augmentation de taille interdite après perte (anti-martingale)"
            
            # Limiter l'augmentation à 50% maximum
            if new_size > current_size * 1.5:
                return False, f"Augmentation limitée à 50% (demandé {new_size:.2f} vs {current_size:.2f})"
            
            # Si revenge trading bloqué, interdire toute augmentation
            if self._revenge_trading_blocked:
                return False, "Revenge trading bloqué - aucune augmentation autorisée"
            
            return True, "OK"
    
    def reset_martingale_protections(self, instrument: Instrument) -> None:
        """
        Réinitialise les protections anti-martingale (après période de calme).
        À utiliser manuellement ou automatiquement après condition spécifique.
        """
        with self._lock:
            if instrument in self._locked_position_size:
                del self._locked_position_size[instrument]
            self._position_size_locked = False
            self._revenge_trading_blocked = False
            self._current_position_size_multiplier = 1.0
            logger.info(f"Protections anti-martingale réinitialisées pour {instrument}")
    
    def _map_blocking_reason_to_enum(self, reason: str):
        """Map blocking reason string to TradeRejectionReason enum."""
        if not TRADE_JOURNAL_AVAILABLE:
            return None
            
        from .trade_journal import TradeRejectionReason
        
        reason_lower = reason.lower()
        
        if "rr" in reason_lower or "risk/reward" in reason_lower:
            return TradeRejectionReason.RR_INSUFFICIENT
        elif "drawdown" in reason_lower:
            return TradeRejectionReason.DRAWDOWN_LIMIT
        elif "consecutive" in reason_lower or "pertes" in reason_lower:
            return TradeRejectionReason.CONSECUTIVE_LOSSES
        elif "session" in reason_lower:
            return TradeRejectionReason.SESSION_FILTER
        elif "news" in reason_lower:
            return TradeRejectionReason.NEWS_FILTER
        elif "volatilit" in reason_lower:
            return TradeRejectionReason.VOLATILITY_FILTER
        elif "martingale" in reason_lower or "revenge" in reason_lower:
            return TradeRejectionReason.MARTINGALE_BLOCKED
        elif "position size" in reason_lower or "taille" in reason_lower:
            return TradeRejectionReason.POSITION_SIZE_INVALID
        elif "sl" in reason_lower or "stop loss" in reason_lower:
            return TradeRejectionReason.SL_PLACEMENT_INVALID
        else:
            return TradeRejectionReason.RISK_LIMIT
    
    def check_trailing_stop(
        self,
        trade_id: str,
        current_price: float,
        recent_candles: list[dict],  # For structure trailing
        current_atr: float | None = None,
    ) -> tuple[bool, float | None]:
        """
        Vérifie si le trailing stop doit être mis à jour.
        Mode trailing structurel (§9): SL suit les swings du marché.
        Returns: (should_update, new_sl_price)
        """
        trade = self._open_trades.get(trade_id)
        if not trade:
            return False, None

        cfg = get_instrument_config(trade.instrument)

        # Mode trailing structurel : suivre les swings récents
        if trade.mode == "trailing_structural" and recent_candles:
            atr = current_atr or cfg.sl_atr_multiplier * cfg.pip_value * 100
            lookback = cfg.trailing_structure_lookback

            if trade.direction == "buy":
                # Find recent swing low in candles
                swing_lows = [c["low"] for c in recent_candles[-lookback:] if "low" in c]
                if swing_lows:
                    recent_swing_low = min(swing_lows)
                    new_sl = recent_swing_low - (atr * 0.5)
                    if new_sl > trade.sl_price and new_sl < current_price:
                        trade.sl_price = new_sl
                        return True, new_sl
            else:  # sell
                # Find recent swing high in candles
                swing_highs = [c["high"] for c in recent_candles[-lookback:] if "high" in c]
                if swing_highs:
                    recent_swing_high = max(swing_highs)
                    new_sl = recent_swing_high + (atr * 0.5)
                    if new_sl < trade.sl_price and new_sl > current_price:
                        trade.sl_price = new_sl
                        return True, new_sl

        return False, None
    
    # --------------------------------------------------------
    # STATUS & REPORTING
    # --------------------------------------------------------
    
    def get_status(self, instrument: Instrument | None = None) -> dict:
        """Status complet du risk manager."""
        with self._lock:
            self._check_daily_reset()
            
            if instrument:
                return self._get_instrument_status(instrument)
            
            # Status global
            return {
                "initial_capital": self.initial_capital,
                "current_equity": round(self.current_equity, 2),
                "total_pnl": round(self.current_equity - self.initial_capital, 2),
                "total_pnl_pct": round((self.current_equity - self.initial_capital) / self.initial_capital * 100, 2),
                "daily_pnl": round(self._daily_pnl, 2),
                "daily_pnl_pct": round(self._daily_pnl / self._session_start_equity * 100, 2) if self._session_start_equity > 0 else 0,
                "peak_equity": round(self._peak_equity, 2),
                "total_drawdown_pct": round((self._peak_equity - self.current_equity) / self._peak_equity * 100, 2) if self._peak_equity > 0 else 0,
                "consecutive_losses": self._consecutive_losses,
                "trades_today": self._trades_today,
                "open_positions": len(self._open_trades),
                "total_trades": len(self._trade_history),
                "instruments": {
                    sym: self._get_instrument_status(sym)
                    for sym in ["EURUSD", "GBPUSD", "XAUUSD"]
                },
            }
    
    def _get_instrument_status(self, instrument: Instrument) -> dict:
        limits = self._limits[instrument]
        open_trades = [t for t in self._open_trades.values() if t.instrument == instrument]
        
        return {
            "instrument": instrument,
            "can_trade": False,  # Must be computed via check_all_limits()
            "open_positions": len(open_trades),
            "trades_today": self._trades_today,  # Global pour l'instant
            "limits": {
                "max_risk_per_trade_pct": limits.max_risk_per_trade_pct,
                "max_daily_drawdown_pct": limits.max_daily_drawdown_pct,
                "max_total_drawdown_pct": limits.max_total_drawdown_pct,
                "max_consecutive_losses": limits.max_consecutive_losses,
                "max_trades_per_session": limits.max_trades_per_session,
                "max_simultaneous_positions": limits.max_simultaneous_positions,
                "min_rr_ratio": limits.min_rr_ratio,
            },
            "open_trades": [
                {
                    "id": t.id,
                    "direction": t.direction,
                    "entry": t.entry_price,
                    "sl": t.sl_price,
                    "tp": t.tp_price,
                    "size": t.position_size,
                    "mode": t.mode,
                }
                for t in open_trades
            ],
        }
    
    def get_trade_history(self, instrument: Instrument | None = None, limit: int = 100) -> list[TradeRecord]:
        """Récupère l'historique des trades."""
        with self._lock:
            trades = self._trade_history
            if instrument:
                trades = [t for t in trades if t.instrument == instrument]
            return trades[-limit:]
    
    def get_statistics(self, instrument: Instrument | None = None) -> dict:
        """Calcule les statistiques de performance."""
        with self._lock:
            trades = self.get_trade_history(instrument)
            closed = [t for t in trades if t.result in ("win", "loss", "breakeven")]
            
            if not closed:
                return {"message": "Aucun trade clôturé"}
            
            wins = [t for t in closed if t.result == "win"]
            losses = [t for t in closed if t.result == "loss"]
            breakevens = [t for t in closed if t.result == "breakeven"]
            
            total_pnl = sum(t.pnl for t in closed)
            gross_profit = sum(t.pnl for t in wins)
            gross_loss = abs(sum(t.pnl for t in losses))
            
            return {
                "instrument": instrument or "ALL",
                "total_trades": len(closed),
                "wins": len(wins),
                "losses": len(losses),
                "breakevens": len(breakevens),
                "win_rate": round(len(wins) / len(closed) * 100, 2) if closed else 0,
                "avg_win": round(gross_profit / len(wins), 2) if wins else 0,
                "avg_loss": round(gross_loss / len(losses), 2) if losses else 0,
                "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else float('inf'),
                "expectancy": round(total_pnl / len(closed), 2) if closed else 0,
                "total_pnl": round(total_pnl, 2),
                "avg_r_multiple": round(sum(t.r_multiple for t in closed) / len(closed), 2) if closed else 0,
                "max_consecutive_wins": self._max_consecutive(closed, "win"),
                "max_consecutive_losses": self._max_consecutive(closed, "loss"),
                "largest_win": round(max((t.pnl for t in wins), default=0), 2),
                "largest_loss": round(min((t.pnl for t in losses), default=0), 2),
            }
    
    def _max_consecutive(self, trades: list[TradeRecord], result: TradeResult) -> int:
        max_streak = 0
        current = 0
        for t in trades:
            if t.result == result:
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
        return max_streak


# Instance globale par défaut
default_risk_manager = IctRiskManager()


# ============================================================
# HELPERS SIMPLES
# ============================================================

def check_trade_allowed(
    instrument: Instrument,
    entry: float,
    sl: float,
    tp: float,
    mode: PositionMode = "fixed_tp",
    atr_pips: float | None = None,
    direction: Literal["buy", "sell"] = "buy",
) -> RiskStatus:
    """Vérification rapide : trade autorisé ?"""
    return default_risk_manager.check_all_limits(instrument, entry, sl, tp, mode, atr_pips, direction)


def get_risk_status(instrument: Instrument | None = None) -> dict:
    """Status complet du risk manager."""
    return default_risk_manager.get_status(instrument)


def register_trade(
    trade_id: str,
    instrument: Instrument,
    direction: Literal["buy", "sell"],
    entry: float,
    sl: float,
    tp: float,
    size: float,
    risk_amt: float,
    risk_pct: float,
    rr: float,
    session: str,
    setup: str,
    mode: PositionMode = "fixed_tp",
) -> TradeRecord:
    """Enregistre un trade ouvert."""
    return default_risk_manager.register_trade_entry(
        trade_id, instrument, direction, entry, sl, tp, size, risk_amt, risk_pct, rr, session, setup, mode
    )


def close_trade(trade_id: str, exit_price: float) -> TradeRecord | None:
    """Ferme un trade."""
    return default_risk_manager.register_trade_exit(trade_id, exit_price)