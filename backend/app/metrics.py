"""Lightweight Prometheus-compatible metrics for AEGIS AI.

No external dependencies — exports Prometheus text exposition format.
Usage:
    from . import metrics
    metrics.http_requests_total.labels(method="GET", path="/api/v1/dashboard", status="200").inc()
"""

import threading
import time
from collections import defaultdict
from typing import Optional


class Counter:
    """Monotonically increasing counter."""

    def __init__(self, name: str, help_text: str, label_names: tuple[str, ...] = ()):
        self.name = name
        self.help_text = help_text
        self.label_names = label_names
        self._values: dict[tuple, float] = defaultdict(float)
        self._lock = threading.Lock()

    def labels(self, **kwargs) -> "Counter":
        key = tuple(kwargs.get(k, "") for k in self.label_names)
        return _LabelProxy(self, key)

    def _inc(self, key: tuple, value: float = 1.0) -> None:
        with self._lock:
            self._values[key] += value

    def _serialize(self) -> str:
        lines = [f"# HELP {self.name} {self.help_text}", f"# TYPE {self.name} counter"]
        with self._lock:
            for key, val in sorted(self._values.items()):
                if self.label_names:
                    labels = ",".join(f'{k}="{v}"' for k, v in zip(self.label_names, key))
                    lines.append(f'{self.name}{{{labels}}} {val}')
                else:
                    lines.append(f"{self.name} {val}")
        return "\n".join(lines)


class Gauge:
    """Gauge that can go up and down."""

    def __init__(self, name: str, help_text: str, label_names: tuple[str, ...] = ()):
        self.name = name
        self.help_text = help_text
        self.label_names = label_names
        self._values: dict[tuple, float] = defaultdict(float)
        self._lock = threading.Lock()

    def labels(self, **kwargs) -> "Gauge":
        key = tuple(kwargs.get(k, "") for k in self.label_names)
        return _LabelProxy(self, key)

    def _set(self, key: tuple, value: float) -> None:
        with self._lock:
            self._values[key] = value

    def _dec(self, key: tuple, value: float = 1.0) -> None:
        with self._lock:
            self._values[key] -= value

    def _serialize(self) -> str:
        lines = [f"# HELP {self.name} {self.help_text}", f"# TYPE {self.name} gauge"]
        with self._lock:
            for key, val in sorted(self._values.items()):
                if self.label_names:
                    labels = ",".join(f'{k}="{v}"' for k, v in zip(self.label_names, key))
                    lines.append(f'{self.name}{{{labels}}} {val}')
                else:
                    lines.append(f"{self.name} {val}")
        return "\n".join(lines)


class Histogram:
    """Histogram for tracking value distributions."""

    BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(self, name: str, help_text: str, label_names: tuple[str, ...] = ()):
        self.name = name
        self.help_text = help_text
        self.label_names = label_names
        self._counts: dict[tuple, dict] = defaultdict(lambda: {"count": 0, "sum": 0.0, "buckets": defaultdict(int)})
        self._lock = threading.Lock()

    def labels(self, **kwargs) -> "Histogram":
        key = tuple(kwargs.get(k, "") for k in self.label_names)
        return _LabelProxy(self, key)

    def _observe(self, key: tuple, value: float) -> None:
        with self._lock:
            bucket_counts = self._counts[key]["buckets"]
            bucket_counts["_count"] += 1
            bucket_counts["_sum"] += value
            for b in self.BUCKETS:
                if value <= b:
                    bucket_counts[b] += 1

    def _serialize(self) -> str:
        lines = [f"# HELP {self.name} {self.help_text}", f"# TYPE {self.name} histogram"]
        with self._lock:
            for key, data in sorted(self._counts.items()):
                bc = data["buckets"]
                count = bc.get("_count", 0)
                total = bc.get("_sum", 0.0)
                if self.label_names:
                    labels = ",".join(f'{k}="{v}"' for k, v in zip(self.label_names, key))
                    base = f'{self.name}{{{labels}}}'
                else:
                    base = self.name
                cumulative = 0
                for b in self.BUCKETS:
                    cumulative += bc.get(b, 0)
                    lines.append(f'{base}_bucket{{le="{b}"}} {cumulative}')
                lines.append(f"{base}_bucket{{le=\"+Inf\"}} {count}")
                lines.append(f"{base}_count {count}")
                lines.append(f"{base}_sum {total}")
        return "\n".join(lines)


class _LabelProxy:
    """Allows chained .labels(...).method() calls."""

    def __init__(self, metric, key: tuple):
        self._metric = metric
        self._key = key

    def inc(self, value: float = 1.0):
        self._metric._inc(self._key, value)

    def set(self, value: float):
        self._metric._set(self._key, value)

    def dec(self, value: float = 1.0):
        self._metric._dec(self._key, value)

    def observe(self, value: float):
        self._metric._observe(self._key, value)


# ─── Application Metrics ───────────────────────────────────────────

http_requests_total = Counter(
    "aegis_http_requests_total",
    "Total HTTP requests",
    label_names=("method", "path", "status"),
)

http_request_duration_seconds = Histogram(
    "aegis_http_request_duration_seconds",
    "HTTP request latency in seconds",
    label_names=("method", "path"),
)

db_query_duration_seconds = Histogram(
    "aegis_db_query_duration_seconds",
    "Database query latency in seconds",
    label_names=("operation",),
)

engine_cycles_total = Counter(
    "aegis_engine_cycles_total",
    "Total autonomous engine cycles completed",
)

engine_errors_total = Counter(
    "aegis_engine_errors_total",
    "Total engine errors",
    label_names=("task",),
)

trades_total = Counter(
    "aegis_trades_total",
    "Total trades executed",
    label_names=("side", "symbol", "mode"),
)

active_positions = Gauge(
    "aegis_active_positions",
    "Number of active positions",
)

portfolio_equity = Gauge(
    "aegis_portfolio_equity_usd",
    "Current portfolio equity in USD",
)

ws_connections_active = Gauge(
    "aegis_ws_connections_active",
    "Number of active WebSocket connections",
)

engine_uptime_seconds = Gauge(
    "aegis_engine_uptime_seconds",
    "Engine uptime in seconds",
)

# ─── Metrics Registry ──────────────────────────────────────────────

_ALL_METRICS: list = [
    http_requests_total,
    http_request_duration_seconds,
    db_query_duration_seconds,
    engine_cycles_total,
    engine_errors_total,
    trades_total,
    active_positions,
    portfolio_equity,
    ws_connections_active,
    engine_uptime_seconds,
]


def serialize() -> str:
    """Serialize all metrics in Prometheus text exposition format."""
    header = "# AEGIS AI Quant metrics\n"
    parts = [m._serialize() for m in _ALL_METRICS]
    return header + "\n\n".join(parts) + "\n"
