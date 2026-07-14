"""Episodic memory: compare current market configurations with past episodes."""

from statistics import fmean


def _hash_features(features: dict) -> str:
    """Create a simple fingerprint from key market features."""
    sma_ratio = round(features["sma_20"] / features["sma_50"], 2)
    vol_bucket = round(features["volatility_20"] * 100) / 100  # 2 decimals
    mom_bucket = round(features["momentum_20"] * 100) / 100
    rsi_bucket = round(features["rsi_14"] / 10) * 10  # nearest 10
    return f"sma{sma_ratio}_vol{vol_bucket}_mom{mom_bucket}_rsi{rsi_bucket}"


def _similarity(a: dict, b: dict) -> float:
    """Compute similarity score between two feature sets (0 to 1)."""
    keys = ["sma_20", "sma_50", "momentum_20", "volatility_20", "rsi_14"]
    diffs = []
    for k in keys:
        va = a.get(k, 0)
        vb = b.get(k, 0)
        max_val = max(abs(va), abs(vb), 1e-8)
        diffs.append(1 - abs(va - vb) / max_val)
    return round(fmean(diffs), 4)


def remember(features: dict, episodes: list[dict], threshold: float = 0.85) -> dict:
    """Compare current features with past episodes and return similar matches.

    Each episode should have: {features, result, timestamp, strategy}.
    """
    fingerprint = _hash_features(features)
    matches = []

    for ep in episodes:
        ep_features = ep.get("features", {})
        sim = _similarity(features, ep_features)
        if sim >= threshold:
            matches.append({
                "episode_id": ep.get("id"),
                "similarity": sim,
                "result": ep.get("result"),
                "strategy": ep.get("strategy"),
                "timestamp": ep.get("timestamp"),
                "fingerprint": _hash_features(ep_features),
            })

    matches.sort(key=lambda m: m["similarity"], reverse=True)

    return {
        "current_fingerprint": fingerprint,
        "matches_found": len(matches),
        "matches": matches[:5],  # Top 5
        "confidence_boost": min(0.2, len(matches) * 0.05) if matches else 0.0,
    }


def summarize_episodes(episodes: list[dict]) -> dict:
    """Summarize memory of past episodes for the dashboard."""
    if not episodes:
        return {"total_episodes": 0, "strategies_used": [], "avg_result": None, "best_fingerprint": None}

    strategies = {}
    results = []
    for ep in episodes:
        strat = ep.get("strategy", "unknown")
        result = ep.get("result") or {}
        if strat not in strategies:
            strategies[strat] = {"count": 0, "wins": 0}
        strategies[strat]["count"] += 1
        if result.get("total_return", 0) > 0:
            strategies[strat]["wins"] += 1
        results.append(result.get("total_return", 0))

    best_strat = max(strategies.items(), key=lambda x: x[1]["wins"] / max(x[1]["count"], 1)) if strategies else None

    return {
        "total_episodes": len(episodes),
        "strategies_used": [
            {"strategy": s, "count": v["count"], "win_rate": round(v["wins"] / max(v["count"], 1), 4)}
            for s, v in strategies.items()
        ],
        "avg_result": round(fmean(results), 6) if results else None,
        "best_fingerprint": best_strat[0] if best_strat else None,
    }
