"""SQLite persistence for the paper-trading MVP."""

import os
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "aegis.db"
DATABASE_PATH = Path(os.getenv("AEGIS_DB_PATH", DEFAULT_DATABASE_PATH))


def connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(DATABASE_PATH)
    database.row_factory = sqlite3.Row
    return database


def initialize() -> None:
    with connection() as database:
        database.executescript(
            """
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                quantity REAL NOT NULL,
                average_price REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS paper_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                reference_price REAL NOT NULL,
                notional REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS market_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                source TEXT NOT NULL,
                collected_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_market_snapshots_symbol_collected_at
                ON market_snapshots(symbol, collected_at DESC);
            CREATE TABLE IF NOT EXISTS ohlcv_candles (
                symbol TEXT NOT NULL,
                interval TEXT NOT NULL,
                open_time INTEGER NOT NULL,
                close_time INTEGER NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                source TEXT NOT NULL,
                PRIMARY KEY (symbol, interval, open_time)
            );
            CREATE TABLE IF NOT EXISTS backtests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy TEXT NOT NULL,
                symbol TEXT NOT NULL,
                interval TEXT NOT NULL,
                parameters_json TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS decision_journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                interval TEXT NOT NULL,
                decision_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS system_controls (
                name TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS system_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS fear_greed (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                value INTEGER NOT NULL,
                classification TEXT NOT NULL,
                source TEXT NOT NULL,
                collected_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS funding_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                mark_price REAL NOT NULL,
                index_price REAL NOT NULL,
                funding_rate REAL NOT NULL,
                next_funding_time INTEGER NOT NULL,
                source TEXT NOT NULL,
                collected_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_funding_rates_symbol_collected_at
                ON funding_rates(symbol, collected_at DESC);
            CREATE TABLE IF NOT EXISTS open_interest (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                open_interest REAL NOT NULL,
                open_interest_usd REAL NOT NULL,
                price REAL NOT NULL,
                source TEXT NOT NULL,
                collected_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_open_interest_symbol_collected_at
                ON open_interest(symbol, collected_at DESC);
            CREATE TABLE IF NOT EXISTS memory_episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                strategy TEXT NOT NULL,
                features_json TEXT NOT NULL,
                result_json TEXT,
                fingerprint TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_memory_fingerprint
                ON memory_episodes(fingerprint);
            """
        )


def list_positions() -> list[dict]:
    with connection() as database:
        return [dict(row) for row in database.execute("SELECT * FROM positions ORDER BY symbol")]


def list_recent_orders(limit: int = 10) -> list[dict]:
    with connection() as database:
        return [
            dict(row)
            for row in database.execute(
                "SELECT * FROM paper_orders ORDER BY id DESC LIMIT ?", (limit,)
            )
        ]


def save_order_and_position(order: dict, position: dict | None) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    with connection() as database:
        cursor = database.execute(
            """
            INSERT INTO paper_orders (symbol, side, quantity, reference_price, notional, status, created_at)
            VALUES (:symbol, :side, :quantity, :reference_price, :notional, 'filled_simulated', :created_at)
            """,
            {**order, "created_at": timestamp},
        )
        if position is None:
            database.execute("DELETE FROM positions WHERE symbol = ?", (order["symbol"],))
        else:
            database.execute(
                """
                INSERT INTO positions (symbol, quantity, average_price)
                VALUES (:symbol, :quantity, :average_price)
                ON CONFLICT(symbol) DO UPDATE SET
                    quantity = excluded.quantity,
                    average_price = excluded.average_price
                """,
                position,
            )
        return {"id": cursor.lastrowid, **order, "status": "filled_simulated", "created_at": timestamp}


def save_market_snapshots(snapshots: list[dict]) -> list[dict]:
    with connection() as database:
        database.executemany(
            """
            INSERT INTO market_snapshots (symbol, price, source, collected_at)
            VALUES (:symbol, :price, :source, :collected_at)
            """,
            snapshots,
        )
    return snapshots


def list_market_snapshots(limit: int = 30) -> list[dict]:
    with connection() as database:
        return [
            dict(row)
            for row in database.execute(
                "SELECT * FROM market_snapshots ORDER BY id DESC LIMIT ?", (limit,)
            )
        ]


def save_ohlcv_candles(candles: list[dict]) -> int:
    with connection() as database:
        database.executemany(
            """
            INSERT INTO ohlcv_candles
                (symbol, interval, open_time, close_time, open, high, low, close, volume, source)
            VALUES
                (:symbol, :interval, :open_time, :close_time, :open, :high, :low, :close, :volume, :source)
            ON CONFLICT(symbol, interval, open_time) DO UPDATE SET
                close_time = excluded.close_time,
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                source = excluded.source
            """,
            candles,
        )
    return len(candles)


def list_ohlcv_candles(symbol: str, interval: str, limit: int) -> list[dict]:
    with connection() as database:
        rows = database.execute(
            """
            SELECT * FROM ohlcv_candles
            WHERE symbol = ? AND interval = ?
            ORDER BY open_time DESC LIMIT ?
            """,
            (symbol, interval, limit),
        )
        return list(reversed([dict(row) for row in rows]))


def save_backtest(strategy: str, symbol: str, interval: str, parameters: dict, metrics: dict) -> dict:
    created_at = datetime.now(timezone.utc).isoformat()
    with connection() as database:
        cursor = database.execute(
            """
            INSERT INTO backtests (strategy, symbol, interval, parameters_json, metrics_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (strategy, symbol, interval, json.dumps(parameters), json.dumps(metrics), created_at),
        )
        return {"id": cursor.lastrowid, "strategy": strategy, "symbol": symbol, "interval": interval, "parameters": parameters, "metrics": metrics, "created_at": created_at}


def list_recent_backtests(limit: int = 5) -> list[dict]:
    with connection() as database:
        rows = database.execute("SELECT * FROM backtests ORDER BY id DESC LIMIT ?", (limit,))
        return [
            {
                "id": row["id"], "strategy": row["strategy"], "symbol": row["symbol"], "interval": row["interval"],
                "parameters": json.loads(row["parameters_json"]), "metrics": json.loads(row["metrics_json"]), "created_at": row["created_at"],
            }
            for row in rows
        ]


def save_decision(symbol: str, interval: str, decision: dict) -> dict:
    created_at = datetime.now(timezone.utc).isoformat()
    with connection() as database:
        cursor = database.execute("INSERT INTO decision_journal (symbol, interval, decision_json, created_at) VALUES (?, ?, ?, ?)", (symbol, interval, json.dumps(decision), created_at))
        return {"id": cursor.lastrowid, "symbol": symbol, "interval": interval, "decision": decision, "created_at": created_at}


def list_recent_decisions(limit: int = 20) -> list[dict]:
    with connection() as database:
        return [{"id": row["id"], "symbol": row["symbol"], "interval": row["interval"], "decision": json.loads(row["decision_json"]), "created_at": row["created_at"]} for row in database.execute("SELECT * FROM decision_journal ORDER BY id DESC LIMIT ?", (limit,))]


def get_kill_switch() -> bool:
    with connection() as database:
        row = database.execute("SELECT value FROM system_controls WHERE name = 'kill_switch'").fetchone()
        return row is not None and row["value"] == "active"


def set_kill_switch(active: bool, message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    with connection() as database:
        database.execute("INSERT INTO system_controls (name, value, updated_at) VALUES ('kill_switch', ?, ?) ON CONFLICT(name) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at", ("active" if active else "inactive", timestamp))
        database.execute("INSERT INTO system_alerts (severity, message, created_at) VALUES (?, ?, ?)", ("critical" if active else "info", message, timestamp))


def list_alerts(limit: int = 50) -> list[dict]:
    with connection() as database:
        return [dict(row) for row in database.execute("SELECT * FROM system_alerts ORDER BY id DESC LIMIT ?", (limit,))]


def compute_equity_curve(initial_capital: float, positions: list[dict], orders: list[dict]) -> list[dict]:
    """Compute a simple equity curve from order history for dashboard display."""
    if not orders:
        return [{"time": "now", "equity": initial_capital}]
    sorted_orders = sorted(orders, key=lambda o: o["id"])
    equity = initial_capital
    curve = [{"time": "start", "equity": initial_capital}]
    for order in sorted_orders:
        if order["side"] == "buy":
            equity -= order["notional"]
        else:
            equity += order["notional"]
        curve.append({"time": order["created_at"], "equity": round(equity, 2)})
    for pos in positions:
        equity += pos["quantity"] * pos["average_price"]
    curve.append({"time": "current", "equity": round(equity, 2)})
    return curve[-20:]


def save_fear_greed(data: dict) -> dict:
    with connection() as database:
        database.execute(
            "INSERT INTO fear_greed (value, classification, source, collected_at) VALUES (:value, :classification, :source, :collected_at)",
            data,
        )
    return data


def list_fear_greed(limit: int = 30) -> list[dict]:
    with connection() as database:
        return [dict(row) for row in database.execute("SELECT * FROM fear_greed ORDER BY id DESC LIMIT ?", (limit,))]


def save_funding_rate(data: dict) -> dict:
    with connection() as database:
        database.execute(
            """INSERT INTO funding_rates (symbol, mark_price, index_price, funding_rate, next_funding_time, source, collected_at)
            VALUES (:symbol, :mark_price, :index_price, :funding_rate, :next_funding_time, :source, :collected_at)""",
            data,
        )
    return data


def list_funding_rates(symbol: str | None = None, limit: int = 30) -> list[dict]:
    with connection() as database:
        if symbol:
            return [dict(row) for row in database.execute(
                "SELECT * FROM funding_rates WHERE symbol = ? ORDER BY id DESC LIMIT ?", (symbol, limit)
            )]
        return [dict(row) for row in database.execute("SELECT * FROM funding_rates ORDER BY id DESC LIMIT ?", (limit,))]


def save_open_interest(data: dict) -> dict:
    with connection() as database:
        database.execute(
            """INSERT INTO open_interest (symbol, open_interest, open_interest_usd, price, source, collected_at)
            VALUES (:symbol, :open_interest, :open_interest_usd, :price, :source, :collected_at)""",
            data,
        )
    return data


def list_open_interest(symbol: str | None = None, limit: int = 30) -> list[dict]:
    with connection() as database:
        if symbol:
            return [dict(row) for row in database.execute(
                "SELECT * FROM open_interest WHERE symbol = ? ORDER BY id DESC LIMIT ?", (symbol, limit)
            )]
        return [dict(row) for row in database.execute("SELECT * FROM open_interest ORDER BY id DESC LIMIT ?", (limit,))]


def save_memory_episode(symbol: str, strategy: str, features: dict, result: dict | None, fingerprint: str) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    with connection() as database:
        cursor = database.execute(
            """INSERT INTO memory_episodes (symbol, strategy, features_json, result_json, fingerprint, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (symbol, strategy, json.dumps(features), json.dumps(result) if result else None, fingerprint, timestamp),
        )
        return {"id": cursor.lastrowid, "symbol": symbol, "strategy": strategy, "fingerprint": fingerprint, "created_at": timestamp}


def list_memory_episodes(symbol: str | None = None, limit: int = 100) -> list[dict]:
    with connection() as database:
        if symbol:
            rows = database.execute(
                "SELECT * FROM memory_episodes WHERE symbol = ? ORDER BY id DESC LIMIT ?", (symbol, limit)
            )
        else:
            rows = database.execute("SELECT * FROM memory_episodes ORDER BY id DESC LIMIT ?", (limit,))
        return [
            {
                "id": row["id"],
                "symbol": row["symbol"],
                "strategy": row["strategy"],
                "features": json.loads(row["features_json"]),
                "result": json.loads(row["result_json"]) if row["result_json"] else None,
                "fingerprint": row["fingerprint"],
                "timestamp": row["created_at"],
            }
            for row in rows
        ]
