"""Centralized safe defaults for the paper-trading MVP."""

import os

MODE = os.getenv("AEGIS_MODE", "paper")
API_ORIGINS = os.getenv("AEGIS_CORS_ORIGINS", "http://localhost:5173").split(",")
PAPER_CAPITAL = float(os.getenv("AEGIS_INITIAL_CAPITAL", "10000"))
ADMIN_TOKEN = os.getenv("AEGIS_ADMIN_TOKEN", "")

# Gemini AI keys (rotate through 4 keys)
GEMINI_API_KEYS = []
for i in range(1, 5):
    k = os.getenv(f"GEMINI_API_KEY_{i}", "")
    if k:
        GEMINI_API_KEYS.append(k)
if not GEMINI_API_KEYS:
    single = os.getenv("GEMINI_API_KEY", "")
    if single:
        GEMINI_API_KEYS.append(single)

if MODE != "paper":
    raise RuntimeError("AEGIS only supports paper mode in this build.")
