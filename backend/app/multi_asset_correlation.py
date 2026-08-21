"""Multi-Asset Correlation — dynamic position sizing based on cross-asset correlations."""

import logging
from statistics import fmean, stdev

from . import risk, storage

logger = logging.getLogger(__name__)

# Max correlation threshold: if two assets are highly correlated, reduce sizing
HIGH_CORRELATION_THRESHOLD = 0.7
MODERATE_CORRELATION_THRESHOLD = 0.4

# Sizing adjustments
REDUCTION_HIGH_CORR = 0.5  # 50% size reduction for highly correlated assets
REDUCTION_MODERATE_CORR = 0.75  # 25% size reduction for moderately correlated


def compute_cross_asset_correlation(symbols: list[str]) -> dict:
    """Compute correlation matrix across multiple crypto assets.

    Returns:
        {"symbols": [...], "matrix": {pair: corr}, "avg_correlation": float, "interpretation": str}
    """
    if len(symbols) < 2:
        return {"symbols": symbols, "matrix": {}, "avg_correlation": None, "interpretation": "insufficient_assets"}

    # Fetch OHLCV close prices for each symbol
    assets: dict[str, list[float]] = {}
    for symbol in symbols:
        candles = storage.list_ohlcv_candles(symbol=symbol, interval="1h", limit=30)
        if candles:
            prices = [c["close"] for c in candles if c.get("close")]
            if len(prices) >= 10:
                assets[symbol] = prices

    if len(assets) < 2:
        return {"symbols": symbols, "matrix": {}, "avg_correlation": None, "interpretation": "insufficient_data"}

    return risk.correlation_matrix(assets)


def compute_dynamic_allocation(
    target_symbol: str,
    all_symbols: list[str],
    base_allocation: float,
) -> dict:
    """Adjust position allocation based on cross-asset correlations.

    If target asset is highly correlated with existing positions, reduce allocation.

    Args:
        target_symbol: The asset we want to trade
        all_symbols: All assets currently in the portfolio (or being considered)
        base_allocation: Original allocation percentage (e.g., 0.3)

    Returns:
        {"adjusted_allocation": float, "correlation_factor": float, "reason": str}
    """
    if target_symbol not in all_symbols or len(all_symbols) < 2:
        return {
            "adjusted_allocation": base_allocation,
            "correlation_factor": 1.0,
            "reason": "no_correlation_data",
        }

    corr_result = compute_cross_asset_correlation(all_symbols)
    avg_corr = corr_result.get("avg_correlation")

    if avg_corr is None:
        return {
            "adjusted_allocation": base_allocation,
            "correlation_factor": 1.0,
            "reason": "insufficient_data",
        }

    # Calculate adjustment factor
    if avg_corr >= HIGH_CORRELATION_THRESHOLD:
        factor = REDUCTION_HIGH_CORR
        reason = f"high_avg_correlation_{avg_corr:.2f}"
    elif avg_corr >= MODERATE_CORRELATION_THRESHOLD:
        factor = REDUCTION_MODERATE_CORR
        reason = f"moderate_avg_correlation_{avg_corr:.2f}"
    else:
        factor = 1.0
        reason = f"low_avg_correlation_{avg_corr:.2f}"

    adjusted = round(base_allocation * factor, 4)

    return {
        "adjusted_allocation": adjusted,
        "correlation_factor": factor,
        "avg_correlation": avg_corr,
        "reason": reason,
    }


def compute_portfolio_correlation_risk(symbols: list[str]) -> dict:
    """Analyze correlation risk across the portfolio.

    Returns comprehensive correlation analysis including:
    - Average correlation
    - Max pairwise correlation
    - Diversification score
    - Recommended allocation adjustments
    """
    corr_result = compute_cross_asset_correlation(symbols)

    avg_corr = corr_result.get("avg_correlation")
    matrix = corr_result.get("matrix", {})

    # Find max pairwise correlation
    max_corr = 0.0
    max_pair = None
    for pair, corr in matrix.items():
        if corr is not None and abs(corr) > abs(max_corr):
            max_corr = corr
            max_pair = pair

    # Diversification score (0-100): higher is better
    if avg_corr is None:
        div_score = 50  # Neutral when no data
    elif avg_corr <= 0:
        div_score = 100
    elif avg_corr >= 1.0:
        div_score = 0
    else:
        div_score = round((1 - avg_corr) * 100)

    # Sizing recommendations
    recommendations = {}
    for symbol in symbols:
        adj = compute_dynamic_allocation(symbol, symbols, base_allocation=0.3)
        recommendations[symbol] = adj

    return {
        "symbols": symbols,
        "avg_correlation": avg_corr,
        "max_correlation": round(max_corr, 4) if max_corr else None,
        "max_pair": max_pair,
        "diversification_score": div_score,
        "interpretation": corr_result.get("interpretation", "unknown"),
        "recommendations": recommendations,
    }
