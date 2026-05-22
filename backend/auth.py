"""
backend/auth.py
API-key authentication middleware for FastAPI.

Usage in main.py:
    from backend.auth import require_api_key
    
    @app.post("/predict")
    async def predict(request: PredictRequest, _=Depends(require_api_key)):
        ...
"""

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from backend.config import get_settings

# Header name the client must send, e.g.:  X-API-Key: my-secret-key
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str | None = Security(API_KEY_HEADER)) -> str:
    """
    FastAPI dependency that validates the X-API-Key header.
    If auth is disabled (AUTH_ENABLED=false in .env), all requests pass through.
    """
    settings = get_settings()

    if not settings.auth_enabled:
        return "anonymous"

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key not in settings.valid_api_keys:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return api_key


# ── Optional: request-level logging ──────────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time
import logging

logger = logging.getLogger("economic_agent.access")


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Logs method, path, status code, and latency for every request."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s → %d (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response