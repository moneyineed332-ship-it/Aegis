"""ICT/SMC Backtesting Engine for Forex Trading Bot.

Implements comprehensive backtesting according to cahier des charges:
- Historical backtest with multi-instrument support
- Out-of-sample testing
- Forward testing in virtual environment
- Comprehensive statistics and analysis
- Walk-forward analysis
- Anti-over-optimization safeguards

Key Statistics (Cahier des charges §21):
- Total trades
- Win rate
- Average R-multiple
- Expectancy
- Maximum drawdown
- Profit factor
- Sharpe ratio (simplified)
- Trade distribution analysis
"""

import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Literal, Optional, Callable, get_args


def _as_datetime(value) -> datetime:
    """Best-effort candle timestamp parser (datetime, ISO string, or epoch)."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)
    if isinstance(value, (int, float)):
        ts = value / 1000 if value > 1e12 else value
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    return datetime.now(timezone.utc)
from enum import Enum
import statistics

from .ict_config import (
    Instrument, PositionMode, get_instrument_config,
    INSTRUMENT_CONFIGS
)
from .indicators import (
    market_structure, liquidity_zones, order_blocks,
    fair_value_gaps, swing_highs_lows
)
from .forex_indicators import (
    price_to_pips_forex, calculate_pip_profit, forex_atr
)
from .ict_risk_manager import IctRiskManager, TradeRecord, RiskStatus
from .position_manager import PositionManager, Position, TradeStatus, CloseReason
from .ict_signal_generator import ICTSignalGenerator, generate_ict_signal

logger = logging.getLogger(__name__)


# ============================================================
# TYPES & ENUMS
# ============================================================

class BacktestPhase(Enum):
    """Phase of backtesting process."""
    IN_SAMPLE = "in_sample"
    OUT_OF_SAMPLE = "out_of_sample"
    FORWARD_TEST = "forward_test"


class BacktestResult(Enum):
    """Result of a backtest."""
    VALID = "valid"
    INVALID_HIGH_DD = "invalid_high_drawdown"
    INVALID_NEGATIVE_EXPECTANCY = "invalid_negative_expectancy"
    INVALID_OVERFITTED = "invalid_overfitted"
    INVALID_INSTRUMENT_DEPENDENT = "invalid_instrument_dependent"
    INVALID_FEW_TRADES = "invalid_few_trades"


# ============================================================
# STATISTICS DATA CLASSES
# ============================================================

@dataclass
class TradeStatistics:
    """Comprehensive trade statistics."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    
    win_rate: float = 0.0
    loss_rate: float = 0.0
    
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    average_pnl: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    
    total_r_multiple: float = 0.0
    average_r_multiple: float = 0.0
    expectancy: float = 0.0
    
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    max_runup: float = 0.0
    
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0  # Simplified
    
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    current_consecutive_wins: int = 0
    current_consecutive_losses: int = 0
    
    best_trade: float = 0.0
    worst_trade: float = 0.0
    
    average_trade_duration_hours: float = 0.0
    longest_trade_duration_hours: float = 0.0
    shortest_trade_duration_hours: float = 0.0
    
    # Risk metrics
    average_risk_per_trade: float = 0.0
    total_risk_taken: float = 0.0
    
    # Instrument breakdown
    instrument_performance: dict[Instrument, dict] = field(default_factory=dict)
    
    # Timeframe breakdown
    timeframe_performance: dict[str, dict] = field(default_factory=dict)
    
    # Setup type breakdown
    setup_performance: dict[str, dict] = field(default_factory=dict)


@dataclass
class BacktestReport:
    """Complete backtest report."""
    phase: BacktestPhase
    instrument: Instrument
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    
    statistics: TradeStatistics
    trades: list[TradeRecord]
    
    result: BacktestResult
    validation_reason: str = ""
    
    # Equity curve data (for visualization)
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)
    
    # Parameter set used
    parameters: dict = field(default_factory=dict)


# ============================================================
# ICT/SMC BACKTESTER
# ============================================================

class IctBacktester:
    """
    ICT/SMC Backtesting Engine.
    
    Implements comprehensive backtesting with:
    - Multi-instrument support
    - Walk-forward analysis
    - Out-of-sample validation
    - Anti-over-optimization safeguards
    - Comprehensive statistics per cahier des charges
    """
    
    def __init__(
        self,
        initial_capital: float = 50.0,
        risk_manager: IctRiskManager | None = None,
        position_mode: PositionMode = "fixed_tp"
    ):
        self.initial_capital = initial_capital
        self.risk_manager = risk_manager or IctRiskManager(initial_capital)
        self.position_mode = position_mode
        self.position_manager = PositionManager(mode=position_mode, risk_manager=self.risk_manager)
        
        # Backtest data storage
        self.reports: dict[Instrument, BacktestReport] = {}
        self.trade_records: list[TradeRecord] = []
        
        # Anti-over-optimization safeguards
        self._parameter_combinations_tested = 0
        self._max_parameter_combinations = 100  # Limit search space
        
    def run_backtest(
        self,
        instrument: Instrument,
        candles: list[dict],
        start_date: datetime,
        end_date: datetime,
        phase: BacktestPhase = BacktestPhase.IN_SAMPLE,
        parameters: dict | None = None
    ) -> BacktestReport:
        """
        Run a complete backtest for an instrument.
        
        Args:
            instrument: Forex instrument
            candles: Historical OHLCV data
            start_date: Backtest start date
            end_date: Backtest end date
            phase: Backtest phase (in_sample, out_of_sample, forward_test)
            parameters: Custom parameters for testing
        
        Returns:
            BacktestReport with comprehensive statistics
        """
        logger.info(f"Starting backtest for {instrument} - Phase: {phase.value}")
        
        # Anti-over-optimization check
        self._parameter_combinations_tested += 1
        if self._parameter_combinations_tested > self._max_parameter_combinations:
            logger.warning("Parameter search space exhausted - potential over-optimization")
        
        # Reset state for new backtest
        self.risk_manager.current_equity = self.initial_capital
        self.risk_manager._daily_pnl = 0.0
        self.risk_manager._trades_today = 0
        self.risk_manager._consecutive_losses = 0
        self.position_manager.positions.clear()
        
        # Initialize tracking
        equity_curve = [(start_date, self.initial_capital)]
        backtest_trades: list[TradeRecord] = []
        
        # Process candles
        for i, candle in enumerate(candles):
            if not (start_date <= _as_datetime(candle.get("time")) <= end_date):
                continue
            
            # Update positions
            self._update_positions(candle)
            
            # Generate signals based on ICT/SMC
            signal = self._generate_ict_signal(instrument, candles[:i+1], parameters)
            
            if signal:
                # Check if position can be opened
                risk_status = self.risk_manager.check_all_limits(
                    instrument,
                    signal["entry_price"],
                    signal["sl_price"],
                    signal["tp_price"],
                    self.position_mode,
                    None,
                    signal["direction"]
                )
                
                if risk_status.can_trade:
                    # Open position
                    position_update = self.position_manager.open_position(
                        instrument=instrument,
                        direction=signal["direction"],
                        entry_price=signal["entry_price"],
                        sl_price=signal["sl_price"],
                        tp_price=signal["tp_price"],
                        account_balance=self.risk_manager.current_equity,
                        setup_type=signal.get("setup_type", ""),
                        timeframe=signal.get("timeframe", ""),
                        session=signal.get("session", "")
                    )
                    
                    if position_update.action == "open":
                        # Register with risk manager
                        self.risk_manager.register_trade_entry(
                            trade_id=position_update.position_id,
                            instrument=instrument,
                            direction=signal["direction"],
                            entry_price=signal["entry_price"],
                            sl_price=signal["sl_price"],
                            tp_price=signal["tp_price"],
                            position_size=signal.get("position_size", 0.01),
                            risk_amount=signal.get("risk_amount", 0.0),
                            risk_pct=signal.get("risk_pct", 0.0),
                            rr_ratio=signal.get("rr_ratio", 0.0),
                            session=signal.get("session", ""),
                            setup_type=signal.get("setup_type", ""),
                            mode=self.position_mode
                        )
            
            # Update equity curve
            equity_curve.append((_as_datetime(candle.get("time")), self.risk_manager.current_equity))

        # Collect closed trades (TradeRecords are mutated in place on exit).
        backtest_trades = [
            t for t in self.risk_manager._trade_history
            if t.result in ("win", "loss", "breakeven")
        ]

        # Calculate statistics
        statistics = self._calculate_statistics(backtest_trades, equity_curve)
        
        # Validate results
        result, validation_reason = self._validate_backtest(instrument, statistics)
        
        # Create report
        report = BacktestReport(
            phase=phase,
            instrument=instrument,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=self.risk_manager.current_equity,
            statistics=statistics,
            trades=backtest_trades,
            result=result,
            validation_reason=validation_reason,
            equity_curve=equity_curve,
            parameters=parameters or {}
        )
        
        self.reports[instrument] = report
        logger.info(f"Backtest completed for {instrument}: {result.value}")
        
        return report
    
    def _generate_ict_signal(
        self,
        instrument: Instrument,
        candles: list[dict],
        parameters: dict | None = None
    ) -> dict | None:
        """
        Generate ICT/SMC trading signal using the new signal generator.
        
        Uses comprehensive ICT/SMC analysis:
        - Multi-timeframe analysis (H4/H1/M15/M5)
        - Market structure (HH, HL, LH, LL, BOS, CHoCH)
        - Liquidity zones and sweeps
        - Order Blocks
        - Fair Value Gaps
        - Confluence scoring
        """
        if len(candles) < 100:
            return None
        
        # Use the new ICT signal generator
        try:
            signal_generator = ICTSignalGenerator(instrument)

            # Multi-TF: slice the same candle array to simulate different TFs.
            # In production, fetch separate candle arrays per TF from exchange.
            signal = signal_generator.generate_signal(
                candles_h4=candles[-100:],  # Context: higher TF
                candles_h1=candles[-50:],   # Structure: medium TF
                candles_m15=candles[-20:],  # Setup: lower TF
                candles_m5=candles[-5:],    # Confirmation: execution TF
                current_price=candles[-1]["close"]
            )
            
            if signal:
                return {
                    "direction": signal.direction.value,
                    "entry_price": signal.entry_price,
                    "sl_price": signal.sl_price,
                    "tp_price": signal.tp_price,
                    "rr_ratio": signal.rr_ratio,
                    "confluence_score": signal.confluence_score,
                    "setup_type": signal.setup_type,
                    "quality": signal.quality.value
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating ICT signal: {e}")
            return None
    
    def _update_positions(self, candle: dict) -> None:
        """Update all open positions with current candle data."""
        for position_id, position in list(self.position_manager.positions.items()):
            update = self.position_manager.update_position(
                position_id,
                candle["close"],
                candle["high"],
                candle["low"]
            )
            
            if update.action == "close":
                # Register exit with risk manager
                self.risk_manager.register_trade_exit(
                    position_id,
                    update.close_price,
                    candle.get("time")
                )
    
    def _calculate_statistics(
        self,
        trades: list[TradeRecord],
        equity_curve: list[tuple[datetime, float]]
    ) -> TradeStatistics:
        """Calculate comprehensive statistics per cahier des charges."""
        stats = TradeStatistics()
        
        if not trades:
            return stats
        
        stats.total_trades = len(trades)
        stats.winning_trades = sum(1 for t in trades if t.result == "win")
        stats.losing_trades = sum(1 for t in trades if t.result == "loss")
        stats.breakeven_trades = sum(1 for t in trades if t.result == "breakeven")
        
        stats.win_rate = stats.winning_trades / stats.total_trades if stats.total_trades > 0 else 0.0
        stats.loss_rate = stats.losing_trades / stats.total_trades if stats.total_trades > 0 else 0.0
        
        stats.total_pnl = sum(t.pnl for t in trades)
        stats.total_pnl_pct = (stats.total_pnl / self.initial_capital) * 100 if self.initial_capital > 0 else 0.0
        stats.average_pnl = stats.total_pnl / stats.total_trades if stats.total_trades > 0 else 0.0
        
        wins = [t.pnl for t in trades if t.result == "win"]
        losses = [t.pnl for t in trades if t.result == "loss"]
        
        stats.average_win = statistics.mean(wins) if wins else 0.0
        stats.average_loss = statistics.mean(losses) if losses else 0.0
        
        stats.total_r_multiple = sum(t.r_multiple for t in trades)
        stats.average_r_multiple = stats.total_r_multiple / stats.total_trades if stats.total_trades > 0 else 0.0
        
        # Expectancy = (WinRate * AvgWin) + (LossRate * AvgLoss)
        stats.expectancy = (stats.win_rate * stats.average_win) + (stats.loss_rate * stats.average_loss)
        
        # Drawdown calculation
        peak_equity = self.initial_capital
        max_dd = 0.0
        for _, equity in equity_curve:
            peak_equity = max(peak_equity, equity)
            dd = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0.0
            max_dd = max(max_dd, dd)
        
        stats.max_drawdown = peak_equity - min(equity for _, equity in equity_curve)
        stats.max_drawdown_pct = max_dd * 100
        
        # Runup
        min_equity = self.initial_capital
        max_runup = 0.0
        for _, equity in equity_curve:
            min_equity = min(min_equity, equity)
            runup = (equity - min_equity) / min_equity if min_equity > 0 else 0.0
            max_runup = max(max_runup, runup)
        
        stats.max_runup = max_runup * 100
        
        # Profit factor
        total_wins = sum(wins) if wins else 0.0
        total_losses = abs(sum(losses)) if losses else 0.0
        stats.profit_factor = total_wins / total_losses if total_losses > 0 else 0.0
        
        # Sharpe ratio (simplified)
        if len(equity_curve) > 1:
            returns = [(equity_curve[i][1] - equity_curve[i-1][1]) / equity_curve[i-1][1] 
                      for i in range(1, len(equity_curve)) if equity_curve[i-1][1] > 0]
            if returns:
                avg_return = statistics.mean(returns)
                std_return = statistics.stdev(returns) if len(returns) > 1 else 0.001
                stats.sharpe_ratio = (avg_return / std_return) * (252 ** 0.5) if std_return > 0 else 0.0
        
        # Consecutive wins/losses
        consecutive_wins = 0
        consecutive_losses = 0
        max_cons_wins = 0
        max_cons_losses = 0
        
        for trade in trades:
            if trade.result == "win":
                consecutive_wins += 1
                consecutive_losses = 0
                max_cons_wins = max(max_cons_wins, consecutive_wins)
            elif trade.result == "loss":
                consecutive_losses += 1
                consecutive_wins = 0
                max_cons_losses = max(max_cons_losses, consecutive_losses)
        
        stats.max_consecutive_wins = max_cons_wins
        stats.max_consecutive_losses = max_cons_losses
        
        # Best/worst trades
        stats.best_trade = max(wins) if wins else 0.0
        stats.worst_trade = min(losses) if losses else 0.0
        
        # Trade duration
        durations = []
        for trade in trades:
            if trade.exit_time and trade.entry_time:
                duration = (trade.exit_time - trade.entry_time).total_seconds() / 3600  # hours
                durations.append(duration)
        
        if durations:
            stats.average_trade_duration_hours = statistics.mean(durations)
            stats.longest_trade_duration_hours = max(durations)
            stats.shortest_trade_duration_hours = min(durations)
        
        # Risk metrics
        stats.average_risk_per_trade = statistics.mean([t.risk_amount for t in trades]) if trades else 0.0
        stats.total_risk_taken = sum(t.risk_amount for t in trades)
        
        # Instrument breakdown (Instrument is a Literal — iterate its values)
        for instrument in get_args(Instrument):
            inst_trades = [t for t in trades if t.instrument == instrument]
            if inst_trades:
                stats.instrument_performance[instrument] = {
                    "total_trades": len(inst_trades),
                    "total_pnl": sum(t.pnl for t in inst_trades),
                    "win_rate": sum(1 for t in inst_trades if t.result == "win") / len(inst_trades)
                }
        
        return stats
    
    def _validate_backtest(
        self,
        instrument: Instrument,
        statistics: TradeStatistics
    ) -> tuple[BacktestResult, str]:
        """
        Validate backtest results per cahier des charges §21.
        
        Validation criteria:
        - Coherent risk management (drawdown acceptable)
        - Acceptable drawdown
        - Positive or sufficiently promising expectancy
        - Relative stability across multiple periods
        - Performance not dependent on one instrument
        - No dependence on a few exceptional trades
        """
        cfg = get_instrument_config(instrument)
        
        # Check minimum trades
        if statistics.total_trades < 20:
            return BacktestResult.INVALID_FEW_TRADES, f"Insufficient trades: {statistics.total_trades} < 20"
        
        # Check drawdown
        if statistics.max_drawdown_pct > cfg.max_total_drawdown_pct * 100:
            return BacktestResult.INVALID_HIGH_DD, f"Drawdown too high: {statistics.max_drawdown_pct:.1f}% > {cfg.max_total_drawdown_pct * 100:.1f}%"
        
        # Check expectancy
        if statistics.expectancy < 0:
            return BacktestResult.INVALID_NEGATIVE_EXPECTANCY, f"Negative expectancy: {statistics.expectancy:.2f}"
        
        # Check instrument dependence
        if len(statistics.instrument_performance) == 1:
            return BacktestResult.INVALID_INSTRUMENT_DEPENDENT, "Performance depends on single instrument"
        
        # Check for over-optimization (too few trades, high win rate unrealistic)
        if statistics.win_rate > 0.80 and statistics.total_trades < 50:
            return BacktestResult.INVALID_OVERFITTED, f"Suspiciously high win rate ({statistics.win_rate:.1%}) with few trades"
        
        # Check for exceptional trade dependence
        if statistics.best_trade > abs(statistics.total_pnl) * 0.5:
            return BacktestResult.INVALID_OVERFITTED, "Dependence on single exceptional trade"
        
        return BacktestResult.VALID, "Backtest passes validation criteria"
    
    def run_multi_instrument_backtest(
        self,
        candles: dict[Instrument, list[dict]],
        start_date: datetime,
        end_date: datetime,
        phase: BacktestPhase = BacktestPhase.IN_SAMPLE
    ) -> dict[Instrument, BacktestReport]:
        """
        Run backtest across all instruments.
        
        Returns:
            Dictionary of backtest reports per instrument
        """
        reports = {}
        
        for instrument in candles:
            try:
                report = self.run_backtest(
                    instrument,
                    candles[instrument],
                    start_date,
                    end_date,
                    phase
                )
                reports[instrument] = report
            except Exception as e:
                logger.error(f"Backtest failed for {instrument}: {e}")
        
        return reports
    
    def generate_comparison_report(
        self,
        in_sample_reports: dict[Instrument, BacktestReport],
        out_of_sample_reports: dict[Instrument, BacktestReport] | None = None
    ) -> dict:
        """
        Generate comparison report between in-sample and out-of-sample results.
        
        Cahier des charges §21: Compare backtest versus forward results.
        """
        comparison = {
            "in_sample_summary": {},
            "out_of_sample_summary": {},
            "stability_analysis": {},
            "recommendation": ""
        }
        
        # Summarize in-sample
        total_trades_in = sum(r.statistics.total_trades for r in in_sample_reports.values())
        total_pnl_in = sum(r.statistics.total_pnl for r in in_sample_reports.values())
        avg_win_rate_in = statistics.mean([r.statistics.win_rate for r in in_sample_reports.values()]) if in_sample_reports else 0.0
        avg_dd_in = statistics.mean([r.statistics.max_drawdown_pct for r in in_sample_reports.values()]) if in_sample_reports else 0.0
        
        comparison["in_sample_summary"] = {
            "total_trades": total_trades_in,
            "total_pnl": total_pnl_in,
            "average_win_rate": avg_win_rate_in,
            "average_drawdown": avg_dd_in,
            "valid_instruments": sum(1 for r in in_sample_reports.values() if r.result == BacktestResult.VALID)
        }
        
        # Summarize out-of-sample if available
        if out_of_sample_reports:
            total_trades_out = sum(r.statistics.total_trades for r in out_of_sample_reports.values())
            total_pnl_out = sum(r.statistics.total_pnl for r in out_of_sample_reports.values())
            avg_win_rate_out = statistics.mean([r.statistics.win_rate for r in out_of_sample_reports.values()]) if out_of_sample_reports else 0.0
            avg_dd_out = statistics.mean([r.statistics.max_drawdown_pct for r in out_of_sample_reports.values()]) if out_of_sample_reports else 0.0
            
            comparison["out_of_sample_summary"] = {
                "total_trades": total_trades_out,
                "total_pnl": total_pnl_out,
                "average_win_rate": avg_win_rate_out,
                "average_drawdown": avg_dd_out,
                "valid_instruments": sum(1 for r in out_of_sample_reports.values() if r.result == BacktestResult.VALID)
            }
            
            # Stability analysis
            win_rate_diff = abs(avg_win_rate_in - avg_win_rate_out)
            dd_diff = abs(avg_dd_in - avg_dd_out)
            
            comparison["stability_analysis"] = {
                "win_rate_difference": win_rate_diff,
                "drawdown_difference": dd_diff,
                "is_stable": win_rate_diff < 0.15 and dd_diff < 5.0  # 15% win rate diff, 5% DD diff
            }
            
            # Recommendation
            if comparison["stability_analysis"]["is_stable"] and comparison["out_of_sample_summary"]["valid_instruments"] >= 2:
                comparison["recommendation"] = "APPROVED: Stable performance across in-sample and out-of-sample"
            else:
                comparison["recommendation"] = "CAUTION: Performance degradation in out-of-sample testing"
        
        return comparison


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def calculate_rr_ratio(instrument: Instrument, entry: float, sl: float, tp: float) -> float:
    """Calculate Risk/Reward ratio."""
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    return reward / risk if risk > 0 else 0.0
