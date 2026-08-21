"""Centralized structured logging configuration for AEGIS AI.

Provides JSON-formatted structured logging with configurable levels,
request ID tracking, and performance context.
"""

import json
import logging
import sys
import time
from datetime import datetime, timezone
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")


class JSONFormatter(logging.Formatter):
    """Outputs log records as single-line JSON for easy parsing."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
            "correlation_id": correlation_id_var.get(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "path"):
            log_entry["path"] = record.path
        return json.dumps(log_entry, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable format for development console output."""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[1;31m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = datetime.now().strftime("%H:%M:%S")
        rid = request_id_var.get()
        prefix = f"{color}{ts} [{record.levelname}]{self.RESET} {record.name}"
        if rid != "-":
            prefix += f" [{rid[:8]}]"
        return f"{prefix}: {record.getMessage()}"


def setup_logging(level: str = "INFO", fmt: str = "auto") -> None:
    """Configure application-wide logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        fmt: Format mode - "json" for structured, "text" for colored, "auto" for text in dev.
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    for handler in root.handlers[:]:
        root.removeHandler(handler)

    if fmt == "auto":
        fmt = "text" if sys.stderr.isatty() else "json"

    if fmt == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    root.addHandler(handler)

    noisy_loggers = [
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "starlette",
        "httpx",
        "ccxt",
    ]
    for name in noisy_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)


class RequestTimer:
    """Context manager that logs elapsed time on completion."""

    def __init__(self, method: str, path: str, status_code: int = 0):
        self.method = method
        self.path = path
        self.status_code = status_code
        self.start = 0.0
        self.logger = logging.getLogger("aegis.access")

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        elapsed_ms = round((time.perf_counter() - self.start) * 1000, 1)
        record = self.logger.makeRecord(
            self.logger.name,
            logging.INFO,
            "",
            0,
            f"{self.method} {self.path} {self.status_code} {elapsed_ms}ms",
            (),
            None,
        )
        record.duration_ms = elapsed_ms
        record.status_code = self.status_code
        record.method = self.method
        record.path = self.path
        self.logger.handle(record)
        return False
