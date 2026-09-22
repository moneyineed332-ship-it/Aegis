"""AEGIS AI Quant — Vercel Serverless API entry point.

This wraps the FastAPI app for Vercel's Python runtime.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Serverless guardrails (must be set BEFORE importing app.main):
# - No autonomous engine (infinite asyncio tasks don't survive serverless).
# - SQLite in /tmp (only writable dir on Vercel; data is ephemeral here —
#   use Fly.io + persistent volume for the real trading engine).
os.environ.setdefault("AEGIS_ENGINE_ENABLED", "false")
os.environ.setdefault("AEGIS_DB_PATH", "/tmp/aegis.db")

from app.main import app

# Vercel expects a WSGI-compatible `app` or ASGI-compatible `app`
# FastAPI is ASGI-compatible, so this works directly
