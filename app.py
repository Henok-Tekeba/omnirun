"""Vercel Python entrypoint.

Vercel loads the ASGI ``app`` from this root-level file and serves the whole
FastAPI application as one function. Local development still uses
``uvicorn api.main:app``.
"""

from api.main import app

__all__ = ["app"]
