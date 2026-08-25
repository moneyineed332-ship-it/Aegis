"""AEGIS AI Quant — Vercel Serverless API entry point.

This wraps the FastAPI app for Vercel's Python runtime.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.main import app

# Vercel expects a WSGI-compatible `app` or ASGI-compatible `app`
# FastAPI is ASGI-compatible, so this works directly
