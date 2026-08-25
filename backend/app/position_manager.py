"""Position Manager for ICT/SMC Trading Bot.

Implements the 4 position management modes as per cahier des charges:
- Mode A: TP fixe (Entrée → SL → TP)
- Mode B: Partiel (Fermeture partielle au premier objectif)
- Mode C: Break-even (Déplacement SL après progression suffisante)
- Mode D: Trailing structurel (SL suit la structure du marché)

Each mode can be tested separately to determine which has the best statistics.
"""

import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Literal, Optional
from enum import Enum

from .ict_config import (
    Instrument, PositionMode, get_instrument_config,
    calculate_position_size, calculate_rr_ratio, validate_rr_ratio
)
from .forex_indicators import (
    price_to_pips_forex, calculate_pip_profit, validate_sl_placement
)
from .ict_risk_manager import IctRiskManager
from .trade_journal import (
    TradeJournal, ConfluenceFactor, ConfluenceType,
    trade_journal
)

logger = logging.getLogger(__name__)


# ============================================================
# TYPES & ENUMS
# ============================================================

class TradeStatus(Enum):
    """Status of a trade position."""
    OPEN = "open"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"
    STOPPED_OUT = "stopped_out"
    CANCELLED = "cancelled"


class CloseReason(Enum):
    """Reason for position closure."""
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    PARTIAL_CLOSE = "partial_close"
    BREAK_EVEN = "break_even"
    TRAILING_STOP = "trailing_stop"
    MANUAL = "manual"
    RISK_LIMIT = "risk_limit"
    SESSION_END = "session_end"


# ============================================================
# POSITION DATA CLASSES
# ============================================================

@dataclass
class Position:
    """Represents a trading position."""
    id: str
    instrument: Instrument
    direction: Literal["buy", "sell"]
    entry_price: float
    initial_sl_price: float
    initial_tp_price: float
    position_size_lots: float
    risk_amount: float
    rr_ratio: float
    mode: PositionMode
    
    # Current state
    current_sl_price: float
    current_tp_price: float
    status: TradeStatus = TradeStatus.OPEN
    entry_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    
    # Mode-specific state
    partial_close_triggered: bool = False
    partial_close_size: float = 0.0
    breakeven_triggered: bool = False
    trailing_high_low: Optional[float] = None  # For trailing
    
    # Performance tracking
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    max_favorable_pnl: float = 0.0
    max_adverse_pnl: float = 0.0
    
    # ICT/SMC context
    setup_type: str = ""
    timeframe: str = ""
    session: str = ""
    
    # Journal integration
    journal_entry_id: str = ""  # Link to trade journal entry
    
    def __post_init__(self):
        """Initialize derived fields."""
        self.current_sl_price = self.initial_sl_price
        self.current_tp_price = self.initial_tp_price


@dataclass
class PositionUpdate:
    """Result of a position update."""
    position_id: str
    action: Literal["open", "modify", "partial_close", "close", "none"]
    reason: CloseReason | None
    new_sl: Optional[float] = None
    new_tp: Optional[float] = None
    close_size: Optional[float] = None
    close_price: Optional[float] = None
    pnl: Optional[float] = None
    message: str = ""


# ============================================================
# POSITION MANAGER CLASS
# ============================================================

class PositionManager:
    """
    Manages positions according to ICT/SMC methodology.
    
    Handles:
    - Opening positions with proper risk management
    - Managing positions according to selected mode
    - Tracking P&L and performance metrics
    - Implementing stop loss and take profit logic
    - CENTRALIZED RISK MANAGER INTEGRATION (Cahier des charges §7)
      - No strategy can bypass the risk manager
      - All positions must pass risk validation
    """
    
    def __init__(self, mode: PositionMode = "fixed_tp", risk_manager: IctRiskManager | None = None, journal: TradeJournal | None = None):
        self.mode = mode
        self.positions: dict[str, Position] = {}
        self.position_counter = 0
        self.risk_manager = risk_manager  # Centralized risk manager reference
        self.journal = journal or trade_journal  # Trade journal reference
        
    def set_mode(self, mode: PositionMode) -> None:
        """Change the position management mode."""
        self.mode = mode
        logger.info(f"Position mode changed to: {mode}")
    
    def open_position(
        self,
        instrument: Instrument,
        direction: Literal["buy", "sell"],
        entry_price: float,
        sl_price: float,
        tp_price: float,
        account_balance: float,
        setup_type: str = "",
        timeframe: str = "",
        session: str = ""
    ) -> PositionUpdate:
        """
        Open a new position with ICT/SMC validation.
        
        RÈGLE FONDAMENTALE (Cahier des charges §7):
        - Le Risk Manager centralisé doit valider TOUTES les positions
        - Aucune stratégie ne peut contourner cette validation
        - Si Risk Manager refuse → POSITION REFUSÉE
        
        Args:
            instrument: Forex instrument
            direction: buy or sell
            entry_price: Entry price
            sl_price: Stop loss price
            tp_price: Take profit price
            account_balance: Current account balance
            setup_type: ICT/SMC setup type
            timeframe: Analysis timeframe
            session: Trading session
        
        Returns:
            PositionUpdate with action result
        """
        cfg = get_instrument_config(instrument)
        
        # CENTRALIZED RISK MANAGER VALIDATION (Cahier des charges §7)
        if self.risk_manager:
            risk_status = self.risk_manager.check_all_limits(
                instrument, entry_price, sl_price, tp_price, self.mode, None, direction
            )
            if not risk_status.can_trade:
                return PositionUpdate(
                    position_id="",
                    action="none",
                    reason=None,
                    message=f"TRADE REFUSÉ par Risk Manager: {'; '.join(risk_status.blocking_reasons)}"
                )
        
        # Validate RR ratio
        rr_result = calculate_rr_ratio(instrument, entry_price, sl_price, tp_price)
        if not validate_rr_ratio(instrument, rr_result):
            return PositionUpdate(
                position_id="",
                action="none",
                reason=None,
                message=f"RR ratio {rr_result:.2f} below minimum {cfg.min_rr_ratio}"
            )
        
        # Calculate position size
        position_size = calculate_position_size(
            instrument, account_balance, entry_price, sl_price, cfg.risk_per_trade_pct
        )
        
        if position_size == 0:
            return PositionUpdate(
                position_id="",
                action="none",
                reason=None,
                message="Invalid position size calculation"
            )
        
        # Validate SL placement
        atr_pips = 20.0  # Default ATR if not available
        sl_validation = validate_sl_placement(instrument, entry_price, sl_price, atr_pips)
        if not sl_validation["is_valid"]:
            return PositionUpdate(
                position_id="",
                action="none",
                reason=None,
                message=f"SL placement invalid: {sl_validation['warning']}"
            )
        
        # Create position
        self.position_counter += 1
        position_id = f"pos_{self.position_counter:06d}"
        
        risk_amount = account_balance * cfg.risk_per_trade_pct
        
        position = Position(
            id=position_id,
            instrument=instrument,
            direction=direction,
            entry_price=entry_price,
            initial_sl_price=sl_price,
            initial_tp_price=tp_price,
            position_size_lots=position_size,
            risk_amount=risk_amount,
            rr_ratio=rr_result,
            mode=self.mode,
            setup_type=setup_type,
            timeframe=timeframe,
            session=session
        )
        
        self.positions[position_id] = position
        
        # Log to trade journal (Cahier des charges §20)
        journal_entry = self.journal.add_trade_entry(
            instrument=instrument,
            direction=direction,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            position_size_lots=position_size,
            risk_amount=risk_amount,
            risk_pct=cfg.risk_per_trade_pct,
            rr_ratio=rr_result,
            setup_type=setup_type,
            timeframe=timeframe,
            session=session,
            setup_score=0.8,  # Default score (could be calculated from confluence)
            notes=f"Position ID: {position_id}, Mode: {self.mode}"
        )
        
        # Link position to journal entry
        position.journal_entry_id = journal_entry.trade_id
        
        logger.info(f"Position opened: {position_id} {instrument} {direction} @ {entry_price}")
        
        return PositionUpdate(
            position_id=position_id,
            action="open",
            reason=None,
            new_sl=sl_price,
            new_tp=tp_price,
            message=f"Position opened: {direction} {instrument} @ {entry_price}"
        )
    
    def update_position(
        self,
        position_id: str,
        current_price: float,
        current_high: Optional[float] = None,
        current_low: Optional[float] = None
    ) -> PositionUpdate:
        """
        Update position according to current market data and selected mode.
        
        Args:
            position_id: Position identifier
            current_price: Current market price
            current_high: Current high (for trailing)
            current_low: Current low (for trailing)
        
        Returns:
            PositionUpdate with action taken
        """
        if position_id not in self.positions:
            return PositionUpdate(
                position_id=position_id,
                action="none",
                reason=None,
                message="Position not found"
            )
        
        position = self.positions[position_id]
        
        if position.status != TradeStatus.OPEN:
            return PositionUpdate(
                position_id=position_id,
                action="none",
                reason=None,
                message=f"Position already {position.status.value}"
            )
        
        # Calculate unrealized P&L
        position.unrealized_pnl = self._calculate_pnl(position, current_price)
        
        # Update max favorable/adverse P&L
        if position.unrealized_pnl > position.max_favorable_pnl:
            position.max_favorable_pnl = position.unrealized_pnl
        if position.unrealized_pnl < position.max_adverse_pnl:
            position.max_adverse_pnl = position.unrealized_pnl
        
        # Route to appropriate mode handler
        if self.mode == "fixed_tp":
            return self._handle_fixed_tp_mode(position, current_price)
        elif self.mode == "partial":
            return self._handle_partial_mode(position, current_price)
        elif self.mode == "breakeven":
            return self._handle_breakeven_mode(position, current_price)
        elif self.mode == "trailing_structural":
            return self._handle_trailing_mode(position, current_price, current_high, current_low)
        else:
            return PositionUpdate(
                position_id=position_id,
                action="none",
                reason=None,
                message=f"Unknown mode: {self.mode}"
            )
    
    def _handle_fixed_tp_mode(self, position: Position, current_price: float) -> PositionUpdate:
        """Mode A: TP fixe (Entrée → SL → TP)."""
        
        # Check SL hit
        if self._check_sl_hit(position, current_price):
            return self._close_position(position, current_price, CloseReason.STOP_LOSS)
        
        # Check TP hit
        if self._check_tp_hit(position, current_price):
            return self._close_position(position, current_price, CloseReason.TAKE_PROFIT)
        
        return PositionUpdate(
            position_id=position.id,
            action="none",
            reason=None,
            message="No action required"
        )
    
    def _handle_partial_mode(self, position: Position, current_price: float) -> PositionUpdate:
        """Mode B: Partiel (Fermeture partielle au premier objectif)."""
        cfg = get_instrument_config(position.instrument)
        
        # Check SL hit first
        if self._check_sl_hit(position, current_price):
            return self._close_position(position, current_price, CloseReason.STOP_LOSS)
        
        # Check if partial close should be triggered
        if not position.partial_close_triggered:
            first_target_r = cfg.tp_first_target_r  # Usually 1R
            risk_pips = price_to_pips_forex(position.instrument, abs(position.entry_price - position.initial_sl_price))
            first_target_pips = risk_pips * first_target_r
            
            if position.direction == "buy":
                first_target_price = position.entry_price + first_target_pips * get_instrument_config(position.instrument).pip_value
                if current_price >= first_target_price:
                    return self._partial_close_position(position, current_price, cfg.partial_close_pct)
            else:  # sell
                first_target_price = position.entry_price - first_target_pips * get_instrument_config(position.instrument).pip_value
                if current_price <= first_target_price:
                    return self._partial_close_position(position, current_price, cfg.partial_close_pct)
        
        # Check final TP hit on remaining position
        if self._check_tp_hit(position, current_price):
            return self._close_position(position, current_price, CloseReason.TAKE_PROFIT)
        
        return PositionUpdate(
            position_id=position.id,
            action="none",
            reason=None,
            message="No action required"
        )
    
    def _handle_breakeven_mode(self, position: Position, current_price: float) -> PositionUpdate:
        """Mode C: Break-even (Déplacement SL après progression suffisante)."""
        cfg = get_instrument_config(position.instrument)
        
        # Check SL hit
        if self._check_sl_hit(position, current_price):
            return self._close_position(position, current_price, CloseReason.STOP_LOSS)
        
        # Check TP hit
        if self._check_tp_hit(position, current_price):
            return self._close_position(position, current_price, CloseReason.TAKE_PROFIT)
        
        # Check if breakeven should be triggered
        if not position.breakeven_triggered:
            trigger_r = cfg.breakeven_trigger_r  # Usually 1R
            risk_pips = price_to_pips_forex(position.instrument, abs(position.entry_price - position.initial_sl_price))
            trigger_pips = risk_pips * trigger_r
            
            if position.direction == "buy":
                trigger_price = position.entry_price + trigger_pips * get_instrument_config(position.instrument).pip_value
                if current_price >= trigger_price:
                    return self._move_to_breakeven(position, cfg.breakeven_offset_pips)
            else:  # sell
                trigger_price = position.entry_price - trigger_pips * get_instrument_config(position.instrument).pip_value
                if current_price <= trigger_price:
                    return self._move_to_breakeven(position, cfg.breakeven_offset_pips)
        
        return PositionUpdate(
            position_id=position.id,
            action="none",
            reason=None,
            message="No action required"
        )
    
    def _handle_trailing_mode(
        self,
        position: Position,
        current_price: float,
        current_high: Optional[float],
        current_low: Optional[float]
    ) -> PositionUpdate:
        """Mode D: Trailing structurel (SL suit la structure du marché)."""
        cfg = get_instrument_config(position.instrument)
        
        # Check SL hit
        if self._check_sl_hit(position, current_price):
            return self._close_position(position, current_price, CloseReason.STOP_LOSS)
        
        # Check TP hit
        if self._check_tp_hit(position, current_price):
            return self._close_position(position, current_price, CloseReason.TAKE_PROFIT)
        
        # Implement trailing stop based on structure
        lookback = cfg.trailing_structure_lookback
        pip_value = get_instrument_config(position.instrument).pip_value
        atr_multiplier = cfg.trailing_atr_multiplier
        
        # Simple trailing logic: move SL behind recent swing point
        if position.direction == "buy":
            if current_high:
                # Trail SL below recent high with ATR buffer
                new_sl = current_high - (atr_multiplier * 20 * pip_value)  # 20 pips ATR buffer
                
                # Only move SL up (never down)
                if new_sl > position.current_sl_price and new_sl < current_price:
                    position.current_sl_price = new_sl
                    position.trailing_high_low = current_high
                    
                    return PositionUpdate(
                        position_id=position.id,
                        action="modify",
                        reason=CloseReason.TRAILING_STOP,
                        new_sl=new_sl,
                        message=f"Trailing SL moved to {new_sl}"
                    )
        else:  # sell
            if current_low:
                # Trail SL above recent low with ATR buffer
                new_sl = current_low + (atr_multiplier * 20 * pip_value)
                
                # Only move SL down (never up)
                if new_sl < position.current_sl_price and new_sl > current_price:
                    position.current_sl_price = new_sl
                    position.trailing_high_low = current_low
                    
                    return PositionUpdate(
                        position_id=position.id,
                        action="modify",
                        reason=CloseReason.TRAILING_STOP,
                        new_sl=new_sl,
                        message=f"Trailing SL moved to {new_sl}"
                    )
        
        return PositionUpdate(
            position_id=position.id,
            action="none",
            reason=None,
            message="No action required"
        )
    
    def _check_sl_hit(self, position: Position, current_price: float) -> bool:
        """Check if stop loss has been hit."""
        if position.direction == "buy":
            return current_price <= position.current_sl_price
        else:  # sell
            return current_price >= position.current_sl_price
    
    def _check_tp_hit(self, position: Position, current_price: float) -> bool:
        """Check if take profit has been hit."""
        if position.direction == "buy":
            return current_price >= position.current_tp_price
        else:  # sell
            return current_price <= position.current_tp_price
    
    def _close_position(self, position: Position, exit_price: float, reason: CloseReason) -> PositionUpdate:
        """Close a position and calculate final P&L."""
        position.status = TradeStatus.CLOSED
        position.exit_time = datetime.now(timezone.utc)
        position.exit_price = exit_price
        position.realized_pnl = self._calculate_pnl(position, exit_price)
        
        # Determine result
        if position.realized_pnl > 0:
            result = "win"
        elif position.realized_pnl < 0:
            result = "loss"
        else:
            result = "breakeven"
        
        # Calculate P&L percentage and R-multiple
        pnl_pct = (position.realized_pnl / position.risk_amount) * 100 if position.risk_amount > 0 else 0.0
        r_multiple = position.realized_pnl / position.risk_amount if position.risk_amount > 0 else 0.0
        
        # Update trade journal (Cahier des charges §20)
        if position.journal_entry_id:
            self.journal.update_trade_exit(
                trade_id=position.journal_entry_id,
                exit_price=exit_price,
                result=result,
                pnl=position.realized_pnl,
                pnl_pct=pnl_pct,
                r_multiple=r_multiple,
                drawdown_at_close=0.0  # Would need to track current drawdown
            )
        
        # Remove from active positions
        del self.positions[position.id]
        
        logger.info(f"Position closed: {position.id} - Reason: {reason.value}, P&L: {position.realized_pnl:.2f}")
        
        return PositionUpdate(
            position_id=position.id,
            action="close",
            reason=reason,
            close_price=exit_price,
            close_size=position.position_size_lots,
            pnl=position.realized_pnl,
            message=f"Position closed: {reason.value}, P&L: {position.realized_pnl:.2f}"
        )
    
    def _partial_close_position(self, position: Position, current_price: float, close_percentage: float) -> PositionUpdate:
        """Partially close a position."""
        position.status = TradeStatus.PARTIALLY_CLOSED
        position.partial_close_triggered = True
        position.partial_close_size = close_percentage
        
        close_size_lots = position.position_size_lots * close_percentage
        partial_pnl = self._calculate_pnl(position, current_price, close_size_lots)
        
        # Reduce position size
        position.position_size_lots -= close_size_lots
        position.realized_pnl = partial_pnl
        
        logger.info(f"Partial close: {position.id} - {close_percentage:.0%} at {current_price}, P&L: {partial_pnl:.2f}")
        
        return PositionUpdate(
            position_id=position.id,
            action="partial_close",
            reason=CloseReason.PARTIAL_CLOSE,
            close_price=current_price,
            close_size=close_size_lots,
            pnl=partial_pnl,
            message=f"Partial close: {close_percentage:.0%} at {current_price}"
        )
    
    def _move_to_breakeven(self, position: Position, offset_pips: float) -> PositionUpdate:
        """Move stop loss to breakeven with offset."""
        pip_value = get_instrument_config(position.instrument).pip_value
        offset_price = offset_pips * pip_value
        
        if position.direction == "buy":
            new_sl = position.entry_price + offset_price
        else:  # sell
            new_sl = position.entry_price - offset_price
        
        position.current_sl_price = new_sl
        position.breakeven_triggered = True
        
        logger.info(f"Breakeven triggered: {position.id} - SL moved to {new_sl}")
        
        return PositionUpdate(
            position_id=position.id,
            action="modify",
            reason=CloseReason.BREAK_EVEN,
            new_sl=new_sl,
            message=f"Breakeven: SL moved to {new_sl}"
        )
    
    def _calculate_pnl(self, position: Position, exit_price: float, size_lots: Optional[float] = None) -> float:
        """Calculate P&L for position or partial close."""
        size = size_lots if size_lots is not None else position.position_size_lots
        
        if position.direction == "buy":
            price_diff = exit_price - position.entry_price
        else:  # sell
            price_diff = position.entry_price - exit_price
        
        return calculate_pip_profit(position.instrument, position.entry_price, exit_price, size)["currency_profit"]
    
    def get_position(self, position_id: str) -> Optional[Position]:
        """Get position by ID."""
        return self.positions.get(position_id)
    
    def get_all_positions(self) -> list[Position]:
        """Get all active positions."""
        return list(self.positions.values())
    
    def get_position_count(self) -> int:
        """Get count of active positions."""
        return len(self.positions)


# ============================================================
# GLOBAL INSTANCE
# ============================================================

position_manager = PositionManager()


def initialize_with_risk_manager(risk_manager: IctRiskManager, journal: TradeJournal | None = None) -> None:
    """Initialize the global position manager with a risk manager and journal."""
    global position_manager
    position_manager = PositionManager(risk_manager=risk_manager, journal=journal)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def set_position_mode(mode: PositionMode) -> None:
    """Set the global position management mode."""
    position_manager.set_mode(mode)


def get_position_mode() -> PositionMode:
    """Get the current position management mode."""
    return position_manager.mode


def open_trade_position(
    instrument: Instrument,
    direction: Literal["buy", "sell"],
    entry_price: float,
    sl_price: float,
    tp_price: float,
    account_balance: float,
    setup_type: str = "",
    timeframe: str = "",
    session: str = ""
) -> PositionUpdate:
    """Open a new trading position using global manager."""
    return position_manager.open_position(
        instrument, direction, entry_price, sl_price, tp_price,
        account_balance, setup_type, timeframe, session
    )


def update_trade_position(
    position_id: str,
    current_price: float,
    current_high: Optional[float] = None,
    current_low: Optional[float] = None
) -> PositionUpdate:
    """Update a trading position using global manager."""
    return position_manager.update_position(position_id, current_price, current_high, current_low)


def get_active_positions() -> list[Position]:
    """Get all active positions using global manager."""
    return position_manager.get_all_positions()


def close_position(position_id: str, exit_price: float, reason: CloseReason) -> PositionUpdate:
    """Manually close a position."""
    position = position_manager.get_position(position_id)
    if position:
        return position_manager._close_position(position, exit_price, reason)
    return PositionUpdate(
        position_id=position_id,
        action="none",
        reason=None,
        message="Position not found"
    )
