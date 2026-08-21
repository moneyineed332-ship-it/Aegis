"""ICT/SMC Dashboard Router for Forex Trading Bot.

Provides API endpoints for the dashboard according to cahier des charges:
- Capital metrics (initial, current, P&L, drawdown)
- Market analysis (instrument, trend, structure, liquidity, FVG, OB, signal)
- Risk metrics (next-trade risk, daily loss, drawdown, trades, consecutive losses)
- Trade journal (history, statistics, export)
"""

import logging
from datetime import datetime, timezone
from typing import Literal, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..ict_config import Instrument, get_instrument_config
from ..ict_risk_manager import IctRiskManager, RiskStatus
from ..position_manager import PositionManager, Position
from ..trade_journal import TradeJournal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ict/dashboard", tags=["ICT Dashboard"])


# ============================================================
# PYDANTIC MODELS
# ============================================================

class CapitalMetrics(BaseModel):
    initial_capital: float
    current_capital: float
    profit_loss: float
    profit_loss_pct: float
    drawdown: float
    drawdown_pct: float


class MarketMetrics(BaseModel):
    instrument: Instrument
    current_price: float
    trend: str
    structure: dict
    liquidity: dict
    fvg: dict
    order_block: dict
    current_signal: Optional[Literal["buy", "sell", "neutral"]]
    signal_strength: float
    timeframe: str


class RiskMetrics(BaseModel):
    next_trade_risk: float
    next_trade_risk_pct: float
    daily_loss: float
    daily_loss_pct: float
    drawdown: float
    drawdown_pct: float
    trades_today: int
    consecutive_losses: int
    open_positions: int
    max_trades_remaining: int
    can_trade: bool
    blocking_reasons: list[str]


class JournalEntryAPI(BaseModel):
    trade_id: str
    date: str
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
    pnl: float
    pnl_pct: float
    r_multiple: float
    setup_score: float
    confluence_count: int
    session: str
    notes: str


class JournalStatistics(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    rejected_trades: int
    win_rate: float
    average_setup_score: float
    average_rr: float


# ============================================================
# GLOBAL INSTANCES (resolved lazily from engine module)
# ============================================================

_trade_journal: Optional[TradeJournal] = None


def _get_risk_manager():
    from .. import engine
    return getattr(engine, '_ict_risk_manager', None)


def _get_position_manager():
    from .. import engine
    return getattr(engine, '_ict_position_manager', None)


def initialize_dashboard(
    risk_manager=None,
    position_manager=None,
    trade_journal: TradeJournal | None = None,
) -> None:
    """Initialize dashboard. Risk/position managers resolved from engine."""
    global _trade_journal
    if trade_journal:
        _trade_journal = trade_journal
    logger.info("ICT Dashboard initialized")


# ============================================================
# CAPITAL ENDPOINTS
# ============================================================

@router.get("/capital", response_model=CapitalMetrics)
async def get_capital_metrics() -> CapitalMetrics:
    rm = _get_risk_manager()
    if not rm:
        raise HTTPException(status_code=503, detail="Risk Manager not initialized")

    initial_capital = rm.initial_capital
    current_capital = rm.current_equity
    profit_loss = current_capital - initial_capital
    profit_loss_pct = (profit_loss / initial_capital) * 100 if initial_capital > 0 else 0.0

    peak_equity = rm._peak_equity
    drawdown = peak_equity - current_capital
    drawdown_pct = (drawdown / peak_equity) * 100 if peak_equity > 0 else 0.0

    return CapitalMetrics(
        initial_capital=initial_capital,
        current_capital=current_capital,
        profit_loss=profit_loss,
        profit_loss_pct=profit_loss_pct,
        drawdown=drawdown,
        drawdown_pct=drawdown_pct,
    )


# ============================================================
# MARKET ENDPOINTS
# ============================================================

@router.get("/market/{instrument}", response_model=MarketMetrics)
async def get_market_metrics(instrument: Instrument, timeframe: str = "M15") -> MarketMetrics:
    cfg = get_instrument_config(instrument)

    return MarketMetrics(
        instrument=instrument,
        current_price=0.0,
        trend="neutral",
        structure={"trend": "neutral", "last_bos": None, "last_choch": None, "structure_points": []},
        liquidity={"buy_side_liquidity": [], "sell_side_liquidity": [], "recent_bull_sweep": None, "recent_bear_sweep": None},
        fvg={"bullish_fvg": None, "bearish_fvg": None},
        order_block={"bullish_ob": None, "bearish_ob": None},
        current_signal="neutral",
        signal_strength=0.0,
        timeframe=timeframe,
    )


@router.get("/market/{instrument}/realtime")
async def get_realtime_market_data(instrument: Instrument, timeframe: str = Query("M15")) -> dict:
    return {
        "instrument": instrument,
        "timeframe": timeframe,
        "current_price": 0.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "indicators": {"market_structure": {}, "liquidity_zones": {}, "order_blocks": {}, "fair_value_gaps": {}},
    }


# ============================================================
# RISK ENDPOINTS
# ============================================================

@router.get("/risk", response_model=RiskMetrics)
async def get_risk_metrics() -> RiskMetrics:
    rm = _get_risk_manager()
    if not rm:
        raise HTTPException(status_code=503, detail="Risk Manager not initialized")

    cfg = get_instrument_config("EURUSD")
    next_trade_risk = rm.current_equity * (cfg.risk_per_trade_pct / 100)

    daily_loss = rm._daily_pnl
    daily_loss_pct = (daily_loss / rm._session_start_equity) * 100 if rm._session_start_equity > 0 else 0.0

    peak_equity = rm._peak_equity
    drawdown = peak_equity - rm.current_equity
    drawdown_pct = (drawdown / peak_equity) * 100 if peak_equity > 0 else 0.0

    trades_today = rm._trades_today
    consecutive_losses = rm._consecutive_losses
    open_positions = len(rm._open_trades)

    limits = rm._limits.get("EURUSD")
    max_trades_remaining = limits.max_trades_per_session - trades_today if limits else 0

    risk_status = rm.check_all_limits("EURUSD", 0.0, 0.0, 0.0)

    return RiskMetrics(
        next_trade_risk=next_trade_risk,
        next_trade_risk_pct=cfg.risk_per_trade_pct,
        daily_loss=daily_loss,
        daily_loss_pct=daily_loss_pct,
        drawdown=drawdown,
        drawdown_pct=drawdown_pct,
        trades_today=trades_today,
        consecutive_losses=consecutive_losses,
        open_positions=open_positions,
        max_trades_remaining=max_trades_remaining,
        can_trade=risk_status.can_trade,
        blocking_reasons=risk_status.blocking_reasons,
    )


@router.get("/risk/status")
async def get_risk_status(instrument: Instrument = Query("EURUSD")) -> RiskStatus:
    rm = _get_risk_manager()
    if not rm:
        raise HTTPException(status_code=503, detail="Risk Manager not initialized")

    return rm.check_all_limits(instrument, 0.0, 0.0, 0.0)


# ============================================================
# TRADE JOURNAL ENDPOINTS
# ============================================================

@router.get("/journal", response_model=list[JournalEntryAPI])
async def get_trade_journal(
    instrument: Optional[Instrument] = Query(None),
    result: Optional[Literal["win", "loss", "breakeven", "rejected"]] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> list[JournalEntryAPI]:
    if not _trade_journal:
        raise HTTPException(status_code=503, detail="Trade Journal not initialized")

    entries = _trade_journal.get_all_entries()

    if instrument:
        entries = [e for e in entries if e.instrument == instrument]
    if result:
        entries = [e for e in entries if e.result == result]

    entries = entries[-limit:]

    return [
        JournalEntryAPI(
            trade_id=e.trade_id,
            date=e.date.isoformat(),
            instrument=e.instrument,
            direction=e.direction,
            setup_type=e.setup_type,
            timeframe=e.timeframe,
            entry_price=e.entry_price,
            sl_price=e.sl_price,
            tp_price=e.tp_price,
            risk_amount=e.risk_amount,
            risk_pct=e.risk_pct,
            result=e.result,
            rr_ratio=e.rr_ratio,
            drawdown_at_close=e.drawdown_at_close,
            pnl=e.pnl,
            pnl_pct=e.pnl_pct,
            r_multiple=e.r_multiple,
            setup_score=e.setup_score,
            confluence_count=len(e.confluence_factors),
            session=e.session,
            notes=e.notes,
        )
        for e in entries
    ]


@router.get("/journal/statistics", response_model=JournalStatistics)
async def get_journal_statistics() -> JournalStatistics:
    if not _trade_journal:
        raise HTTPException(status_code=503, detail="Trade Journal not initialized")

    stats = _trade_journal.get_statistics()

    return JournalStatistics(
        total_trades=stats["total_trades"],
        winning_trades=stats["winning_trades"],
        losing_trades=stats["losing_trades"],
        breakeven_trades=stats["breakeven_trades"],
        rejected_trades=stats["rejected_trades"],
        win_rate=stats["win_rate"],
        average_setup_score=stats["average_setup_score"],
        average_rr=stats["average_rr"],
    )


@router.get("/journal/export")
async def export_journal(
    format: Literal["csv", "json"] = Query("csv"),
    include_rejected: bool = Query(False),
) -> dict:
    if not _trade_journal:
        raise HTTPException(status_code=503, detail="Trade Journal not initialized")

    if format == "csv":
        content = _trade_journal.export_to_csv(include_rejected)
        content_type = "text/csv"
    else:
        content = _trade_journal.export_to_json(include_rejected)
        content_type = "application/json"

    filename = f"trade_journal_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.{format}"
    return {"content": content, "content_type": content_type, "filename": filename}


@router.get("/journal/cahier-format")
async def get_journal_cahier_format() -> list[str]:
    if not _trade_journal:
        raise HTTPException(status_code=503, detail="Trade Journal not initialized")
    return _trade_journal.get_cahier_format_lines()


# ============================================================
# POSITIONS ENDPOINTS
# ============================================================

@router.get("/positions")
async def get_active_positions(instrument: Optional[Instrument] = Query(None)) -> list[dict]:
    pm = _get_position_manager()
    if not pm:
        raise HTTPException(status_code=503, detail="Position Manager not initialized")

    positions = pm.get_all_positions()
    if instrument:
        positions = [p for p in positions if p.instrument == instrument]

    return [
        {
            "id": p.id, "instrument": p.instrument, "direction": p.direction,
            "entry_price": p.entry_price, "current_sl_price": p.current_sl_price,
            "current_tp_price": p.current_tp_price, "position_size_lots": p.position_size_lots,
            "unrealized_pnl": p.unrealized_pnl, "realized_pnl": p.realized_pnl,
            "rr_ratio": p.rr_ratio, "mode": p.mode, "setup_type": p.setup_type,
            "timeframe": p.timeframe, "entry_time": p.entry_time.isoformat(),
            "status": p.status.value,
        }
        for p in positions
    ]


@router.get("/positions/{position_id}")
async def get_position(position_id: str) -> dict:
    pm = _get_position_manager()
    if not pm:
        raise HTTPException(status_code=503, detail="Position Manager not initialized")

    position = pm.get_position(position_id)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    return {
        "id": position.id, "instrument": position.instrument, "direction": position.direction,
        "entry_price": position.entry_price, "initial_sl_price": position.initial_sl_price,
        "initial_tp_price": position.initial_tp_price, "current_sl_price": position.current_sl_price,
        "current_tp_price": position.current_tp_price, "position_size_lots": position.position_size_lots,
        "risk_amount": position.risk_amount, "rr_ratio": position.rr_ratio,
        "mode": position.mode, "status": position.status.value,
        "unrealized_pnl": position.unrealized_pnl, "realized_pnl": position.realized_pnl,
        "max_favorable_pnl": position.max_favorable_pnl, "max_adverse_pnl": position.max_adverse_pnl,
        "setup_type": position.setup_type, "timeframe": position.timeframe,
        "session": position.session, "entry_time": position.entry_time.isoformat(),
        "exit_time": position.exit_time.isoformat() if position.exit_time else None,
        "exit_price": position.exit_price,
        "partial_close_triggered": position.partial_close_triggered,
        "breakeven_triggered": position.breakeven_triggered,
    }


# ============================================================
# SUMMARY ENDPOINT
# ============================================================

@router.get("/summary")
async def get_dashboard_summary() -> dict:
    capital = await get_capital_metrics()
    risk = await get_risk_metrics()
    positions = await get_active_positions()

    return {
        "capital": capital.dict(),
        "risk": risk.dict(),
        "positions": positions,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
