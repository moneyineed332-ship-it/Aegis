"""API integration tests for all AEGIS endpoints."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import storage
storage.initialize()

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# === Health ===

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "kill_switch_active" in data


# === Dashboard ===

def test_dashboard():
    r = client.get("/api/v1/dashboard")
    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == "paper"
    assert "capital" in data
    assert "positions" in data
    assert "recent_backtests" in data
    assert "data_quality" in data
    assert "strategy_registry" in data
    assert "fear_greed" in data
    assert "funding_rates" in data
    assert "open_interest" in data
    assert "memory" in data
    assert "journal" in data
    assert "stress_test" in data
    assert "correlation" in data
    assert "concentration" in data


# === Paper Orders ===

def test_create_paper_order():
    r = client.post("/api/v1/paper-orders", json={
        "symbol": "BTC/USDT",
        "side": "buy",
        "quantity": 0.001,
        "reference_price": 50000,
    })
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "filled_simulated"


def test_paper_order_exceeds_limit():
    r = client.post("/api/v1/paper-orders", json={
        "symbol": "BTC/USDT",
        "side": "buy",
        "quantity": 10,
        "reference_price": 50000,
    })
    assert r.status_code == 422


# === Market Snapshots ===

def test_market_snapshots():
    r = client.get("/api/v1/market-snapshots")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_refresh_market_snapshots():
    r = client.post("/api/v1/market-snapshots/refresh")
    assert r.status_code == 201
    data = r.json()
    assert isinstance(data, list)


# === OHLCV ===

def test_ohlcv():
    r = client.get("/api/v1/ohlcv")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_refresh_ohlcv():
    r = client.post("/api/v1/ohlcv/refresh", params={"symbol": "BTCUSDT", "interval": "1h", "limit": 100})
    assert r.status_code == 201
    data = r.json()
    assert "stored" in data


# === Data Quality ===

def test_data_quality():
    r = client.get("/api/v1/data-quality/ohlcv")
    assert r.status_code == 200
    data = r.json()
    assert "valid" in data
    assert "candle_count" in data


# === Risk ===

def test_risk_summary():
    r = client.get("/api/v1/risk/summary")
    assert r.status_code in (200, 422)


def test_risk_stress_test():
    r = client.get("/api/v1/risk/stress-test")
    assert r.status_code in (200, 422)


def test_risk_correlation():
    r = client.get("/api/v1/risk/correlation")
    assert r.status_code in (200, 422)


def test_risk_concentration():
    r = client.get("/api/v1/risk/concentration")
    assert r.status_code == 200
    data = r.json()
    assert "total_exposure" in data


# === Market Analysis ===

def test_market_analysis():
    r = client.get("/api/v1/market-analysis")
    assert r.status_code in (200, 422)


# === Decisions ===

def test_recommendation():
    r = client.post("/api/v1/decisions/recommendation")
    assert r.status_code in (201, 422)


def test_decisions_list():
    r = client.get("/api/v1/decisions")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# === Strategies ===

def test_strategies():
    r = client.get("/api/v1/strategies")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 4


# === Coach ===

def test_coach_review():
    r = client.get("/api/v1/coach/review")
    assert r.status_code == 200
    data = r.json()
    assert "reviewed_backtests" in data
    assert "strategy_analysis" in data
    assert "improvement_proposals" in data


# === Lab ===

def test_lab_promotions():
    r = client.get("/api/v1/lab/promotions")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# === Supervisor ===

def test_supervisor_status():
    r = client.get("/api/v1/supervisor")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "kill_switch_active" in data


# === Fear & Greed ===

def test_fear_greed():
    r = client.get("/api/v1/fear-greed")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_refresh_fear_greed():
    r = client.post("/api/v1/fear-greed/refresh")
    assert r.status_code in (201, 502)


# === Funding Rates ===

def test_funding_rates():
    r = client.get("/api/v1/funding-rates")
    assert r.status_code == 200


def test_refresh_funding_rates():
    r = client.post("/api/v1/funding-rates/refresh")
    assert r.status_code in (201, 502)


# === Open Interest ===

def test_open_interest():
    r = client.get("/api/v1/open-interest")
    assert r.status_code == 200


def test_refresh_open_interest():
    r = client.post("/api/v1/open-interest/refresh")
    assert r.status_code in (201, 502)


# === Memory ===

def test_memory_list():
    r = client.get("/api/v1/memory")
    assert r.status_code == 200
    data = r.json()
    assert "summary" in data
    assert "episodes" in data


def test_memory_remember():
    r = client.post("/api/v1/memory/remember")
    assert r.status_code in (201, 422)


def test_memory_compare():
    r = client.get("/api/v1/memory/compare")
    assert r.status_code in (200, 422)


# === Journal ===

def test_journal_analysis():
    r = client.get("/api/v1/journal/analysis")
    assert r.status_code == 200
    data = r.json()
    assert "total_decisions" in data
    assert "feedback" in data


def test_journal_outcomes():
    r = client.get("/api/v1/journal/outcomes")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# === Backtests SMA ===

def test_sma_backtest():
    r = client.post("/api/v1/backtests/sma-crossover", json={
        "symbol": "BTCUSDT",
        "interval": "1h",
        "fast_period": 10,
        "slow_period": 30,
    })
    assert r.status_code in (201, 422)


def test_sma_walk_forward():
    r = client.post("/api/v1/backtests/sma-crossover/walk-forward")
    assert r.status_code in (201, 422)


# === Backtests Donchian ===

def test_donchian_walk_forward():
    r = client.post("/api/v1/backtests/donchian-breakout/walk-forward")
    assert r.status_code in (201, 422)


# === Backtests Mean Reversion ===

def test_mean_reversion_backtest():
    r = client.post("/api/v1/backtests/mean-reversion", json={
        "symbol": "BTCUSDT",
        "interval": "1h",
    })
    assert r.status_code in (201, 422)


def test_mean_reversion_walk_forward():
    r = client.post("/api/v1/backtests/mean-reversion/walk-forward")
    assert r.status_code in (201, 422)


# === Backtests Grid ===

def test_grid_backtest():
    r = client.post("/api/v1/backtests/grid", json={
        "symbol": "BTCUSDT",
        "interval": "1h",
    })
    assert r.status_code in (201, 422)


def test_grid_walk_forward():
    r = client.post("/api/v1/backtests/grid/walk-forward")
    assert r.status_code in (201, 422)


# === Execution ===

def test_market_order():
    client.post("/api/v1/market-snapshots/refresh")
    r = client.post("/api/v1/execution/market-order", params={
        "symbol": "BTCUSDT",
        "side": "buy",
        "quantity": 0.001,
    })
    assert r.status_code in (201, 422, 423)


def test_limit_order():
    r = client.post("/api/v1/execution/limit-order", params={
        "symbol": "BTCUSDT",
        "side": "buy",
        "quantity": 0.001,
        "limit_price": 50000,
    })
    assert r.status_code == 201


def test_fractioned_order():
    r = client.post("/api/v1/execution/fractioned-order", params={
        "symbol": "BTCUSDT",
        "side": "buy",
        "quantity": 0.01,
        "chunks": 3,
    })
    assert r.status_code in (201, 422, 423)


def test_estimate_slippage():
    r = client.post("/api/v1/execution/estimate-slippage", params={"order_value": 100})
    assert r.status_code == 200
    data = r.json()
    assert "estimated_slippage_bps" in data


# === Phase 3: Optimization ===

def test_optimize_sma():
    r = client.post("/api/v1/optimizer/sma")
    assert r.status_code in (200, 422)


def test_optimize_donchian():
    r = client.post("/api/v1/optimizer/donchian")
    assert r.status_code in (200, 422)


def test_optimize_mean_reversion():
    r = client.post("/api/v1/optimizer/mean-reversion")
    assert r.status_code in (200, 422)


def test_optimize_grid():
    r = client.post("/api/v1/optimizer/grid")
    assert r.status_code in (200, 422)


def test_compare_strategies():
    r = client.post("/api/v1/optimizer/compare")
    assert r.status_code in (200, 422)


# === Phase 4: WebSocket Alerts ===

def test_alert_history():
    r = client.get("/api/v1/alerts/history")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_alert_thresholds():
    r = client.get("/api/v1/alerts/thresholds")
    assert r.status_code == 200
    data = r.json()
    assert "max_drawdown_pct" in data


def test_check_alerts():
    r = client.post("/api/v1/alerts/check")
    assert r.status_code == 200


# === Phase 4: Advanced Backtesting ===

def test_advanced_walk_forward():
    r = client.post("/api/v1/backtests/advanced/walk-forward")
    assert r.status_code in (200, 201, 422)


def test_monte_carlo():
    r = client.post("/api/v1/backtests/advanced/monte-carlo")
    assert r.status_code in (200, 201, 422)


def test_sensitivity():
    r = client.post("/api/v1/backtests/advanced/sensitivity")
    assert r.status_code in (200, 201, 422)


# === Phase 4: ML Regime ===

def test_ml_regime_summary():
    r = client.get("/api/v1/ml/regime/summary")
    assert r.status_code == 200
    data = r.json()
    assert "trained" in data


def test_ml_regime_predict():
    r = client.get("/api/v1/ml/regime/predict")
    assert r.status_code in (200, 422)


# === Phase 4: Binance Testnet ===

def test_binance_testnet_health():
    r = client.get("/api/v1/binance/testnet/health")
    assert r.status_code == 200


def test_binance_testnet_status():
    r = client.get("/api/v1/binance/testnet/status")
    assert r.status_code == 200


def test_binance_testnet_price():
    r = client.get("/api/v1/binance/testnet/price?symbol=BTCUSDT")
    assert r.status_code == 200


# === Phase 4: Multi-Asset ===

def test_asset_classes():
    r = client.get("/api/v1/assets/classes")
    assert r.status_code == 200
    data = r.json()
    assert "crypto" in data


def test_supported_symbols():
    r = client.get("/api/v1/assets/symbols")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_forex_rates():
    r = client.get("/api/v1/assets/forex")
    assert r.status_code in (200, 422)


def test_commodity_prices():
    r = client.get("/api/v1/assets/commodities")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# === Deployment ===

def test_create_pipeline():
    r = client.post("/api/v1/deployment/pipeline")
    assert r.status_code == 201
    data = r.json()
    assert data["current_stage"] == "idea"


def test_validate_backtest():
    r = client.post("/api/v1/deployment/validate-backtest")
    assert r.status_code in (200, 422)


# === Summary ===

def test_all_endpoints():
    """Run all tests and report summary."""
    import pytest
    # This is just a marker for pytest collection
    pass


if __name__ == "__main__":
    tests = [
        test_health, test_dashboard,
        test_create_paper_order, test_paper_order_exceeds_limit,
        test_market_snapshots, test_refresh_market_snapshots,
        test_ohlcv, test_refresh_ohlcv,
        test_data_quality,
        test_risk_summary, test_risk_stress_test, test_risk_correlation, test_risk_concentration,
        test_market_analysis,
        test_recommendation, test_decisions_list,
        test_strategies,
        test_coach_review, test_lab_promotions,
        test_supervisor_status,
        test_fear_greed, test_refresh_fear_greed,
        test_funding_rates, test_refresh_funding_rates,
        test_open_interest, test_refresh_open_interest,
        test_memory_list, test_memory_remember, test_memory_compare,
        test_journal_analysis, test_journal_outcomes,
        test_sma_backtest, test_sma_walk_forward,
        test_donchian_walk_forward,
        test_mean_reversion_backtest, test_mean_reversion_walk_forward,
        test_grid_backtest, test_grid_walk_forward,
        test_market_order, test_limit_order, test_fractioned_order, test_estimate_slippage,
        test_optimize_sma, test_optimize_donchian, test_optimize_mean_reversion, test_optimize_grid, test_compare_strategies,
        test_alert_history, test_alert_thresholds, test_check_alerts,
        test_advanced_walk_forward, test_monte_carlo, test_sensitivity,
        test_ml_regime_summary, test_ml_regime_predict,
        test_binance_testnet_health, test_binance_testnet_status, test_binance_testnet_price,
        test_asset_classes, test_supported_symbols, test_forex_rates, test_commodity_prices,
        test_create_pipeline, test_validate_backtest,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"  PASS: {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL: {test.__name__} — {e}")
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
