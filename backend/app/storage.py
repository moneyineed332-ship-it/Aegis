"""SQLite persistence for the paper-trading MVP."""

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from . import config

logger = logging.getLogger(__name__)

DATABASE_PATH = Path(config.DB_PATH)


# --- Symbol normalization ---
# Internal storage uses unified format (no slash).
# Frontend/API uses display format (with slash).
# Crypto: "BTC/USDT" -> "BTCUSDT"
# Forex: "EUR/USD" -> "EURUSD"
def normalize_symbol(symbol: str) -> str:
    """Convert any symbol format to the internal format (no slash)."""
    return symbol.replace("/", "").replace("-", "")


def display_symbol(symbol: str) -> str:
    """Convert internal symbol to display format (with slash)."""
    s = normalize_symbol(symbol)
    
    # Handle Forex symbols (EURUSD, GBPUSD, XAUUSD)
    if s in ["EURUSD", "GBPUSD", "XAUUSD"]:
        if s == "XAUUSD":
            return "XAU/USD"
        elif len(s) == 6:  # EURUSD, GBPUSD
            return s[:3] + "/" + s[3:]
    
    # Handle crypto symbols (BTCUSDT, ETHUSDT, etc.)
    if len(s) > 3 and s[-4:] in ("USDT", "USDC", "BUSD", "BTC", "ETH"):
        return s[:-4] + "/" + s[-4:]
    
    return s

# Connection pool with threading lock
_db_lock = threading.RLock()
_db_connection: sqlite3.Connection | None = None
_initialized = False


def _get_connection() -> sqlite3.Connection:
    """Get a persistent SQLite connection with WAL mode."""
    global _db_connection, DATABASE_PATH
    with _db_lock:
        current_path = Path(config.DB_PATH)
        if _db_connection is None or DATABASE_PATH != current_path:
            if _db_connection is not None:
                try:
                    _db_connection.close()
                except Exception:
                    pass
                _db_connection = None
            current_path.parent.mkdir(parents=True, exist_ok=True)
            _db_connection = sqlite3.connect(str(current_path), check_same_thread=False)
            _db_connection.row_factory = sqlite3.Row
            _db_connection.execute("PRAGMA journal_mode=WAL")
            _db_connection.execute("PRAGMA synchronous=NORMAL")
            _db_connection.execute("PRAGMA cache_size=-64000")
            DATABASE_PATH = current_path
        return _db_connection


@contextmanager
def connection():
    """Context manager that yields the persistent connection with thread-safe locking."""
    db = _get_connection()
    _db_lock.acquire()
    try:
        yield db
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        _db_lock.release()


def initialize() -> None:
    """Initialize database tables. Called once at startup."""
    global _initialized
    if _initialized:
        return
    with _db_lock:
        db = _get_connection()
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                quantity REAL NOT NULL,
                average_price REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS paper_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                reference_price REAL NOT NULL,
                notional REAL NOT NULL,
                status TEXT NOT NULL,
                strategy TEXT DEFAULT 'manual',
                mode TEXT DEFAULT 'paper',
                exchange_order_id TEXT,
                fill_price REAL,
                fee REAL DEFAULT 0,
                reason TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_paper_orders_created
                ON paper_orders(created_at DESC);
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
            CREATE INDEX IF NOT EXISTS idx_backtests_strategy ON backtests(strategy);
            CREATE INDEX IF NOT EXISTS idx_backtests_created ON backtests(created_at DESC);
            CREATE TABLE IF NOT EXISTS decision_journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                interval TEXT NOT NULL,
                decision_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_decision_journal_created ON decision_journal(created_at DESC);
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
            CREATE INDEX IF NOT EXISTS idx_system_alerts_created ON system_alerts(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_system_alerts_severity ON system_alerts(severity);
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
            CREATE INDEX IF NOT EXISTS idx_memory_symbol_strategy
                ON memory_episodes(symbol, strategy);

            -- ICT/SMC specific tables
            CREATE TABLE IF NOT EXISTS ict_trades_journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                instrument TEXT NOT NULL,
                direction TEXT NOT NULL,
                setup TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                entry_price REAL NOT NULL,
                sl_price REAL NOT NULL,
                tp_price REAL NOT NULL,
                risk_amount REAL NOT NULL,
                result TEXT NOT NULL,
                rr_ratio REAL NOT NULL,
                drawdown REAL,
                pnl REAL,
                notes TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ict_journal_date ON ict_trades_journal(date DESC);
            CREATE INDEX IF NOT EXISTS idx_ict_journal_instrument ON ict_trades_journal(instrument);
            CREATE INDEX IF NOT EXISTS idx_ict_journal_result ON ict_trades_journal(result);

            -- Engine state tables
            CREATE TABLE IF NOT EXISTS engine_state (
                name TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS engine_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details_json TEXT,
                severity TEXT NOT NULL DEFAULT 'info',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_engine_log_cycle
                ON engine_log(cycle_id);
            CREATE INDEX IF NOT EXISTS idx_engine_log_created
                ON engine_log(created_at DESC);
            CREATE TABLE IF NOT EXISTS trailing_stops_active (
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                trail_pct REAL NOT NULL,
                highest_price REAL,
                lowest_price REAL,
                stop_price REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                PRIMARY KEY (symbol, side)
            );
            CREATE TABLE IF NOT EXISTS trade_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                strategy TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                signal_json TEXT NOT NULL,
                executed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_trade_signals_created
                ON trade_signals(created_at DESC);
            CREATE TABLE IF NOT EXISTS open_orders (
                order_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                limit_price REAL NOT NULL,
                strategy TEXT NOT NULL DEFAULT 'manual',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );
            """
        )
        # --- Migration: add missing columns to existing tables ---
        _migrate_paper_orders(db)
        # Seed the kill switch so its absence can be treated as a fault below
        # rather than as "trading allowed".
        db.execute(
            "INSERT OR IGNORE INTO system_controls (name, value, updated_at) VALUES ('kill_switch', 'inactive', ?)",
            (datetime.now(timezone.utc).isoformat(),),
        )
        _initialized = True
        logger.info("Database initialized with WAL mode")


def _migrate_paper_orders(db: sqlite3.Connection) -> None:
    """Add missing columns to paper_orders table for existing databases."""
    new_columns = {
        "order_id": "TEXT",
        "strategy": "TEXT DEFAULT 'manual'",
        "mode": "TEXT DEFAULT 'paper'",
        "exchange_order_id": "TEXT",
        "fill_price": "REAL",
        "fee": "REAL DEFAULT 0",
        "reason": "TEXT",
    }
    existing = {row[1] for row in db.execute("PRAGMA table_info(paper_orders)").fetchall()}
    for col, col_type in new_columns.items():
        if col not in existing:
            try:
                db.execute(f"ALTER TABLE paper_orders ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists (race condition)
    # Add index if missing
    try:
        db.execute("CREATE INDEX IF NOT EXISTS idx_paper_orders_created ON paper_orders(created_at DESC)")
    except sqlite3.OperationalError:
        pass


def list_positions() -> list[dict]:
    with connection() as database:
        return [dict(row) for row in database.execute("SELECT * FROM positions ORDER BY symbol")]


def cleanup_stale_positions() -> int:
    """Remove positions with non-normalized symbols or non-positive prices.

    A low price is NOT by itself corruption: EURUSD (~1.08), DOGE and SHIB all
    trade below 1. Only impossible values (price <= 0) are dropped, so a boot
    can never silently delete a legitimate Forex or micro-cap holding. Prices
    that look implausible for a given symbol are only logged for review.
    """
    stale_symbols = []
    suspicious = []
    with connection() as database:
        rows = database.execute("SELECT symbol, average_price FROM positions").fetchall()
        for row in rows:
            symbol = row["symbol"]
            price = row["average_price"]
            normalized = normalize_symbol(symbol)
            if symbol != normalized:
                stale_symbols.append(symbol)
            elif price is None or price <= 0:
                stale_symbols.append(symbol)
            else:
                implausible = _implausible_price(symbol, price)
                if implausible:
                    suspicious.append(f"{symbol} @ {price}")
        for sym in stale_symbols:
            database.execute("DELETE FROM positions WHERE symbol = ?", (sym,))
            logger.warning("Removed stale position: %s", sym)
        for item in suspicious:
            logger.warning("Position price looks implausible, kept for review: %s", item)
    return len(stale_symbols)


# Rough order-of-magnitude sanity bands, used for logging only.
_PRICE_BANDS = {
    "BTC": (1_000.0, 1_000_000.0),
    "ETH": (50.0, 100_000.0),
    "XAU": (100.0, 10_000.0),
    "EUR": (0.5, 3.0),
    "GBP": (0.5, 3.0),
}


def _implausible_price(symbol: str, price: float) -> bool:
    """Return True when a price is far outside the expected range for a symbol."""
    normalized = normalize_symbol(symbol).upper()
    for prefix, (low, high) in _PRICE_BANDS.items():
        if normalized.startswith(prefix):
            return not (low <= price <= high)
    return False


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
            INSERT INTO paper_orders (order_id, symbol, side, quantity, reference_price, notional, status, strategy, mode, exchange_order_id, fill_price, fee, reason, created_at)
            VALUES (:order_id, :symbol, :side, :quantity, :reference_price, :notional, :status, :strategy, :mode, :exchange_order_id, :fill_price, :fee, :reason, :created_at)
            """,
            {
                "order_id": order.get("order_id"),
                "symbol": order["symbol"],
                "side": order["side"],
                "quantity": order["quantity"],
                "reference_price": order["reference_price"],
                "notional": order["notional"],
                "status": order.get("status", "filled_simulated"),
                "strategy": order.get("strategy", "manual"),
                "mode": order.get("mode", "paper"),
                "exchange_order_id": order.get("exchange_order_id"),
                "fill_price": order.get("fill_price", order["reference_price"]),
                "fee": order.get("fee", 0),
                "reason": order.get("reason"),
                "created_at": timestamp,
            },
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
        return {"id": cursor.lastrowid, **order, "status": order.get("status", "filled_simulated"), "created_at": timestamp}


def save_open_order(order_id: str, symbol: str, side: str, quantity: float, limit_price: float, strategy: str = "manual") -> None:
    """Save a pending limit order to open_orders table."""
    timestamp = datetime.now(timezone.utc).isoformat()
    with connection() as database:
        database.execute(
            """
            INSERT INTO open_orders (order_id, symbol, side, quantity, limit_price, strategy, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (order_id, symbol, side, quantity, limit_price, strategy, timestamp),
        )


def list_open_orders() -> list[dict]:
    """List all pending open orders."""
    with connection() as database:
        return [
            dict(row)
            for row in database.execute(
                "SELECT * FROM open_orders WHERE status = 'pending' ORDER BY created_at DESC"
            )
        ]


def remove_open_order(order_id: str) -> None:
    """Mark an open order as filled/cancelled."""
    with connection() as database:
        database.execute(
            "UPDATE open_orders SET status = 'filled' WHERE order_id = ?",
            (order_id,),
        )


def cancel_open_order(order_id: str) -> None:
    """Cancel a pending open order."""
    with connection() as database:
        database.execute(
            "UPDATE open_orders SET status = 'cancelled' WHERE order_id = ?",
            (order_id,),
        )


def save_market_snapshots(snapshots: list[dict]) -> list[dict]:
    normalized = []
    for s in snapshots:
        normalized.append({**s, "symbol": normalize_symbol(s["symbol"])})
    with connection() as database:
        database.executemany(
            """
            INSERT INTO market_snapshots (symbol, price, source, collected_at)
            VALUES (:symbol, :price, :source, :collected_at)
            """,
            normalized,
        )
    return normalized


def list_market_snapshots(limit: int = 30) -> list[dict]:
    with connection() as database:
        return [
            dict(row)
            for row in database.execute(
                "SELECT * FROM market_snapshots ORDER BY id DESC LIMIT ?", (limit,)
            )
        ]


def save_ohlcv_candles(candles: list[dict]) -> int:
    normalized = [{**c, "symbol": normalize_symbol(c["symbol"])} for c in candles]
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
            normalized,
        )
    return len(normalized)


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
    """Read the kill switch, failing closed.

    A missing row or a storage error means the state of the switch is unknown,
    so it is reported as ACTIVE: a read fault must never silently re-enable
    trading. The row is seeded as "inactive" at database init.
    """
    try:
        with connection() as database:
            row = database.execute("SELECT value FROM system_controls WHERE name = 'kill_switch'").fetchone()
        if row is None:
            logger.error("Kill switch row missing: failing closed (trading halted)")
            return True
        return row["value"] == "active"
    except Exception:
        logger.error("Kill switch read failed: failing closed (trading halted)", exc_info=True)
        return True


def set_kill_switch(active: bool, message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    with connection() as database:
        database.execute("INSERT INTO system_controls (name, value, updated_at) VALUES ('kill_switch', ?, ?) ON CONFLICT(name) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at", ("active" if active else "inactive", timestamp))
        database.execute("INSERT INTO system_alerts (severity, message, created_at) VALUES (?, ?, ?)", ("critical" if active else "info", message, timestamp))


def list_alerts(limit: int = 50) -> list[dict]:
    with connection() as database:
        return [dict(row) for row in database.execute("SELECT * FROM system_alerts ORDER BY id DESC LIMIT ?", (limit,))]


# Cap on the number of orders replayed to rebuild the equity curve, so a
# long-lived database cannot turn a dashboard call into a full table scan.
_EQUITY_CURVE_MAX_ORDERS = 5_000


def compute_equity_curve(initial_capital: float, positions: list[dict], orders: list[dict], prices: dict[str, float] | None = None) -> list[dict]:
    """Rebuild the equity curve from the order history.

    Equity is ``initial_capital + realized_pnl - fees + unrealized_pnl``.
    Orders are replayed with per-symbol netting so that a closing trade books
    the real gain or loss instead of the traded notional, and fees are always
    charged. Mark prices come from ``prices`` and fall back to the basis
    established by the replay, which makes the unrealized term explicit
    instead of silently zero.

    Falls back to the recorded equity snapshots in ``engine_log`` when no
    order history exists.
    """
    from datetime import datetime, timezone

    if not orders:
        return _equity_curve_from_logs(initial_capital)

    # The order id is the replay cursor, so work oldest-first.
    sorted_orders = sorted(orders, key=lambda o: o["id"])
    if len(sorted_orders) > _EQUITY_CURVE_MAX_ORDERS:
        logger.warning(
            "Equity curve truncated to the last %d orders (got %d)",
            _EQUITY_CURVE_MAX_ORDERS, len(sorted_orders),
        )
        sorted_orders = sorted_orders[-_EQUITY_CURVE_MAX_ORDERS:]

    # Replay state: net quantity and cost basis per symbol.
    quantity: dict[str, float] = {}
    basis: dict[str, float] = {}
    last_price: dict[str, float] = {}
    realized = 0.0

    start_time = sorted_orders[0]["created_at"]
    curve = [{"time": start_time, "equity": round(initial_capital, 2)}]

    for order in sorted_orders:
        symbol = order["symbol"]
        price = order.get("fill_price") or order.get("reference_price")
        if not price:
            # Cannot net a trade without a price; skip rather than corrupt the curve.
            logger.warning("Equity curve skipped order %s: no fill price", order.get("id"))
            continue
        signed = order["quantity"] if order["side"] == "buy" else -order["quantity"]
        held = quantity.get(symbol, 0.0)

        if held == 0:
            quantity[symbol] = signed
            basis[symbol] = price
        elif (held > 0) == (signed > 0):
            # Adding to the position: weighted average cost basis.
            total_cost = abs(basis[symbol] * held) + abs(price * signed)
            quantity[symbol] = held + signed
            basis[symbol] = total_cost / abs(quantity[symbol])
        else:
            # Reducing or flipping: book the realized result on the closed part.
            closed = min(abs(signed), abs(held))
            direction = 1.0 if held > 0 else -1.0
            realized += (price - basis[symbol]) * closed * direction
            new_qty = held + signed
            if new_qty == 0:
                quantity.pop(symbol, None)
                basis.pop(symbol, None)
            elif (new_qty > 0) != (held > 0):
                # Flipped direction: the residual is a fresh position.
                quantity[symbol] = new_qty
                basis[symbol] = price
            else:
                # Partial close: quantity shrinks, the basis is untouched.
                quantity[symbol] = new_qty

        # Fees are a realized cost whatever the direction.
        realized -= float(order.get("fee") or 0.0)
        last_price[symbol] = price

        # Historical points are marked with the price known at that point in
        # the replay. Using today's mark here would retroactively rewrite the
        # whole curve.
        equity = initial_capital + realized + _unrealized_from_state(quantity, basis, None, last_price)
        curve.append({"time": order["created_at"], "equity": round(equity, 2)})

    final_equity = initial_capital + realized + _unrealized_from_state(quantity, basis, prices, last_price)
    curve.append({
        "time": datetime.now(timezone.utc).isoformat(),
        "equity": round(final_equity, 2),
    })
    return curve[-100:]


def _unrealized_from_state(
    quantity: dict[str, float],
    basis: dict[str, float],
    prices: dict[str, float] | None,
    last_price: dict[str, float],
) -> float:
    """Mark-to-market value of the replayed open positions.

    ``prices`` holds live marks and is used for the current point only; the
    historical points fall back to the last traded price of each symbol.
    """
    marks = prices or {}
    total = 0.0
    for symbol, qty in quantity.items():
        if qty == 0:
            continue
        mark = marks.get(symbol) or last_price.get(symbol) or basis.get(symbol)
        if mark is None:
            continue
        total += (mark - basis[symbol]) * qty
    return total


def _equity_curve_from_logs(initial_capital: float) -> list[dict]:
    """Rebuild the curve from recorded equity snapshots, newest first."""
    with connection() as database:
        rows = database.execute(
            "SELECT created_at, details_json FROM engine_log "
            "WHERE event_type = 'position_update' ORDER BY id DESC LIMIT 200"
        ).fetchall()

    curve: list[dict] = []
    seen_minutes: set[str] = set()
    for row in reversed(rows):
        try:
            details = json.loads(row["details_json"] or "{}")
        except (TypeError, ValueError):
            continue
        equity = details.get("equity")
        if equity is None:
            continue
        minute_key = row["created_at"][:16]
        if minute_key in seen_minutes:
            continue
        seen_minutes.add(minute_key)
        curve.append({"time": row["created_at"], "equity": round(float(equity), 2)})

    if not curve:
        from datetime import datetime, timezone
        return [{"time": datetime.now(timezone.utc).isoformat(), "equity": round(initial_capital, 2)}]

    return curve[-50:]


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
                "features": json.loads(row["features_json"]) if row["features_json"] else {},
                "result": json.loads(row["result_json"]) if row["result_json"] else None,
                "fingerprint": row["fingerprint"],
                "timestamp": row["created_at"],
            }
            for row in rows
        ]


# --- Engine State ---

def get_engine_state(name: str) -> str | None:
    """Get a named engine state value."""
    with connection() as database:
        row = database.execute("SELECT value FROM engine_state WHERE name = ?", (name,)).fetchone()
        return row["value"] if row else None


def set_engine_state(name: str, value: str) -> None:
    """Set a named engine state value."""
    timestamp = datetime.now(timezone.utc).isoformat()
    with connection() as database:
        database.execute(
            "INSERT INTO engine_state (name, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (name, value, timestamp),
        )


def log_engine_event(cycle_id: str, event_type: str, details: dict | None = None, severity: str = "info") -> None:
    """Log an engine event."""
    timestamp = datetime.now(timezone.utc).isoformat()
    with connection() as database:
        database.execute(
            "INSERT INTO engine_log (cycle_id, event_type, details_json, severity, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (cycle_id, event_type, json.dumps(details) if details else None, severity, timestamp),
        )


def list_engine_logs(limit: int = 100) -> list[dict]:
    """List recent engine log entries."""
    with connection() as database:
        rows = database.execute(
            "SELECT * FROM engine_log ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [
            {
                "id": row["id"],
                "cycle_id": row["cycle_id"],
                "event_type": row["event_type"],
                "details": json.loads(row["details_json"]) if row["details_json"] else None,
                "severity": row["severity"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]


def get_engine_stats() -> dict:
    """Get engine statistics from the log."""
    with connection() as database:
        total = database.execute("SELECT COUNT(*) as n FROM engine_log").fetchone()["n"]
        errors = database.execute("SELECT COUNT(*) as n FROM engine_log WHERE severity = 'error'").fetchone()["n"]
        trades = database.execute("SELECT COUNT(*) as n FROM engine_log WHERE event_type = 'order_executed'").fetchone()["n"]
        signals = database.execute("SELECT COUNT(*) as n FROM engine_log WHERE event_type = 'signal_generated'").fetchone()["n"]
        cycles = database.execute("SELECT COUNT(DISTINCT cycle_id) as n FROM engine_log").fetchone()["n"]
        return {
            "total_events": total,
            "errors": errors,
            "trades_executed": trades,
            "signals_generated": signals,
            "total_cycles": cycles,
        }


def save_trade_signal(symbol: str, strategy: str, signal_type: str, signal: dict) -> dict:
    """Save a trade signal for execution tracking."""
    timestamp = datetime.now(timezone.utc).isoformat()
    with connection() as database:
        cursor = database.execute(
            "INSERT INTO trade_signals (symbol, strategy, signal_type, signal_json, executed, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (symbol, strategy, signal_type, json.dumps(signal), timestamp),
        )
        return {"id": cursor.lastrowid, "symbol": symbol, "strategy": strategy, "created_at": timestamp}


def mark_signal_executed(signal_id: int) -> None:
    """Mark a trade signal as executed."""
    with connection() as database:
        database.execute("UPDATE trade_signals SET executed = 1 WHERE id = ?", (signal_id,))


def list_trade_signals(limit: int = 20) -> list[dict]:
    """List recent trade signals."""
    with connection() as database:
        rows = database.execute(
            "SELECT * FROM trade_signals ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [
            {
                "id": row["id"],
                "symbol": row["symbol"],
                "strategy": row["strategy"],
                "signal_type": row["signal_type"],
                "signal": json.loads(row["signal_json"]),
                "executed": bool(row["executed"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]


# --- Trailing Stops Persistence ---

def save_trailing_stop(symbol: str, side: str, entry_price: float, trail_pct: float, stop_price: float) -> None:
    """Persist a trailing stop to DB."""
    timestamp = datetime.now(timezone.utc).isoformat()
    with connection() as database:
        database.execute(
            "INSERT INTO trailing_stops_active (symbol, side, entry_price, trail_pct, highest_price, lowest_price, stop_price, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?) "
            "ON CONFLICT(symbol, side) DO UPDATE SET "
            "entry_price = excluded.entry_price, trail_pct = excluded.trail_pct, "
            "stop_price = excluded.stop_price, status = 'active', created_at = excluded.created_at",
            (symbol, side, entry_price, trail_pct, entry_price, entry_price, stop_price, timestamp),
        )


def update_trailing_stop_state(symbol: str, side: str, highest_price: float | None, lowest_price: float | None, stop_price: float) -> None:
    """Update trailing stop prices."""
    with connection() as database:
        database.execute(
            "UPDATE trailing_stops_active SET highest_price = ?, lowest_price = ?, stop_price = ? "
            "WHERE symbol = ? AND side = ?",
            (highest_price, lowest_price, stop_price, symbol, side),
        )


def remove_trailing_stop_state(symbol: str, side: str) -> None:
    """Remove a trailing stop from DB."""
    with connection() as database:
        database.execute("DELETE FROM trailing_stops_active WHERE symbol = ? AND side = ?", (symbol, side))


def list_active_trailing_stops() -> list[dict]:
    """List all active trailing stops from DB."""
    with connection() as database:
        return [
            dict(row)
            for row in database.execute(
                "SELECT * FROM trailing_stops_active WHERE status = 'active'"
            )
        ]


# --- Circuit Breaker Persistence ---

def save_circuit_breaker_state(state: dict) -> None:
    """Persist circuit breaker state to engine_state as JSON."""
    serializable = {
        "halted": state["halted"],
        "reason": state["reason"],
        "halted_at": state["halted_at"].isoformat() if state["halted_at"] else None,
        "daily_pnl": state["daily_pnl"],
        "consecutive_losses": state["consecutive_losses"],
    }
    set_engine_state("circuit_breaker", json.dumps(serializable))


def load_circuit_breaker_state() -> dict | None:
    """Load circuit breaker state from DB. Returns None if not found."""
    raw = get_engine_state("circuit_breaker")
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if data.get("halted_at"):
            from datetime import datetime as _dt, timezone as _tz
            data["halted_at"] = _dt.fromisoformat(data["halted_at"])
        return data
    except (json.JSONDecodeError, KeyError):
        return None


# --- Deployment Pipeline Persistence ---

def _ensure_deployment_pipelines_table(db: sqlite3.Connection) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS deployment_pipelines (
            strategy_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            pipeline_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (strategy_id, symbol)
        )
    """)


def save_pipeline(pipeline: dict) -> None:
    """Persist a deployment pipeline to DB."""
    timestamp = datetime.now(timezone.utc).isoformat()
    with connection() as database:
        _ensure_deployment_pipelines_table(database)
        database.execute(
            "INSERT INTO deployment_pipelines (strategy_id, symbol, pipeline_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(strategy_id, symbol) DO UPDATE SET "
            "pipeline_json = excluded.pipeline_json, updated_at = excluded.updated_at",
            (
                pipeline["strategy_id"],
                pipeline["symbol"],
                json.dumps(pipeline),
                pipeline.get("created_at", timestamp),
                timestamp,
            ),
        )


def load_pipeline(strategy_id: str, symbol: str) -> dict | None:
    """Load a deployment pipeline from DB."""
    with connection() as database:
        _ensure_deployment_pipelines_table(database)
        row = database.execute(
            "SELECT pipeline_json FROM deployment_pipelines WHERE strategy_id = ? AND symbol = ?",
            (strategy_id, symbol),
        ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["pipeline_json"])
        except json.JSONDecodeError:
            return None


def list_pipelines(status_filter: str | None = None) -> list[dict]:
    """List all deployment pipelines, optionally filtered by current stage."""
    with connection() as database:
        _ensure_deployment_pipelines_table(database)
        rows = database.execute(
            "SELECT pipeline_json FROM deployment_pipelines ORDER BY updated_at DESC"
        ).fetchall()
        pipelines = []
        for row in rows:
            try:
                p = json.loads(row["pipeline_json"])
                if status_filter is None or p.get("current_stage") == status_filter:
                    pipelines.append(p)
            except json.JSONDecodeError:
                continue
        return pipelines


# --- ML Model Persistence ---

def _ensure_ml_models_table(db: sqlite3.Connection) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS ml_models (
            model_id TEXT PRIMARY KEY,
            model_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)


def save_ml_model(model_id: str, model_data: dict) -> None:
    """Persist ML model state (weights, biases, config) to DB."""
    timestamp = datetime.now(timezone.utc).isoformat()
    with connection() as database:
        _ensure_ml_models_table(database)
        database.execute(
            "INSERT INTO ml_models (model_id, model_json, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(model_id) DO UPDATE SET model_json = excluded.model_json, updated_at = excluded.updated_at",
            (model_id, json.dumps(model_data), timestamp),
        )


def load_ml_model(model_id: str) -> dict | None:
    """Load ML model state from DB."""
    with connection() as database:
        _ensure_ml_models_table(database)
        row = database.execute(
            "SELECT model_json FROM ml_models WHERE model_id = ?", (model_id,)
        ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["model_json"])
        except json.JSONDecodeError:
            return None


# --- Strategy Performance Stats ---

def _ensure_strategy_stats_table(db: sqlite3.Connection) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS strategy_stats (
            strategy_id TEXT PRIMARY KEY,
            stats_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)


def save_strategy_stats(strategy_id: str, stats: dict) -> None:
    """Persist strategy performance stats."""
    timestamp = datetime.now(timezone.utc).isoformat()
    with connection() as database:
        _ensure_strategy_stats_table(database)
        database.execute(
            "INSERT INTO strategy_stats (strategy_id, stats_json, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(strategy_id) DO UPDATE SET stats_json = excluded.stats_json, updated_at = excluded.updated_at",
            (strategy_id, json.dumps(stats), timestamp),
        )


def load_strategy_stats(strategy_id: str) -> dict | None:
    """Load strategy performance stats."""
    with connection() as database:
        _ensure_strategy_stats_table(database)
        row = database.execute(
            "SELECT stats_json FROM strategy_stats WHERE strategy_id = ?", (strategy_id,)
        ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["stats_json"])
        except json.JSONDecodeError:
            return None


def list_strategy_stats() -> list[dict]:
    """List all strategy performance stats."""
    with connection() as database:
        _ensure_strategy_stats_table(database)
        rows = database.execute(
            "SELECT strategy_id, stats_json, updated_at FROM strategy_stats ORDER BY updated_at DESC"
        ).fetchall()
        result = []
        for row in rows:
            try:
                stats = json.loads(row["stats_json"])
                stats["strategy_id"] = row["strategy_id"]
                stats["updated_at"] = row["updated_at"]
                result.append(stats)
            except json.JSONDecodeError:
                continue
        return result


# --- Trade Outcomes ---

def _ensure_trade_outcomes_table(db: sqlite3.Connection) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS trade_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            symbol TEXT NOT NULL,
            strategy TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL,
            quantity REAL NOT NULL,
            pnl REAL,
            pnl_pct REAL,
            duration_seconds INTEGER,
            regime_at_entry TEXT,
            features_json TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            opened_at TEXT NOT NULL,
            closed_at TEXT
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_trade_outcomes_strategy ON trade_outcomes(strategy)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_trade_outcomes_status ON trade_outcomes(status)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_trade_outcomes_opened ON trade_outcomes(opened_at DESC)"
    )


def save_trade_outcome(outcome: dict) -> dict:
    """Save a trade outcome record."""
    with connection() as database:
        _ensure_trade_outcomes_table(database)
        cursor = database.execute(
            """INSERT INTO trade_outcomes
                (order_id, symbol, strategy, side, entry_price, exit_price, quantity,
                 pnl, pnl_pct, duration_seconds, regime_at_entry, features_json, status, opened_at, closed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                outcome.get("order_id"),
                outcome["symbol"],
                outcome["strategy"],
                outcome["side"],
                outcome["entry_price"],
                outcome.get("exit_price"),
                outcome["quantity"],
                outcome.get("pnl"),
                outcome.get("pnl_pct"),
                outcome.get("duration_seconds"),
                outcome.get("regime_at_entry"),
                json.dumps(outcome.get("features")) if outcome.get("features") else None,
                outcome.get("status", "open"),
                outcome["opened_at"],
                outcome.get("closed_at"),
            ),
        )
        return {"id": cursor.lastrowid, **outcome}


def update_trade_outcome_close(order_id: str, exit_price: float, pnl: float, pnl_pct: float, duration_seconds: int) -> None:
    """Update a trade outcome when position is closed."""
    timestamp = datetime.now(timezone.utc).isoformat()
    with connection() as database:
        _ensure_trade_outcomes_table(database)
        database.execute(
            """UPDATE trade_outcomes
            SET exit_price = ?, pnl = ?, pnl_pct = ?, duration_seconds = ?,
                status = 'closed', closed_at = ?
            WHERE order_id = ? AND status = 'open'""",
            (exit_price, pnl, pnl_pct, duration_seconds, timestamp, order_id),
        )


def list_trade_outcomes(symbol: str | None = None, strategy: str | None = None, status: str | None = None, limit: int = 100) -> list[dict]:
    """List trade outcomes with optional filters."""
    with connection() as database:
        _ensure_trade_outcomes_table(database)
        query = "SELECT * FROM trade_outcomes"
        params = []
        conditions = []
        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol)
        if strategy:
            conditions.append("strategy = ?")
            params.append(strategy)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = database.execute(query, params).fetchall()
        return [
            {
                "id": row["id"],
                "order_id": row["order_id"],
                "symbol": row["symbol"],
                "strategy": row["strategy"],
                "side": row["side"],
                "entry_price": row["entry_price"],
                "exit_price": row["exit_price"],
                "quantity": row["quantity"],
                "pnl": row["pnl"],
                "pnl_pct": row["pnl_pct"],
                "duration_seconds": row["duration_seconds"],
                "regime_at_entry": row["regime_at_entry"],
                "features": json.loads(row["features_json"]) if row["features_json"] else None,
                "status": row["status"],
                "opened_at": row["opened_at"],
                "closed_at": row["closed_at"],
            }
            for row in rows
        ]


# ============================================================
# ICT/SMC TRADE JOURNAL FUNCTIONS
# ============================================================

def save_ict_trade_journal(
    date: str,
    instrument: str,
    direction: str,
    setup: str,
    timeframe: str,
    entry_price: float,
    sl_price: float,
    tp_price: float,
    risk_amount: float,
    result: str,
    rr_ratio: float,
    drawdown: float | None = None,
    pnl: float | None = None,
    notes: str = ""
) -> dict:
    """
    Save an ICT/SMC trade journal entry.
    
    Format according to cahier des charges:
    "Date | Instrument | Direction | Setup | Timeframe | Entrée | SL | TP | Risque | Résultat | R/R | Drawdown"
    """
    created_at = datetime.now(timezone.utc).isoformat()
    with connection() as database:
        cursor = database.execute(
            """
            INSERT INTO ict_trades_journal 
            (date, instrument, direction, setup, timeframe, entry_price, sl_price, tp_price, 
             risk_amount, result, rr_ratio, drawdown, pnl, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (date, instrument, direction, setup, timeframe, entry_price, sl_price, tp_price,
             risk_amount, result, rr_ratio, drawdown, pnl, notes, created_at),
        )
        return {
            "id": cursor.lastrowid,
            "date": date,
            "instrument": instrument,
            "direction": direction,
            "setup": setup,
            "timeframe": timeframe,
            "entry_price": entry_price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "risk_amount": risk_amount,
            "result": result,
            "rr_ratio": rr_ratio,
            "drawdown": drawdown,
            "pnl": pnl,
            "notes": notes,
            "created_at": created_at,
        }


def list_ict_trade_journal(
    instrument: str | None = None,
    result: str | None = None,
    limit: int = 100
) -> list[dict]:
    """List ICT/SMC trade journal entries with optional filters."""
    with connection() as database:
        query = "SELECT * FROM ict_trades_journal"
        params = []
        conditions = []
        
        if instrument:
            conditions.append("instrument = ?")
            params.append(instrument)
        if result:
            conditions.append("result = ?")
            params.append(result)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY date DESC LIMIT ?"
        params.append(limit)
        
        rows = database.execute(query, params).fetchall()
        return [
            {
                "id": row["id"],
                "date": row["date"],
                "instrument": row["instrument"],
                "direction": row["direction"],
                "setup": row["setup"],
                "timeframe": row["timeframe"],
                "entry_price": row["entry_price"],
                "sl_price": row["sl_price"],
                "tp_price": row["tp_price"],
                "risk_amount": row["risk_amount"],
                "result": row["result"],
                "rr_ratio": row["rr_ratio"],
                "drawdown": row["drawdown"],
                "pnl": row["pnl"],
                "notes": row["notes"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]


def get_ict_trade_statistics() -> dict:
    """Get ICT/SMC trade statistics according to cahier des charges requirements."""
    with connection() as database:
        # Basic counts
        total_trades = database.execute("SELECT COUNT(*) FROM ict_trades_journal").fetchone()[0]
        winning_trades = database.execute("SELECT COUNT(*) FROM ict_trades_journal WHERE result = 'win'").fetchone()[0]
        losing_trades = database.execute("SELECT COUNT(*) FROM ict_trades_journal WHERE result = 'loss'").fetchone()[0]
        
        # PnL statistics
        pnl_rows = database.execute("SELECT pnl FROM ict_trades_journal WHERE pnl IS NOT NULL").fetchall()
        if pnl_rows:
            pnls = [row["pnl"] for row in pnl_rows]
            total_pnl = sum(pnls)
            avg_win = sum([p for p in pnls if p > 0]) / len([p for p in pnls if p > 0]) if any(p > 0 for p in pnls) else 0
            avg_loss = sum([p for p in pnls if p < 0]) / len([p for p in pnls if p < 0]) if any(p < 0 for p in pnls) else 0
        else:
            total_pnl = 0
            avg_win = 0
            avg_loss = 0
        
        # Win rate
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Profit factor
        gross_profit = sum([row["pnl"] for row in database.execute("SELECT pnl FROM ict_trades_journal WHERE result = 'win' AND pnl IS NOT NULL").fetchall()])
        gross_loss = abs(sum([row["pnl"] for row in database.execute("SELECT pnl FROM ict_trades_journal WHERE result = 'loss' AND pnl IS NOT NULL").fetchall()]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Drawdown
        max_drawdown = 0
        dd_rows = database.execute("SELECT drawdown FROM ict_trades_journal WHERE drawdown IS NOT NULL").fetchall()
        if dd_rows:
            max_drawdown = min([row["drawdown"] for row in dd_rows])  # Most negative drawdown
        
        # Performance by instrument
        instrument_performance = {}
        for instrument in ["EURUSD", "GBPUSD", "XAUUSD"]:
            inst_trades = database.execute("SELECT result, pnl FROM ict_trades_journal WHERE instrument = ?", (instrument,)).fetchall()
            if inst_trades:
                inst_pnl = sum([row["pnl"] for row in inst_trades if row["pnl"] is not None])
                inst_wins = sum([1 for row in inst_trades if row["result"] == "win"])
                instrument_performance[instrument] = {
                    "trades": len(inst_trades),
                    "pnl": inst_pnl,
                    "wins": inst_wins,
                    "win_rate": inst_wins / len(inst_trades) * 100 if inst_trades else 0,
                }
        
        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown": round(max_drawdown, 2),
            "instrument_performance": instrument_performance,
        }
