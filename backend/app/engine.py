"""AEGIS Autonomous Trading Engine.

Runs the complete trading loop:
  1. Fetch market data (prices, OHLCV)
  2. Compute features + classify regime
  3. Generate signals via advisor + consensus
  4. Execute orders (paper or live)
  5. Monitor trailing stops + circuit breaker
  6. Log every decision

All tasks are scheduled via the Scheduler and run as asyncio tasks.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone

from . import (
    backtesting, config, data_quality, execution, features, advisor, journal,
    learning, market_data, memory, ml_regime, oms, position_monitor, regime, risk, storage, telegram
)
from .ict_config import MTF_HIERARCHY, REQUIRED_TIMEFRAMES, TIMEFRAME_MAPPING, Instrument, get_instrument_config
from .alerts import manager as alert_manager
from .scheduler import scheduler
from . import smc_ict, multi_timeframe
from .indicators import multi_timeframe_confluence, multi_scale_crossover

# ICT/SMC pipeline (Cahier des charges)
_ict_signal_generator = None
_ict_risk_manager = None
_ict_position_manager = None

logger = logging.getLogger(__name__)

# --- Engine state ---
_cycle_count = 0
_last_prices: dict[str, float] = {}
_last_analysis: dict | None = None
_last_signal: dict | None = None
_last_smc_analysis: dict[str, dict] = {}
_last_mtf_analysis: dict[str, dict] = {}
_last_analyses: dict[str, dict] = {}

# --- ICT/SMC state ---
_last_ict_signals: dict[str, dict] = {}  # instrument → signal dict
_last_ict_candles: dict[str, dict[str, list]] = {}  # instrument → {tf: candles}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# State Persistence
# ============================================================

_STATE_KEYS = ("last_prices", "last_signal", "last_analyses", "last_smc_analysis", "last_mtf_analysis", "cycle_count")


def _save_state() -> None:
    """Persist engine state to DB for recovery after restart."""
    try:
        storage.set_engine_state("last_prices", json.dumps(_last_prices))
        storage.set_engine_state("last_signal", json.dumps(_last_signal) if _last_signal else "")
        storage.set_engine_state("last_analyses", json.dumps(_last_analyses))
        storage.set_engine_state("last_smc_analysis", json.dumps(_last_smc_analysis))
        storage.set_engine_state("last_mtf_analysis", json.dumps(_last_mtf_analysis))
        storage.set_engine_state("cycle_count", str(_cycle_count))
        storage.set_engine_state("last_ict_signals", json.dumps(_last_ict_signals))
    except Exception as exc:
        logger.warning("Failed to save engine state: %s", exc)


# ============================================================
# ICT/SMC Pipeline Initialization
# ============================================================

def _init_ict_pipeline() -> None:
    """Initialize the ICT/SMC pipeline modules (lazy, on first use)."""
    global _ict_signal_generator, _ict_risk_manager, _ict_position_manager
    if not config.ICT_MODE:
        return
    try:
        from .ict_signal_generator import ICTSignalGenerator
        from .ict_risk_manager import IctRiskManager
        from .position_manager import PositionManager

        if _ict_risk_manager is None:
            _ict_risk_manager = IctRiskManager(initial_capital=config.ICT_PAPER_CAPITAL)
            logger.info("ICT Risk Manager initialized (capital=%.0f€)", config.ICT_PAPER_CAPITAL)
        if _ict_position_manager is None:
            _ict_position_manager = PositionManager(risk_manager=_ict_risk_manager)
            logger.info("ICT Position Manager initialized")
    except Exception as exc:
        logger.error("Failed to initialize ICT pipeline: %s", exc)


def _get_ict_signal(instrument: Instrument, current_price: float):
    """Generate an ICT/SMC signal for one instrument using multi-TF candles."""
    from .ict_signal_generator import ICTSignalGenerator

    tf_map = {"H4": "4h", "H1": "1h", "M15": "15m", "M5": "5m"}
    candles_by_tf: dict[str, list] = {}

    for tf_name, interval in tf_map.items():
        raw = market_data.fetch_ohlcv(instrument, interval, limit=200)
        if raw and len(raw) >= 50:
            candles_by_tf[tf_name] = raw
            storage.save_ohlcv_candles(raw)

    if len(candles_by_tf) < 4:
        return None

    gen = ICTSignalGenerator(instrument)
    return gen.generate_signal(
        candles_h4=candles_by_tf.get("H4", []),
        candles_h1=candles_by_tf.get("H1", []),
        candles_m15=candles_by_tf.get("M15", []),
        candles_m5=candles_by_tf.get("M5", []),
        current_price=current_price,
    )


# ============================================================
# TASK 1: Fetch prices (every 60s)
# ============================================================

async def task_fetch_prices():
    """Fetch spot prices for all configured symbols."""
    global _last_prices
    try:
        snapshots = market_data.fetch_spot_prices()
        storage.save_market_snapshots(snapshots)
        _last_prices = {s["symbol"]: s["price"] for s in snapshots}
        storage.log_engine_event(_get_cycle_id(), "prices_fetched", {"count": len(snapshots)})
        _save_state()
    except Exception as exc:
        storage.log_engine_event(_get_cycle_id(), "prices_error", {"error": str(exc)}, "error")
        raise


# ============================================================
# TASK 2: Fetch OHLCV + features (every 5min)
# ============================================================

async def task_fetch_analysis():
    """Fetch OHLCV for all symbols, compute features, regime, and SMC/ICT analysis with multi-TF hierarchy."""
    global _last_analysis, _last_smc_analysis, _last_mtf_analysis, _last_analyses
    # FOCUSED_MODE takes priority; then ICT symbols; then default symbols
    if config.FOCUSED_MODE:
        symbols = config.FOCUSED_SYMBOLS
    elif hasattr(config, 'ICT_SYMBOLS'):
        symbols = config.ICT_SYMBOLS
    else:
        symbols = config.SYMBOLS
    
    for symbol in symbols:
        try:
            # Multi-timeframe analysis according to ICT/SMC hierarchy
            mtf_candles = {}
            smc_result = {"symbol": symbol, "score": 0, "signal": "neutral"}
            candles_h1 = None
            feats = None
            regime_result = None
            
            for category, timeframes in MTF_HIERARCHY.items():
                for tf in timeframes:
                    # Convert MT5 format to standard format if needed
                    interval = TIMEFRAME_MAPPING.get(tf, tf.lower())
                    candles = market_data.fetch_ohlcv(symbol, interval, limit=200)
                    if not candles:
                        continue
                    
                    storage.save_ohlcv_candles(candles)
                    quality = data_quality.validate_ohlcv(candles, interval)
                    if not quality["valid"]:
                        storage.log_engine_event(_get_cycle_id(), "data_quality_failed", {"symbol": symbol, "timeframe": tf, "quality": quality}, "warning")
                        continue

                    if len(candles) >= 50:
                        feats = features.latest_features(candles)
                        regime_result = regime.classify(feats)
                        _last_analysis = {"symbol": symbol, "timeframe": tf, "category": category, "features": feats, "regime": regime_result}
                        _last_analyses[f"{symbol}_{tf}"] = _last_analysis
                        
                        # Store H1 candles for SMC analysis
                        if tf == "H1":
                            candles_h1 = candles
                        mtf_candles[interval] = candles

            # After collecting all timeframes, run alerts and analysis
            if feats and regime_result:
                # Real-time alerts: run checks on fresh data and broadcast to
                # WebSocket clients whenever a threshold is triggered.
                positions = [p for p in storage.list_positions() if p["symbol"] == symbol]
                try:
                    await alert_manager.check_and_broadcast(
                        symbol=symbol,
                        features=feats,
                        regime_data=regime_result,
                        positions=positions,
                        capital=config.ICT_PAPER_CAPITAL,
                    )
                except Exception as exc:
                    storage.log_engine_event(_get_cycle_id(), "alerts_error", {"symbol": symbol, "error": str(exc)}, "error")

                # Focused mode: only the Donchian strategy runs. SMC/MTF/MSC
                # overlays are skipped to save resources and keep ONE trade type.
                if config.FOCUSED_MODE:
                    smc_result = {"symbol": symbol, "score": 0, "signal": "neutral"}
                    _last_smc_analysis[symbol] = smc_result
                    _last_mtf_analysis[symbol] = {}
                    storage.log_engine_event(_get_cycle_id(), "analysis_complete", {
                        "symbol": symbol,
                        "regime": regime_result["regime"],
                        "confidence": regime_result["confidence"],
                        "smc_score": 0,
                        "mtf_trend": "neutral",
                        "mtf_score": 0,
                    })
                    continue

                # SMC/ICT analysis on context timeframe (H1)
                if candles_h1 and len(candles_h1) >= 50:
                    smc_result = smc_ict.analyze(candles_h1)
                    _last_smc_analysis[symbol] = smc_result

                # Multi-timeframe analysis using ICT/SMC hierarchy
                if mtf_candles:
                    mtf_result = multi_timeframe.analyze_multi_timeframe(mtf_candles)
                    _last_mtf_analysis[symbol] = mtf_result

                # Multi-scale crossover (using H1 if available)
                if candles_h1 and len(candles_h1) >= 50:
                    msc_result = multi_scale_crossover(candles_h1)
                else:
                    msc_result = {"signal": "neutral", "score": 0}

                storage.log_engine_event(_get_cycle_id(), "analysis_complete", {
                    "symbol": symbol,
                    "regime": regime_result["regime"],
                    "confidence": regime_result["confidence"],
                    "smc_score": smc_result.get("score", 0),
                    "smc_trend": smc_result.get("market_structure", "neutral"),
                    "mtf_trend": mtf_result.get("overall_trend", "neutral") if 'mtf_result' in locals() else "neutral",
                    "mtf_score": mtf_result.get("confluence_score", 0) if 'mtf_result' in locals() else 0,
                    "msc_signal": msc_result.get("signal", "neutral"),
                })
        except Exception as exc:
            storage.log_engine_event(_get_cycle_id(), "analysis_error", {"symbol": symbol, "error": str(exc)}, "error")
            raise
    _save_state()


# ============================================================
# ICT/SMC Pipeline
# ============================================================

async def _run_ict_pipeline() -> None:
    """Run the full ICT/SMC pipeline: fetch multi-TF → signal → risk → execute.

    Cahier des charges §19: Market Data → Analyse Multi-TF → ICT/SMC Engine →
    Signal Generator → Risk Manager → Trade Simulator → Trade Journal.
    """
    global _last_signal, _last_ict_signals
    from .ict_config import INSTRUMENT_CONFIGS

    instruments: list[Instrument] = list(INSTRUMENT_CONFIGS.keys())
    _last_ict_signals.clear()

    for instrument in instruments:
        price = _last_prices.get(instrument)
        if not price:
            continue

        try:
            signal = _get_ict_signal(instrument, price)
            if signal is None:
                storage.log_engine_event(_get_cycle_id(), "ict_no_signal", {
                    "instrument": instrument,
                })
                continue

            # Convert ICTSignal to engine-compatible dict
            direction = signal.direction.value  # "buy" or "sell"
            sig_dict = {
                "instrument": instrument,
                "direction": direction,
                "entry_price": signal.entry_price,
                "sl_price": signal.sl_price,
                "tp_price": signal.tp_price,
                "rr_ratio": signal.rr_ratio,
                "confluence_score": signal.confluence_score,
                "quality": signal.quality.value,
                "setup_type": signal.setup_type,
                "session": signal.session,
                "trend_context": signal.trend_context,
            }
            _last_ict_signals[instrument] = sig_dict

            # --- RISK MANAGER GATE (Cahier des charges §18) ---
            # Aucun module ne peut contourner le Risk Manager.
            if _ict_risk_manager is None:
                continue
            risk_status = _ict_risk_manager.check_all_limits(
                instrument=instrument,
                entry_price=signal.entry_price,
                sl_price=signal.sl_price,
                tp_price=signal.tp_price,
                direction=direction,
            )
            if not risk_status.can_trade:
                storage.log_engine_event(_get_cycle_id(), "ict_trade_refused", {
                    "instrument": instrument,
                    "direction": direction,
                    "reasons": risk_status.blocking_reasons,
                }, "warning")
                continue

            # Calculate position size (with volatility reduction for XAU/USD)
            position_size = _ict_risk_manager.calculate_position_size(
                instrument, signal.entry_price, signal.sl_price,
                volatility_reduction=risk_status.volatility_reduction,
            )

            # Build engine-compatible signal
            _last_signal = {
                "symbol": instrument,
                "regime": {"regime": signal.trend_context, "confidence": signal.confluence_score / 10},
                "recommendation": {
                    "action": direction,
                    "strategy": "ict_smc",
                    "confidence": signal.confluence_score / 10,
                    "reason": f"ICT/SMC {signal.setup_type} | RR {signal.rr_ratio:.1f} | {signal.quality.value} | confluence {signal.confluence_score}/10",
                    "entry_price": signal.entry_price,
                    "sl_price": signal.sl_price,
                    "tp_price": signal.tp_price,
                    "rr_ratio": signal.rr_ratio,
                    "position_size": position_size,
                    "instrument": instrument,
                    "session": signal.session,
                },
                "smc_analysis": {},
                "mtf_analysis": None,
            }

            storage.log_engine_event(_get_cycle_id(), "ict_signal_generated", {
                "instrument": instrument,
                "direction": direction,
                "entry": signal.entry_price,
                "sl": signal.sl_price,
                "tp": signal.tp_price,
                "rr": signal.rr_ratio,
                "confluence": signal.confluence_score,
                "quality": signal.quality.value,
                "position_size": position_size,
            })

            # One signal per cycle — take the first valid one
            break

        except Exception as exc:
            storage.log_engine_event(_get_cycle_id(), "ict_error", {
                "instrument": instrument, "error": str(exc),
            }, "error")


# ============================================================
# TASK 3: Generate signals (every 10min)
# ============================================================

async def task_generate_signals():
    """Analyze regime + risk → generate trade signal via advisor + SMC/ICT.

    Evaluates ALL analyzed symbols and picks the one with the strongest SMC signal.
    When ICT_MODE is enabled, uses the full ICT/SMC pipeline (multi-TF → signal → risk).
    """
    global _last_signal, _last_ict_signals
    if not _last_smc_analysis:
        return

    # --- ICT/SMC Pipeline (Cahier des charges) ---
    if config.ICT_MODE:
        _init_ict_pipeline()
        await _run_ict_pipeline()
        return

    # --- Legacy pipeline (crypto / Donchian) ---

    try:
        positions = storage.list_positions()
        capital = config.ICT_PAPER_CAPITAL
        exposure = sum(abs(p["quantity"] * p["average_price"]) for p in positions)

        best_symbol = None
        best_recommendation = None
        best_smc_score = -1

        # Defaults when no symbol yields a candidate (fallback path below).
        recommendation = {"action": "wait", "strategy": None, "reason": "no analysis", "confidence": 0}
        smc_analysis = {}
        mtf_analysis = {}

        if config.FOCUSED_MODE:
            symbols = config.FOCUSED_SYMBOLS
        elif hasattr(config, 'ICT_SYMBOLS'):
            symbols = config.ICT_SYMBOLS
        else:
            symbols = list(_last_smc_analysis.keys())

        for symbol in symbols:
            analysis_data = _last_analyses.get(symbol, {"symbol": symbol, "regime": {"regime": "range", "confidence": 0.5}})

            # Build risk summary for advisor - use H1 as default timeframe
            h1_interval = TIMEFRAME_MAPPING.get("H1", "1h")
            candles = storage.list_ohlcv_candles(symbol, h1_interval, limit=200)
            risk_summary = {
                "capital": capital,
                "exposure": exposure,
                "conditional_value_at_risk": 0,
            }
            if len(candles) >= 50:
                rm = risk.historical_risk(candles, capital)
                risk_summary["conditional_value_at_risk"] = rm.get("conditional_value_at_risk", 0)

            # Get advisor recommendation (regime-based, Donchian in focused mode)
            recommendation = advisor.recommend(analysis_data, risk_summary)

            # Focused mode: replace the advisor "research" with a real Donchian
            # breakout signal so the bot actually trades its single strategy.
            # Only when the advisor already validated the strategy (risk gates
            # pass); hard gates (CVaR, capitulation, exposure...) return
            # strategy=None and must never be overridden.
            if (
                config.FOCUSED_MODE
                and recommendation.get("strategy")
                and recommendation["action"] in ("research", "wait")
                and len(candles) > max(config.DONCHIAN_PARAMS["breakout_period"], config.DONCHIAN_PARAMS["exit_period"])
            ):
                dc = backtesting.donchian_live_signal(
                    candles,
                    config.DONCHIAN_PARAMS["breakout_period"],
                    config.DONCHIAN_PARAMS["exit_period"],
                )
                if dc["action"] in ("buy", "sell"):
                    recommendation = {
                        "action": dc["action"],
                        "strategy": config.FOCUSED_STRATEGY,
                        "confidence": dc["confidence"],
                        "reason": f"{dc['reason']} ({recommendation['reason']})",
                        "channel_high": dc.get("channel_high"),
                        "channel_low": dc.get("channel_low"),
                    }

            # Layer SMC/ICT analysis on top
            smc_analysis = _last_smc_analysis.get(symbol, {})
            mtf_analysis = _last_mtf_analysis.get(symbol, {})

            # In focused mode the advisor output is the final word (Donchian only).
            # Multi-strategy overlays (SMC/MTF) are disabled to keep ONE trade type.
            if not config.FOCUSED_MODE and smc_analysis.get("score", 0) >= 30:
                smc_signal = smc_analysis.get("signal", "neutral")
                if smc_signal == "buy" and recommendation["action"] in ("research", "wait"):
                    recommendation["action"] = "buy"
                    recommendation["strategy"] = "smc_ict"
                    recommendation["confidence"] = smc_analysis["score"] / 100
                    recommendation["reason"] = (
                        f"SMC/ICT: {smc_analysis.get('market_structure', 'unknown')} structure, "
                        f"score {smc_analysis.get('score', 0)}/100 — "
                        + ", ".join(smc_analysis.get("reasons", [])[:3])
                    )
                    # Add entry/exit levels
                    recommendation["entry_zone"] = smc_analysis.get("entry_zone")
                    recommendation["stop_loss"] = smc_analysis.get("stop_loss")
                    recommendation["take_profit"] = smc_analysis.get("take_profit")
                elif smc_signal == "sell" and recommendation["action"] in ("research", "wait"):
                    recommendation["action"] = "sell"
                    recommendation["strategy"] = "smc_ict"
                    recommendation["confidence"] = smc_analysis["score"] / 100
                    recommendation["reason"] = (
                        f"SMC/ICT: {smc_analysis.get('market_structure', 'unknown')} structure, "
                        f"score {smc_analysis.get('score', 0)}/100 — "
                        + ", ".join(smc_analysis.get("reasons", [])[:3])
                    )
                    recommendation["entry_zone"] = smc_analysis.get("entry_zone")
                    recommendation["stop_loss"] = smc_analysis.get("stop_loss")
                    recommendation["take_profit"] = smc_analysis.get("take_profit")

            # Multi-timeframe confluence boost (multi-strategy mode only)
            if not config.FOCUSED_MODE and mtf_analysis.get("confluence_score", 0) >= 40:
                mtf_trend = mtf_analysis.get("overall_trend", "neutral")
                if mtf_trend == recommendation.get("action", "wait") or (
                    recommendation.get("action") in ("research", "wait") and mtf_trend in ("buy", "sell", "bullish", "bearish")
                ):
                    recommendation["confidence"] = min(
                        recommendation.get("confidence", 0) + 0.1, 0.95
                    )
                    recommendation["reason"] += (
                        f" | MTF confluence: {mtf_trend} "
                        f"({mtf_analysis.get('confluence_score', 0)}/100)"
                    )
                    recommendation["multi_tf_agreement"] = True

            # Track best signal across all symbols.
            # Focused mode: rank by Donchian signal confidence (buy/sell only),
            # so the strongest breakout across the 3 symbols wins the trade slot.
            # Multi-strategy mode: rank by SMC score (legacy behavior).
            if config.FOCUSED_MODE:
                rank_score = recommendation["confidence"] if recommendation["action"] in ("buy", "sell") else 0
            else:
                rank_score = smc_analysis.get("score", 0)
            if rank_score > best_smc_score:
                best_smc_score = rank_score
                best_symbol = symbol
                best_recommendation = recommendation.copy()
                best_recommendation["_symbol"] = symbol
                best_recommendation["_smc_analysis"] = smc_analysis
                best_recommendation["_mtf_analysis"] = {
                    "trend": mtf_analysis.get("overall_trend"),
                    "score": mtf_analysis.get("confluence_score"),
                } if mtf_analysis else None
                best_recommendation["_regime"] = analysis_data.get("regime", {})

        # Use the best signal found
        if best_recommendation and best_symbol:
            symbol = best_symbol
            recommendation = best_recommendation
            smc_analysis = recommendation.pop("_smc_analysis", {})
            mtf_analysis_data = recommendation.pop("_mtf_analysis", None)
            regime_data = recommendation.pop("_regime", {})

            signal = {
                "symbol": symbol,
                "regime": regime_data,
                "recommendation": recommendation,
                "smc_analysis": smc_analysis,
                "mtf_analysis": mtf_analysis_data,
            }
        else:
            # Fallback: use last analyzed symbol
            symbol = _last_analysis.get("symbol", config.SYMBOLS[0])
            signal = {
                "symbol": symbol,
                "regime": _last_analysis.get("regime", {}),
                "recommendation": recommendation,
                "smc_analysis": smc_analysis,
                "mtf_analysis": {
                    "trend": mtf_analysis.get("overall_trend"),
                    "score": mtf_analysis.get("confluence_score"),
                } if mtf_analysis else None,
            }

        _last_signal = signal

        storage.save_trade_signal(
            symbol,
            recommendation.get("strategy") or "none",
            recommendation["action"],
            signal,
        )
        storage.log_engine_event(_get_cycle_id(), "signal_generated", {
            "symbol": symbol,
            "action": recommendation["action"],
            "strategy": recommendation.get("strategy"),
            "confidence": recommendation.get("confidence"),
            "smc_score": smc_analysis.get("score", 0),
            "mtf_score": mtf_analysis.get("confluence_score", 0) if mtf_analysis else 0,
            "reason": recommendation["reason"][:200],
        })
        _save_state()
    except Exception as exc:
        storage.log_engine_event(_get_cycle_id(), "signal_error", {"error": str(exc)}, "error")
        raise


# ============================================================
# ICT/SMC Trade Execution
# ============================================================

async def _execute_ict_trade(symbol: str, recommendation: dict, price: float) -> None:
    """Execute a trade using the ICT pipeline: risk manager → position manager → OMS.

    Cahier des charges §7/§8/§9/§10/§18:
    - Risk Manager validates BEFORE execution
    - Position size calculated from risk %
    - SL based on market structure
    - TP based on available liquidity
    - Position Manager handles 4 modes (A/B/C/D) after entry
    """
    from .ict_config import Instrument, ICTBotConfig

    instrument: Instrument = recommendation.get("instrument", symbol)
    direction = recommendation["action"]
    entry_price = recommendation.get("entry_price", price)
    sl_price = recommendation.get("sl_price")
    tp_price = recommendation.get("tp_price")
    position_size = recommendation.get("position_size", 0)

    if not sl_price or not tp_price or position_size <= 0:
        storage.log_engine_event(_get_cycle_id(), "ict_skip", {
            "instrument": instrument, "reason": "invalid levels or size",
        })
        return

    # Final risk check (should already pass, but defensive)
    if _ict_risk_manager:
        risk_status = _ict_risk_manager.check_all_limits(
            instrument=instrument,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            direction=direction,
        )
        if not risk_status.can_trade:
            storage.log_engine_event(_get_cycle_id(), "ict_trade_refused_at_exec", {
                "instrument": instrument, "reasons": risk_status.blocking_reasons,
            }, "warning")
            return

    # Execute via OMS (paper mode)
    result = oms.oms.submit_market_order(
        symbol=instrument,
        side=direction,
        quantity=position_size,
        current_price=entry_price,
        strategy="ict_smc",
        reason=recommendation.get("reason", ""),
    )

    if result.get("status") in ("filled", "partial"):
        fill_price = result.get("fill_price", entry_price)

        # Register with ICT risk manager
        if _ict_risk_manager:
            risk_amount = _ict_risk_manager.current_equity * get_instrument_config(instrument).risk_per_trade_pct
            _ict_risk_manager.register_trade_entry(
                trade_id=result.get("order_id", ""),
                instrument=instrument,
                direction=direction,
                entry_price=fill_price,
                sl_price=sl_price,
                tp_price=tp_price,
                position_size=position_size,
                risk_amount=risk_amount,
                risk_pct=get_instrument_config(instrument).risk_per_trade_pct,
                rr_ratio=recommendation.get("rr_ratio", 0),
                session=recommendation.get("session", ""),
                setup_type=recommendation.get("setup_type", "ICT_SMC"),
            )

        # Register with Position Manager for post-trade management (§10)
        # Modes: fixed_tp (A), partial (B), breakeven (C), trailing_structural (D)
        if _ict_position_manager:
            _ict_position_manager.open_position(
                instrument=instrument,
                direction=direction,
                entry_price=fill_price,
                sl_price=sl_price,
                tp_price=tp_price,
                account_balance=_ict_risk_manager.current_equity if _ict_risk_manager else config.ICT_PAPER_CAPITAL,
                setup_type=recommendation.get("setup_type", "ICT_SMC"),
                timeframe="M15",
                session=recommendation.get("session", ""),
            )

        # Record in journal
        storage.save_decision(instrument, "M15", {
            "action": direction,
            "strategy": "ict_smc",
            "price": fill_price,
            "quantity": position_size,
            "sl": sl_price,
            "tp": tp_price,
            "rr": recommendation.get("rr_ratio"),
            "confluence": recommendation.get("confluence_score"),
            "reason": recommendation.get("reason"),
            "order_id": result.get("order_id"),
        })

        # Record trade outcome for learning
        order_id = result.get("order_id", "")
        if direction == "buy":
            learning.record_trade_entry(
                order_id=order_id, symbol=instrument, strategy="ict_smc",
                side="buy", entry_price=fill_price, quantity=position_size,
                regime=recommendation.get("trend_context", "unknown"),
            )
        elif direction == "sell":
            learning.record_trade_exit(order_id, fill_price, symbol=instrument)

        storage.log_engine_event(_get_cycle_id(), "ict_order_executed", {
            "instrument": instrument, "direction": direction,
            "entry": fill_price, "sl": sl_price, "tp": tp_price,
            "size": position_size, "rr": recommendation.get("rr_ratio"),
            "order_id": order_id,
        })

        # Telegram notification
        asyncio.create_task(telegram.notify_trade({
            "symbol": instrument, "side": direction,
            "fill_quantity": position_size, "fill_price": fill_price,
            "notional": fill_price * position_size, "strategy": "ict_smc",
        }))

    elif result.get("status") == "rejected":
        storage.log_engine_event(_get_cycle_id(), "ict_order_rejected", {
            "instrument": instrument, "reason": result.get("reason"),
        }, "warning")


# ============================================================
# TASK 4: Execute trades (on signal)
# ============================================================

async def task_execute_trades():
    """Execute orders based on the latest signal via OMS.

    When ICT_MODE is enabled, uses the ICT position manager with
    structure-based SL/TP and risk-validated position sizing.
    """
    if not _last_signal or not _last_prices:
        return

    recommendation = _last_signal["recommendation"]
    symbol = _last_signal["symbol"]

    # Only execute on actionable signals
    if recommendation["action"] not in ("buy", "sell", "research"):
        return

    if recommendation["action"] == "research":
        storage.log_engine_event(_get_cycle_id(), "research_only", {
            "symbol": symbol, "strategy": recommendation.get("strategy"), "reason": recommendation["reason"],
        })
        return

    if recommendation["action"] == "wait":
        return

    price = _last_prices.get(symbol)
    if not price:
        return

    # --- ICT/SMC execution path (Cahier des charges) ---
    if config.ICT_MODE and recommendation.get("strategy") == "ict_smc":
        await _execute_ict_trade(symbol, recommendation, price)
        return

    # --- Legacy execution path (crypto / Donchian) ---

    try:
        strategy = recommendation.get("strategy") or "sma_crossover_long_flat"
        capital = config.PAPER_CAPITAL
        positions = storage.list_positions()
        current_pos = next((p for p in positions if p["symbol"] == symbol), None)
        current_qty = current_pos["quantity"] if current_pos else 0

        # Calculate position size
        sizing = execution.calculate_position_size(capital, entry_price=price)
        target_qty = sizing["quantity"]

        # Determine action
        if current_qty == 0 and target_qty > 0:
            # Max positions gate (Phase 1): never exceed MAX_POSITIONS open deals
            if len(positions) >= config.MAX_POSITIONS:
                storage.log_engine_event(_get_cycle_id(), "trade_skipped", {
                    "reason": f"max_positions_reached ({config.MAX_POSITIONS} deals).",
                    "symbol": symbol,
                })
                return
            side = "buy"
            quantity = target_qty
        elif current_qty > 0 and recommendation["action"] == "sell":
            side = "sell"
            quantity = abs(current_qty)
        else:
            storage.log_engine_event(_get_cycle_id(), "trade_skipped", {"reason": "no_action_needed"})
            return

        # Execute via OMS (handles paper/live routing + validation)
        result = oms.oms.submit_market_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            current_price=price,
            strategy=strategy,
            reason=recommendation["reason"],
        )

        if result.get("status") in ("filled", "partial"):
            fill_price = result.get("fill_price", price)

            # Record in journal
            storage.save_decision(symbol, "1h", {
                "action": side,
                "strategy": strategy,
                "price": fill_price,
                "quantity": quantity,
                "regime": _last_signal["regime"]["regime"],
                "confidence": _last_signal["regime"]["confidence"],
                "reason": recommendation["reason"],
                "mode": result.get("mode", config.MODE),
                "order_id": result.get("order_id"),
            })

            # Record in risk module
            notional = fill_price * quantity
            risk.record_trade_result(notional if side == "sell" else -notional)

            # Track trade outcome for learning
            order_id = result.get("order_id", "")
            if side == "buy":
                # New position — record entry for tracking
                learning.record_trade_entry(
                    order_id=order_id,
                    symbol=symbol,
                    strategy=strategy,
                    side="buy",
                    entry_price=fill_price,
                    quantity=quantity,
                    regime=_last_signal["regime"]["regime"],
                    features=_last_analysis.get("features") if _last_analysis else None,
                )
            elif side == "sell" and current_qty > 0:
                # Closing position — record exit for learning
                # Pass symbol so fallback lookup works even when sell order_id differs
                learning.record_trade_exit(order_id, fill_price, symbol=symbol)

            storage.log_engine_event(_get_cycle_id(), "order_executed", {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": fill_price,
                "notional": notional,
                "strategy": strategy,
                "mode": result.get("mode", config.MODE),
                "order_id": order_id,
            })

            # Telegram trade notification
            asyncio.create_task(telegram.notify_trade({
                "symbol": symbol, "side": side, "fill_quantity": quantity,
                "fill_price": fill_price, "notional": notional, "strategy": strategy,
            }))
        elif result.get("status") == "rejected":
            storage.log_engine_event(_get_cycle_id(), "order_rejected", {
                "symbol": symbol,
                "side": side,
                "reason": result.get("reason", "unknown"),
            }, "warning")
    except Exception as exc:
        storage.log_engine_event(_get_cycle_id(), "execution_error", {"error": str(exc)}, "error")
        raise


# ============================================================
# TASK 5: Monitor trailing stops (every 10s)
# ============================================================

async def task_check_trailing_stops():
    """Check all active trailing stops against current prices."""
    if not _last_prices:
        return

    try:
        triggered = execution.check_trailing_stops(_last_prices)
        for t in triggered:
            # Auto-close position on stop trigger
            symbol = t["symbol"]
            positions = storage.list_positions()
            pos = next((p for p in positions if p["symbol"] == symbol), None)
            if pos and pos["quantity"] > 0:
                price = _last_prices.get(symbol)
                if price:
                    result = execution.market_order(symbol, "sell", abs(pos["quantity"]), price)
                    if result["status"] == "filled":
                        order_data = {
                            "symbol": symbol,
                            "side": "sell",
                            "quantity": abs(pos["quantity"]),
                            "reference_price": result["fill_price"],
                            "notional": result["fill_price"] * abs(pos["quantity"]),
                        }
                        storage.save_order_and_position(order_data, None)
                        execution.remove_trailing_stop(symbol, "buy")
                        storage.remove_trailing_stop_state(symbol, "buy")

                        # Record trade exit for learning
                        open_outcomes = storage.list_trade_outcomes(symbol=symbol, status="open", limit=10)
                        for outcome in open_outcomes:
                            learning.record_trade_exit(outcome["order_id"], result["fill_price"])
                            break  # Close the most recent open trade

                        storage.log_engine_event(_get_cycle_id(), "trailing_stop_triggered", {
                            "symbol": symbol,
                            "stop_price": t["stop_price"],
                            "exit_price": result["fill_price"],
                            "pnl_pct": t["unrealized_pnl_pct"],
                        }, "warning")
    except Exception as exc:
        storage.log_engine_event(_get_cycle_id(), "trailing_stop_error", {"error": str(exc)}, "error")


# ============================================================
# TASK 6: Check circuit breaker (every 30s)
# ============================================================

async def task_check_circuit_breaker():
    """Check if circuit breaker should be triggered."""
    try:
        positions = storage.list_positions()
        capital = config.PAPER_CAPITAL
        equity = capital + sum(p["quantity"] * p["average_price"] for p in positions)

        result = risk.check_circuit_breaker(capital, equity)
        if result.get("halted") and not storage.get_kill_switch():
            storage.set_kill_switch(True, f"Circuit breaker: {result.get('reason', 'daily loss limit')}")
            storage.log_engine_event(_get_cycle_id(), "circuit_breaker_triggered", result, "critical")
            asyncio.create_task(telegram.notify_circuit_breaker(result))
    except Exception as exc:
        storage.log_engine_event(_get_cycle_id(), "circuit_breaker_error", {"error": str(exc)}, "error")


# ============================================================
# TASK 6b: Position monitoring + auto-close (every 15s)
# ============================================================

async def task_monitor_positions():
    """Monitor all positions for PnL and risk breaches. Auto-close if needed."""
    if not _last_prices:
        return

    try:
        result = position_monitor.monitor_cycle(_last_prices)
        portfolio = result["portfolio"]
        alerts = result["alerts"]

        # Log portfolio summary periodically
        storage.log_engine_event(_get_cycle_id(), "position_update", {
            "equity": portfolio["equity"],
            "unrealized_pnl": portfolio["total_unrealized_pnl"],
            "exposure_pct": portfolio["exposure_pct"],
            "position_count": portfolio["position_count"],
        })

        # Process risk alerts
        for alert in alerts:
            severity = "critical"
            storage.log_engine_event(_get_cycle_id(), "position_risk_alert", alert, severity)

            # Telegram risk alert
            asyncio.create_task(telegram.notify_risk_alert(alert))

            # Auto-close individual positions
            if alert.get("action") == "auto_close":
                symbol = alert["symbol"]
                positions = storage.list_positions()
                pos = next((p for p in positions if p["symbol"] == symbol), None)
                if pos and pos["quantity"] > 0:
                    price = _last_prices.get(symbol)
                    if price:
                        result = oms.oms.submit_market_order(
                            symbol=symbol,
                            side="sell",
                            quantity=abs(pos["quantity"]),
                            current_price=price,
                            strategy="risk_auto_close",
                            reason=alert["message"],
                        )
                        if result.get("status") in ("filled", "partial"):
                            # Record trade exit for learning
                            open_outcomes = storage.list_trade_outcomes(symbol=symbol, status="open", limit=10)
                            for outcome in open_outcomes:
                                learning.record_trade_exit(outcome["order_id"], price)
                                break

                            storage.log_engine_event(_get_cycle_id(), "auto_close_executed", {
                                "symbol": symbol,
                                "quantity": abs(pos["quantity"]),
                                "reason": alert["message"],
                                "order_id": result.get("order_id"),
                            })

            # Close all positions on portfolio drawdown breach
            elif alert.get("action") == "close_all":
                positions = storage.list_positions()
                for pos in positions:
                    if pos["quantity"] > 0:
                        price = _last_prices.get(pos["symbol"])
                        if price:
                            result = oms.oms.submit_market_order(
                                symbol=pos["symbol"],
                                side="sell",
                                quantity=abs(pos["quantity"]),
                                current_price=price,
                                strategy="portfolio_risk_close",
                                reason=alert["message"],
                            )
                            if result.get("status") in ("filled", "partial"):
                                # Record trade exit for learning
                                open_outcomes = storage.list_trade_outcomes(symbol=pos["symbol"], status="open", limit=10)
                                for outcome in open_outcomes:
                                    learning.record_trade_exit(outcome["order_id"], price)
                                    break

                                storage.log_engine_event(_get_cycle_id(), "portfolio_close_executed", {
                                    "symbol": pos["symbol"],
                                    "quantity": abs(pos["quantity"]),
                                    "order_id": result.get("order_id"),
                                })

                # Activate kill switch after closing all
                storage.set_kill_switch(True, f"Portfolio drawdown: {alert['message']}")
                storage.log_engine_event(_get_cycle_id(), "kill_switch_activated", {
                    "reason": alert["message"],
                }, "critical")
                asyncio.create_task(telegram.notify_circuit_breaker({
                    "halted": True, "reason": alert["message"],
                    "halted_at": datetime.now(timezone.utc).isoformat(),
                }))

        # --- ICT Position Manager monitoring (§10) ---
        # Updates SL/TP according to selected mode: fixed_tp, partial, breakeven, trailing
        if config.ICT_MODE and _ict_position_manager and _last_prices:
            for pos in _ict_position_manager.get_all_positions():
                price = _last_prices.get(pos.instrument)
                if price:
                    update = _ict_position_manager.update_position(
                        pos.id, price, current_high=price, current_low=price,
                    )
                    if update.action in ("close", "partial_close"):
                        # Close position via OMS
                        close_result = oms.oms.submit_market_order(
                            symbol=pos.instrument,
                            side="sell" if pos.direction == "buy" else "buy",
                            quantity=pos.position_size_lots,
                            current_price=price,
                            strategy="ict_position_manager",
                            reason=update.message,
                        )
                        if close_result.get("status") in ("filled", "partial"):
                            if _ict_risk_manager:
                                _ict_risk_manager.register_trade_exit(
                                    pos.journal_entry_id, price,
                                )
                            storage.log_engine_event(_get_cycle_id(), "ict_position_closed", {
                                "instrument": pos.instrument,
                                "reason": update.reason.value if update.reason else "unknown",
                                "pnl": update.pnl,
                            })
                    elif update.action == "modify":
                        storage.log_engine_event(_get_cycle_id(), "ict_sl_modified", {
                            "instrument": pos.instrument,
                            "new_sl": update.new_sl,
                            "reason": update.reason.value if update.reason else "",
                        })

    except Exception as exc:
        storage.log_engine_event(_get_cycle_id(), "position_monitor_error", {"error": str(exc)}, "error")


# ============================================================
# TASK 7: Memory + Journal (every 1h)
# ============================================================

async def task_learning():
    """Run the full learning cycle: analyze outcomes, score strategies, consolidate memory."""
    try:
        result = learning.learning_cycle(_last_analysis, _last_signal)

        storage.log_engine_event(_get_cycle_id(), "learning_complete", {
            "strategies_scored": result.get("strategies_scored", 0),
            "patterns_found": result.get("patterns_found", 0),
            "advisor_weights_updated": result.get("advisor_weights_updated", False),
        })

        # Send daily summary at end of day (UTC)
        now = datetime.now(timezone.utc)
        if now.hour == 23:
            try:
                from .daily_report import generate_daily_report
                report = generate_daily_report(now.strftime("%Y-%m-%d"))
                asyncio.create_task(telegram.notify_daily_summary({
                    "equity": report["portfolio"]["equity"],
                    "daily_pnl": report["trades"]["total_pnl"],
                    "daily_pnl_pct": (report["trades"]["total_pnl"] / config.PAPER_CAPITAL * 100) if config.PAPER_CAPITAL > 0 else 0,
                    "trades_count": report["trades"]["total"],
                    "win_rate": report["trades"]["win_rate"],
                }))
            except Exception as report_exc:
                logger.debug("Daily summary Telegram failed: %s", report_exc)
    except Exception as exc:
        storage.log_engine_event(_get_cycle_id(), "learning_error", {"error": str(exc)}, "error")


# ============================================================
# Utility
# ============================================================

def _get_cycle_id() -> str:
    """Generate a short cycle ID for log grouping."""
    global _cycle_count
    _cycle_count += 1
    return f"c{_cycle_count}"


def _restore_state() -> None:
    """Restore persistent in-memory state from DB on engine startup."""
    global _last_prices, _last_signal, _last_analyses, _last_smc_analysis, _last_mtf_analysis, _cycle_count

    # Restore engine state (prices, signal, analyses)
    try:
        raw = storage.get_engine_state("last_prices")
        if raw:
            _last_prices = json.loads(raw)
            logger.info("Restored last_prices for %d symbol(s)", len(_last_prices))

        raw = storage.get_engine_state("last_signal")
        if raw:
            _last_signal = json.loads(raw)
            logger.info("Restored last_signal: %s %s", _last_signal.get("symbol"), _last_signal.get("recommendation", {}).get("action"))

        raw = storage.get_engine_state("last_analyses")
        if raw:
            _last_analyses = json.loads(raw)
            logger.info("Restored last_analyses for %d entries", len(_last_analyses))

        raw = storage.get_engine_state("last_smc_analysis")
        if raw:
            _last_smc_analysis = json.loads(raw)

        raw = storage.get_engine_state("last_mtf_analysis")
        if raw:
            _last_mtf_analysis = json.loads(raw)

        raw = storage.get_engine_state("cycle_count")
        if raw:
            _cycle_count = int(raw)

        raw = storage.get_engine_state("last_ict_signals")
        if raw:
            _last_ict_signals = json.loads(raw)
    except Exception as exc:
        logger.warning("Failed to restore engine state: %s", exc)

    # Restore trailing stops
    try:
        active_stops = storage.list_active_trailing_stops()
        for stop in active_stops:
            execution.restore_trailing_stop(
                stop["symbol"], stop["side"],
                stop["entry_price"], stop["trail_pct"],
                stop["highest_price"], stop["lowest_price"],
                stop["stop_price"],
            )
        if active_stops:
            logger.info("Restored %d trailing stop(s) from DB", len(active_stops))
    except Exception as exc:
        logger.warning("Failed to restore trailing stops: %s", exc)

    # Restore circuit breaker
    try:
        risk.restore_circuit_breaker()
        logger.info("Circuit breaker state restored from DB")
    except Exception as exc:
        logger.warning("Failed to restore circuit breaker: %s", exc)

    # Restore ML model
    try:
        restored = ml_regime.predictor.load_model()
        if restored:
            logger.info("ML regime model restored from DB")
    except Exception as exc:
        logger.warning("Failed to restore ML model: %s", exc)


# ============================================================
# Engine Control
# ============================================================

def register_tasks() -> None:
    """Register all engine tasks with the scheduler."""
    scheduler.register("fetch_prices", task_fetch_prices, config.ENGINE_INTERVAL_PRICES)
    scheduler.register("fetch_analysis", task_fetch_analysis, config.ENGINE_INTERVAL_ANALYSIS)
    scheduler.register("generate_signals", task_generate_signals, config.ENGINE_INTERVAL_SIGNALS)
    scheduler.register("execute_trades", task_execute_trades, config.ENGINE_INTERVAL_SIGNALS)
    scheduler.register("check_trailing_stops", task_check_trailing_stops, config.ENGINE_INTERVAL_TRAILING_STOPS)
    scheduler.register("check_circuit_breaker", task_check_circuit_breaker, 30)
    scheduler.register("monitor_positions", task_monitor_positions, config.ENGINE_INTERVAL_POSITIONS)
    scheduler.register("learning", task_learning, config.ENGINE_INTERVAL_OPTIMIZE)


async def start_engine() -> dict:
    """Start the autonomous trading engine."""
    register_tasks()
    _restore_state()
    await scheduler.start()
    storage.set_engine_state("status", "running")
    storage.set_engine_state("started_at", _now_iso())
    storage.log_engine_event(_get_cycle_id(), "engine_started")
    logger.info("AEGIS Engine started")
    return {"status": "running", "started_at": _now_iso()}


async def stop_engine() -> dict:
    """Stop the autonomous trading engine."""
    await scheduler.stop()
    storage.set_engine_state("status", "stopped")
    storage.set_engine_state("stopped_at", _now_iso())
    storage.log_engine_event(_get_cycle_id(), "engine_stopped")
    logger.info("AEGIS Engine stopped")
    return {"status": "stopped", "stopped_at": _now_iso()}


def get_engine_status() -> dict:
    """Get comprehensive engine status."""
    status = storage.get_engine_state("status") or "stopped"
    started_at = storage.get_engine_state("started_at")
    stats = storage.get_engine_stats()
    scheduler_status = scheduler.get_status()

    return {
        "status": status,
        "mode": config.MODE,
        "ict_mode": config.ICT_MODE,
        "focused_mode": config.FOCUSED_MODE,
        "started_at": started_at,
        "cycle_count": _cycle_count,
        "symbols": config.SYMBOLS,
        "last_prices": _last_prices,
        "last_analysis": {
            "symbol": _last_analysis["symbol"],
            "regime": _last_analysis["regime"]["regime"],
            "confidence": _last_analysis["regime"]["confidence"],
        } if _last_analysis else None,
        "last_signal": {
            "symbol": _last_signal["symbol"],
            "action": _last_signal["recommendation"]["action"],
            "strategy": _last_signal["recommendation"].get("strategy"),
        } if _last_signal else None,
        "ict_signals": _last_ict_signals if _last_ict_signals else None,
        "oms": oms.oms.get_status(),
        "stats": stats,
        "scheduler": scheduler_status,
        "intervals": {
            "prices": config.ENGINE_INTERVAL_PRICES,
            "analysis": config.ENGINE_INTERVAL_ANALYSIS,
            "signals": config.ENGINE_INTERVAL_SIGNALS,
            "trailing_stops": config.ENGINE_INTERVAL_TRAILING_STOPS,
            "positions": config.ENGINE_INTERVAL_POSITIONS,
            "optimize": config.ENGINE_INTERVAL_OPTIMIZE,
        },
    }
