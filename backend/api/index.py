"""Vercel Python entry point. Exposes the FastAPI ASGI app so Vercel's
@vercel/python runtime can serve it. All routes are rewritten here (see
vercel.json), so FastAPI sees the original path."""
import os
import sys

# Ensure the backend package root is importable when Vercel runs this file.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402

# Vercel's ASGI detection looks for a module-level `app`.
