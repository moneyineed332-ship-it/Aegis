"""Trade Journal for ICT/SMC Trading Bot.

Implements comprehensive trade journaling according to cahier des charges.

Required format (Cahier des charges §20):
"Date | Instrument | Direction | Setup | Timeframe | Entrée | SL | TP | Risque | Résultat | R/R | Drawdown"

Additional requirements:
- Confluence reasons
- Rejected-trade reasons
- Setup score
- Relevant structure/liquidity/FVG/OB data
- Complete ICT/SMC context for every trade
"""

import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Literal, Optional, Dict, List
from enum import Enum
import json
import csv
from io import StringIO

from .ict_config import Instrument, PositionMode, get_instrument_config

# Optional import to avoid circular dependency
try:
    from .ict_risk_manager import TradeRecord
except ImportError:
    # Define TradeRecord locally if import fails
    from dataclasses import dataclass
    from datetime import datetime
    from typing import Literal
    
    @dataclass
    class TradeRecord:
        id: str
        instrument: Instrument
        direction: Literal["buy", "sell"]
        entry_price: float
        sl_price: float
        tp_price: float
        position_size: float
        risk_amount: float
        risk_pct: float
        rr_ratio: float
        entry_time: datetime
        exit_time: datetime | None = None
        exit_price: float | None = None
        result: Literal["win", "loss", "breakeven", "open"] = "open"
        pnl: float = 0.0
        pnl_pct: float = 0.0
        r_multiple: float = 0.0
        session: str = ""
        setup_type: str = ""
        mode: PositionMode = "fixed_tp"
        notes: str = ""

logger = logging.getLogger(__name__)


# ============================================================
# TYPES & ENUMS
# ============================================================

class TradeRejectionReason(Enum):
    """Reasons for trade rejection."""
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


class ConfluenceType(Enum):
    """Types of confluence factors."""
    MARKET_STRUCTURE = "market_structure"
    LIQUIDITY_SWEEP = "liquidity_sweep"
    ORDER_BLOCK = "order_block"
    FAIR_VALUE_GAP = "fair_value_gap"
    PREMIUM_DISCOUNT = "premium_discount"
    SESSION_ALIGNMENT = "session_alignment"
    TREND_ALIGNMENT = "trend_alignment"


# ============================================================
# JOURNAL ENTRY DATA CLASSES
# ============================================================

@dataclass
class ConfluenceFactor:
    """Individual confluence factor."""
    type: ConfluenceType
    description: str
    strength: float  # 0.0 to 1.0
    price_level: Optional[float] = None
    timeframe: Optional[str] = None


@dataclass
class ICTStructureData:
    """ICT structure data for journal entry."""
    structure_type: str  # HH, HL, LH, LL, BOS, CHoCH
    direction: Literal["bullish", "bearish"]
    price_level: float
    swing_point_price: float
    timeframe: str
    index: int
    time: datetime


@dataclass
class LiquidityData:
    """Liquidity data for journal entry."""
    liquidity_type: str  # internal, external, equal_highs, equal_lows
    price_level: float
    sweep_detected: bool
    sweep_price: Optional[float] = None
    sweep_time: Optional[datetime] = None
    confirmed: bool = False


@dataclass
class ZoneData:
    """Order Block or FVG data for journal entry."""
    zone_type: str  # order_block, fair_value_gap
    direction: Literal["bullish", "bearish"]
    price_low: float
    price_high: float
    fill_status: str  # open, partially_filled, filled
    fill_percentage: float
    retest_count: int
    timeframe: str
    significance: str  # normal, moderate, strong


@dataclass
class TradeJournalEntry:
    """
    Complete trade journal entry per cahier des charges §20.
    
    Format: "Date | Instrument | Direction | Setup | Timeframe | Entrée | SL | TP | Risque | Résultat | R/R | Drawdown"
    Plus: confluence reasons, rejection reasons, setup score, ICT/SMC data
    """
    # Core fields (required format)
    date: datetime
    instrument: Instrument
    direction: Literal["buy", "sell"]
    setup_type: str
    timeframe: str
    entry_price: float
    sl_price: float
    tp_price: float
    risk_amount: float
    risk_pct: float
    result: Literal["win", "loss", "breakeven", "rejected", "open"]
    rr_ratio: float
    drawdown_at_close: float
    
    # Additional mandatory fields
    position_size_lots: float
    exit_price: Optional[float] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    r_multiple: float = 0.0
    trade_id: str = ""
    
    # ICT/SMC context
    confluence_factors: List[ConfluenceFactor] = field(default_factory=list)
    setup_score: float = 0.0  # 0.0 to 1.0
    
    # Structure data
    market_structure: Optional[ICTStructureData] = None
    liquidity_data: Optional[LiquidityData] = None
    order_block_data: Optional[ZoneData] = None
    fvg_data: Optional[ZoneData] = None
    
    # Premium/Discount
    in_premium_zone: bool = False
    in_discount_zone: bool = False
    
    # Session and filters
    session: str = ""
    session_allowed: bool = True
    news_blocked: bool = False
    volatility_status: str = "normal"
    
    # Rejection data (if rejected)
    rejection_reason: Optional[TradeRejectionReason] = None
    rejection_details: str = ""
    
    # Timing
    entry_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    exit_time: Optional[datetime] = None
    duration_hours: float = 0.0
    
    # Notes
    notes: str = ""
    
    def to_cahier_format(self) -> str:
        """
        Convert to cahier des charges format string.
        
        Format: "Date | Instrument | Direction | Setup | Timeframe | Entrée | SL | TP | Risque | Résultat | R/R | Drawdown"
        """
        return (
            f"{self.date.strftime('%Y-%m-%d %H:%M')} | "
            f"{self.instrument} | "
            f"{self.direction.upper()} | "
            f"{self.setup_type} | "
            f"{self.timeframe} | "
            f"{self.entry_price:.5f} | "
            f"{self.sl_price:.5f} | "
            f"{self.tp_price:.5f} | "
            f"{self.risk_amount:.2f}€ ({self.risk_pct:.2%}) | "
            f"{self.result.upper()} | "
            f"{self.rr_ratio:.2f} | "
            f"{self.drawdown_at_close:.2%}"
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export."""
        return {
            "trade_id": self.trade_id,
            "date": self.date.isoformat(),
            "instrument": self.instrument,
            "direction": self.direction,
            "setup_type": self.setup_type,
            "timeframe": self.timeframe,
            "entry_price": self.entry_price,
            "sl_price": self.sl_price,
            "tp_price": self.tp_price,
            "risk_amount": self.risk_amount,
            "risk_pct": self.risk_pct,
            "result": self.result,
            "rr_ratio": self.rr_ratio,
            "drawdown_at_close": self.drawdown_at_close,
            "position_size_lots": self.position_size_lots,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "r_multiple": self.r_multiple,
            "setup_score": self.setup_score,
            "confluence_factors": [
                {
                    "type": cf.type.value,
                    "description": cf.description,
                    "strength": cf.strength,
                    "price_level": cf.price_level,
                    "timeframe": cf.timeframe
                }
                for cf in self.confluence_factors
            ],
            "market_structure": {
                "type": self.market_structure.structure_type,
                "direction": self.market_structure.direction,
                "price_level": self.market_structure.price_level,
                "swing_point_price": self.market_structure.swing_point_price,
                "timeframe": self.market_structure.timeframe
            } if self.market_structure else None,
            "liquidity_data": {
                "type": self.liquidity_data.liquidity_type,
                "price_level": self.liquidity_data.price_level,
                "sweep_detected": self.liquidity_data.sweep_detected,
                "confirmed": self.liquidity_data.confirmed
            } if self.liquidity_data else None,
            "order_block_data": {
                "direction": self.order_block_data.direction,
                "price_low": self.order_block_data.price_low,
                "price_high": self.order_block_data.price_high,
                "fill_status": self.order_block_data.fill_status,
                "retest_count": self.order_block_data.retest_count
            } if self.order_block_data else None,
            "fvg_data": {
                "direction": self.fvg_data.direction,
                "price_low": self.fvg_data.price_low,
                "price_high": self.fvg_data.price_high,
                "fill_status": self.fvg_data.fill_status,
                "significance": self.fvg_data.significance
            } if self.fvg_data else None,
            "in_premium_zone": self.in_premium_zone,
            "in_discount_zone": self.in_discount_zone,
            "session": self.session,
            "session_allowed": self.session_allowed,
            "news_blocked": self.news_blocked,
            "volatility_status": self.volatility_status,
            "rejection_reason": self.rejection_reason.value if self.rejection_reason else None,
            "rejection_details": self.rejection_details,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "duration_hours": self.duration_hours,
            "notes": self.notes
        }


# ============================================================
# TRADE JOURNAL MANAGER
# ============================================================

class TradeJournal:
    """
    Comprehensive trade journal manager.
    
    Maintains complete ICT/SMC context for every trade including:
    - Standard format per cahier des charges
    - Confluence factors with strength scoring
    - ICT structure data (HH, HL, LH, LL, BOS, CHoCH)
    - Liquidity sweep confirmation
    - Order Block and FVG status
    - Rejection reasons for declined trades
    - Export capabilities (CSV, JSON)
    """
    
    def __init__(self):
        self.entries: List[TradeJournalEntry] = []
        self.rejected_entries: List[TradeJournalEntry] = []
        self._entry_counter = 0
    
    def add_trade_entry(
        self,
        instrument: Instrument,
        direction: Literal["buy", "sell"],
        entry_price: float,
        sl_price: float,
        tp_price: float,
        position_size_lots: float,
        risk_amount: float,
        risk_pct: float,
        rr_ratio: float,
        setup_type: str = "",
        timeframe: str = "",
        session: str = "",
        setup_score: float = 0.0,
        confluence_factors: List[ConfluenceFactor] | None = None,
        market_structure: ICTStructureData | None = None,
        liquidity_data: LiquidityData | None = None,
        order_block_data: ZoneData | None = None,
        fvg_data: ZoneData | None = None,
        in_premium_zone: bool = False,
        in_discount_zone: bool = False,
        notes: str = ""
    ) -> TradeJournalEntry:
        """
        Add a new trade entry to the journal.
        
        Args:
            instrument: Forex instrument
            direction: buy or sell
            entry_price: Entry price
            sl_price: Stop loss price
            tp_price: Take profit price
            position_size_lots: Position size in lots
            risk_amount: Risk amount in currency
            risk_pct: Risk percentage
            rr_ratio: Risk/Reward ratio
            setup_type: ICT/SMC setup type
            timeframe: Analysis timeframe
            session: Trading session
            setup_score: Confluence score (0.0 to 1.0)
            confluence_factors: List of confluence factors
            market_structure: ICT structure data
            liquidity_data: Liquidity sweep data
            order_block_data: Order block data
            fvg_data: Fair value gap data
            in_premium_zone: Entry in premium zone
            in_discount_zone: Entry in discount zone
            notes: Additional notes
        
        Returns:
            TradeJournalEntry
        """
        self._entry_counter += 1
        trade_id = f"journal_{self._entry_counter:06d}"
        
        entry = TradeJournalEntry(
            trade_id=trade_id,
            date=datetime.now(timezone.utc),
            instrument=instrument,
            direction=direction,
            setup_type=setup_type,
            timeframe=timeframe,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            risk_amount=risk_amount,
            risk_pct=risk_pct,
            result="open",
            rr_ratio=rr_ratio,
            drawdown_at_close=0.0,
            position_size_lots=position_size_lots,
            setup_score=setup_score,
            confluence_factors=confluence_factors or [],
            market_structure=market_structure,
            liquidity_data=liquidity_data,
            order_block_data=order_block_data,
            fvg_data=fvg_data,
            in_premium_zone=in_premium_zone,
            in_discount_zone=in_discount_zone,
            session=session,
            notes=notes
        )
        
        self.entries.append(entry)
        logger.info(f"Trade journal entry added: {trade_id} - {instrument} {direction}")
        
        return entry
    
    def add_rejected_trade(
        self,
        instrument: Instrument,
        direction: Literal["buy", "sell"],
        entry_price: float,
        sl_price: float,
        tp_price: float,
        rejection_reason: TradeRejectionReason,
        rejection_details: str = "",
        setup_type: str = "",
        timeframe: str = "",
        setup_score: float = 0.0,
        confluence_factors: List[ConfluenceFactor] | None = None,
        market_structure: ICTStructureData | None = None,
        liquidity_data: LiquidityData | None = None,
        notes: str = ""
    ) -> TradeJournalEntry:
        """
        Add a rejected trade entry to the journal.
        
        Args:
            rejection_reason: Reason for rejection
            rejection_details: Detailed explanation
            (other params same as add_trade_entry)
        
        Returns:
            TradeJournalEntry with result="rejected"
        """
        self._entry_counter += 1
        trade_id = f"rejected_{self._entry_counter:06d}"
        
        cfg = get_instrument_config(instrument)
        risk_amount = 0.0  # Not executed, no risk taken
        risk_pct = 0.0
        rr_ratio = 0.0
        position_size_lots = 0.0
        
        entry = TradeJournalEntry(
            trade_id=trade_id,
            date=datetime.now(timezone.utc),
            instrument=instrument,
            direction=direction,
            setup_type=setup_type,
            timeframe=timeframe,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            risk_amount=risk_amount,
            risk_pct=risk_pct,
            result="rejected",
            rr_ratio=rr_ratio,
            drawdown_at_close=0.0,
            position_size_lots=position_size_lots,
            setup_score=setup_score,
            confluence_factors=confluence_factors or [],
            market_structure=market_structure,
            liquidity_data=liquidity_data,
            rejection_reason=rejection_reason,
            rejection_details=rejection_details,
            notes=notes
        )
        
        self.rejected_entries.append(entry)
        logger.info(f"Rejected trade journal entry added: {trade_id} - {rejection_reason.value}")
        
        return entry
    
    def update_trade_exit(
        self,
        trade_id: str,
        exit_price: float,
        result: Literal["win", "loss", "breakeven"],
        pnl: float,
        pnl_pct: float,
        r_multiple: float,
        drawdown_at_close: float,
        exit_time: datetime | None = None
    ) -> Optional[TradeJournalEntry]:
        """
        Update an existing trade entry with exit information.
        
        Args:
            trade_id: Trade identifier
            exit_price: Exit price
            result: Trade result
            pnl: Profit/loss in currency
            pnl_pct: Profit/loss percentage
            r_multiple: R-multiple achieved
            drawdown_at_close: Drawdown at close
            exit_time: Exit time (default: now)
        
        Returns:
            Updated TradeJournalEntry or None if not found
        """
        for entry in self.entries:
            if entry.trade_id == trade_id:
                entry.exit_price = exit_price
                entry.result = result
                entry.pnl = pnl
                entry.pnl_pct = pnl_pct
                entry.r_multiple = r_multiple
                entry.drawdown_at_close = drawdown_at_close
                entry.exit_time = exit_time or datetime.now(timezone.utc)
                
                if entry.entry_time:
                    entry.duration_hours = (entry.exit_time - entry.entry_time).total_seconds() / 3600

                logger.info(f"Trade journal entry updated: {trade_id} - {result}")
                self._persist_closed_trade(entry)
                return entry

        logger.warning(f"Trade journal entry not found: {trade_id}")
        return None

    def _persist_closed_trade(self, entry: "TradeJournalEntry") -> None:
        """Persist a closed trade to the SQL journal (survives restarts)."""
        try:
            from . import storage
            date = entry.date.isoformat() if hasattr(entry.date, "isoformat") else str(entry.date)
            storage.save_ict_trade_journal(
                date=date,
                instrument=str(entry.instrument),
                direction=str(entry.direction),
                setup=entry.setup_type or "",
                timeframe=entry.timeframe or "",
                entry_price=float(entry.entry_price),
                sl_price=float(entry.sl_price),
                tp_price=float(entry.tp_price),
                risk_amount=float(entry.risk_amount),
                result=str(entry.result),
                rr_ratio=float(entry.rr_ratio),
                drawdown=float(entry.drawdown_at_close or 0),
                pnl=float(entry.pnl or 0),
                notes=entry.notes or "",
            )
        except Exception as exc:
            logger.warning(f"Failed to persist journal entry {entry.trade_id}: {exc}")
    
    def get_entry(self, trade_id: str) -> Optional[TradeJournalEntry]:
        """Get a journal entry by ID."""
        for entry in self.entries:
            if entry.trade_id == trade_id:
                return entry
        return None
    
    def get_all_entries(self) -> List[TradeJournalEntry]:
        """Get all journal entries."""
        return self.entries
    
    def get_rejected_entries(self) -> List[TradeJournalEntry]:
        """Get all rejected trade entries."""
        return self.rejected_entries
    
    def get_entries_by_instrument(self, instrument: Instrument) -> List[TradeJournalEntry]:
        """Get all entries for a specific instrument."""
        return [e for e in self.entries if e.instrument == instrument]
    
    def get_entries_by_result(self, result: Literal["win", "loss", "breakeven"]) -> List[TradeJournalEntry]:
        """Get all entries with a specific result."""
        return [e for e in self.entries if e.result == result]
    
    def get_entries_by_setup(self, setup_type: str) -> List[TradeJournalEntry]:
        """Get all entries with a specific setup type."""
        return [e for e in self.entries if e.setup_type == setup_type]
    
    def export_to_csv(self, include_rejected: bool = False) -> str:
        """
        Export journal to CSV format.
        
        Args:
            include_rejected: Include rejected trades in export
        
        Returns:
            CSV string
        """
        output = StringIO()
        writer = csv.writer(output)
        
        # Header (cahier des charges format)
        header = [
            "Date", "Instrument", "Direction", "Setup", "Timeframe",
            "Entry", "SL", "TP", "Risk", "Result", "R/R", "Drawdown",
            "PnL", "PnL%", "R-Multiple", "Setup Score", "Session",
            "Confluence Count", "OB Status", "FVG Status", "Liquidity Sweep",
            "Rejection Reason", "Notes"
        ]
        writer.writerow(header)
        
        # Write entries
        all_entries = self.entries + (self.rejected_entries if include_rejected else [])
        
        for entry in all_entries:
            row = [
                entry.date.strftime('%Y-%m-%d %H:%M:%S'),
                entry.instrument,
                entry.direction,
                entry.setup_type,
                entry.timeframe,
                f"{entry.entry_price:.5f}",
                f"{entry.sl_price:.5f}",
                f"{entry.tp_price:.5f}",
                f"{entry.risk_amount:.2f}",
                entry.result,
                f"{entry.rr_ratio:.2f}",
                f"{entry.drawdown_at_close:.2%}",
                f"{entry.pnl:.2f}",
                f"{entry.pnl_pct:.2%}",
                f"{entry.r_multiple:.2f}",
                f"{entry.setup_score:.2f}",
                entry.session,
                len(entry.confluence_factors),
                entry.order_block_data.fill_status if entry.order_block_data else "",
                entry.fvg_data.fill_status if entry.fvg_data else "",
                entry.liquidity_data.sweep_detected if entry.liquidity_data else False,
                entry.rejection_reason.value if entry.rejection_reason else "",
                entry.notes
            ]
            writer.writerow(row)
        
        return output.getvalue()
    
    def export_to_json(self, include_rejected: bool = False) -> str:
        """
        Export journal to JSON format.
        
        Args:
            include_rejected: Include rejected trades in export
        
        Returns:
            JSON string
        """
        all_entries = self.entries + (self.rejected_entries if include_rejected else [])
        data = [entry.to_dict() for entry in all_entries]
        return json.dumps(data, indent=2, default=str)
    
    def get_cahier_format_lines(self) -> List[str]:
        """
        Get all entries in cahier des charges format.
        
        Returns:
            List of formatted strings
        """
        return [entry.to_cahier_format() for entry in self.entries]
    
    def get_statistics(self) -> dict:
        """Get comprehensive journal statistics (Cahier des charges §15)."""
        if not self.entries:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "breakeven_trades": 0,
                "rejected_trades": len(self.rejected_entries),
                "win_rate": 0.0,
                "average_setup_score": 0.0,
                "average_rr": 0.0,
                "profit_factor": 0.0,
                "expectancy_per_trade": 0.0,
                "max_drawdown_pct": 0.0,
                "max_consecutive_losses": 0,
                "max_consecutive_wins": 0,
                "avg_win_pct": 0.0,
                "avg_loss_pct": 0.0,
                "reward_risk_ratio": 0.0,
                "by_instrument": {},
                "by_session": {},
            }

        winning = [e for e in self.entries if e.result == "win"]
        losing = [e for e in self.entries if e.result == "loss"]
        breakeven = [e for e in self.entries if e.result == "breakeven"]

        avg_setup_score = sum(e.setup_score for e in self.entries) / len(self.entries)
        avg_rr = sum(e.rr_ratio for e in self.entries) / len(self.entries)

        # Win/loss P&L
        total_win_pnl = sum(e.pnl for e in winning)
        total_loss_pnl = abs(sum(e.pnl for e in losing))
        avg_win_pnl = total_win_pnl / len(winning) if winning else 0.0
        avg_loss_pnl = total_loss_pnl / len(losing) if losing else 0.0

        # Profit factor
        profit_factor = total_win_pnl / total_loss_pnl if total_loss_pnl > 0 else float("inf")

        # Expectancy per trade
        total_pnl = sum(e.pnl for e in self.entries)
        expectancy = total_pnl / len(self.entries) if self.entries else 0.0

        # Reward/risk ratio
        reward_risk = avg_win_pnl / avg_loss_pnl if avg_loss_pnl > 0 else 0.0

        # Max drawdown (from equity curve)
        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        for e in self.entries:
            equity += e.pnl
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        # Max consecutive wins/losses
        max_consec_wins = 0
        max_consec_losses = 0
        current_wins = 0
        current_losses = 0
        for e in self.entries:
            if e.result == "win":
                current_wins += 1
                current_losses = 0
                max_consec_wins = max(max_consec_wins, current_wins)
            elif e.result == "loss":
                current_losses += 1
                current_wins = 0
                max_consec_losses = max(max_consec_losses, current_losses)
            else:
                current_wins = 0
                current_losses = 0

        # By instrument
        by_instrument = {}
        for e in self.entries:
            if e.instrument not in by_instrument:
                by_instrument[e.instrument] = {"trades": 0, "wins": 0, "pnl": 0.0}
            by_instrument[e.instrument]["trades"] += 1
            if e.result == "win":
                by_instrument[e.instrument]["wins"] += 1
            by_instrument[e.instrument]["pnl"] += e.pnl

        # By session
        by_session = {}
        for e in self.entries:
            sess = e.session or "unknown"
            if sess not in by_session:
                by_session[sess] = {"trades": 0, "wins": 0, "pnl": 0.0}
            by_session[sess]["trades"] += 1
            if e.result == "win":
                by_session[sess]["wins"] += 1
            by_session[sess]["pnl"] += e.pnl

        return {
            "total_trades": len(self.entries),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "breakeven_trades": len(breakeven),
            "rejected_trades": len(self.rejected_entries),
            "win_rate": len(winning) / len(self.entries) if self.entries else 0.0,
            "average_setup_score": avg_setup_score,
            "average_rr": avg_rr,
            "profit_factor": profit_factor,
            "expectancy_per_trade": expectancy,
            "max_drawdown_pct": max_dd,
            "max_consecutive_losses": max_consec_losses,
            "max_consecutive_wins": max_consec_wins,
            "avg_win_pnl": avg_win_pnl,
            "avg_loss_pnl": avg_loss_pnl,
            "reward_risk_ratio": reward_risk,
            "total_pnl": total_pnl,
            "by_instrument": by_instrument,
            "by_session": by_session,
        }


# ============================================================
# GLOBAL INSTANCE
# ============================================================

trade_journal = TradeJournal()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def log_trade(
    instrument: Instrument,
    direction: Literal["buy", "sell"],
    entry_price: float,
    sl_price: float,
    tp_price: float,
    position_size_lots: float,
    risk_amount: float,
    risk_pct: float,
    rr_ratio: float,
    setup_type: str = "",
    timeframe: str = "",
    session: str = "",
    **kwargs
) -> TradeJournalEntry:
    """Log a trade using the global journal."""
    return trade_journal.add_trade_entry(
        instrument, direction, entry_price, sl_price, tp_price,
        position_size_lots, risk_amount, risk_pct, rr_ratio,
        setup_type, timeframe, session, **kwargs
    )


def log_rejected_trade(
    instrument: Instrument,
    direction: Literal["buy", "sell"],
    entry_price: float,
    sl_price: float,
    tp_price: float,
    rejection_reason: TradeRejectionReason,
    rejection_details: str = "",
    **kwargs
) -> TradeJournalEntry:
    """Log a rejected trade using the global journal."""
    return trade_journal.add_rejected_trade(
        instrument, direction, entry_price, sl_price, tp_price,
        rejection_reason, rejection_details, **kwargs
    )


def update_trade_exit(
    trade_id: str,
    exit_price: float,
    result: Literal["win", "loss", "breakeven"],
    pnl: float,
    pnl_pct: float,
    r_multiple: float,
    drawdown_at_close: float
) -> Optional[TradeJournalEntry]:
    """Update trade exit using the global journal."""
    return trade_journal.update_trade_exit(
        trade_id, exit_price, result, pnl, pnl_pct, r_multiple, drawdown_at_close
    )


def get_journal_entries() -> List[TradeJournalEntry]:
    """Get all journal entries using the global journal."""
    return trade_journal.get_all_entries()


def export_journal_csv(include_rejected: bool = False) -> str:
    """Export journal to CSV using the global journal."""
    return trade_journal.export_to_csv(include_rejected)


def export_journal_json(include_rejected: bool = False) -> str:
    """Export journal to JSON using the global journal."""
    return trade_journal.export_to_json(include_rejected)
