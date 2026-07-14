"""Centralized safe defaults for the paper-trading MVP."""

import os

MODE = os.getenv("AEGIS_MODE", "paper")
API_ORIGINS = os.getenv("AEGIS_CORS_ORIGINS", "http://localhost:5173").split(",")
PAPER_CAPITAL = float(os.getenv("AEGIS_INITIAL_CAPITAL", "10000"))
ADMIN_TOKEN = os.getenv("AEGIS_ADMIN_TOKEN", "")
if MODE != "paper":
    raise RuntimeError("AEGIS only supports paper mode in this build.")
