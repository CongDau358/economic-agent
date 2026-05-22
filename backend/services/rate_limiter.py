"""
backend/services/rate_limiter.py  (TẠO MỚI)

Rate limiting theo IP — dùng slowapi (wrapper của limits trên FastAPI).

Cài đặt:
    pip install slowapi

Đăng ký vào main.py:
    from .services.rate_limiter import limiter, rate_limit_handler
    from slowapi.errors import RateLimitExceeded

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

Dùng trong endpoint:
    from .services.rate_limiter import limiter

    @app.post("/predict")
    @limiter.limit("20/minute")
    async def predict(request: Request, payload: PredictRequest, ...):
        ...
"""

from __future__ import annotations

from fastapi import Request, Response
from fastapi.responses import JSONResponse

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded

    limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
        return JSONResponse(
            status_code=429,
            content={
                "error": "RATE_LIMITED",
                "message": f"Quá nhiều request. Giới hạn: {exc.limit}. Thử lại sau.",
                "retry_after": getattr(exc, "retry_after", 60),
            },
            headers={"Retry-After": "60"},
        )

    SLOWAPI_AVAILABLE = True

except ImportError:
    # slowapi chưa cài — tạo stub để không crash khi import
    SLOWAPI_AVAILABLE = False

    class _StubLimiter:
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    limiter = _StubLimiter()

    async def rate_limit_handler(request, exc):
        return JSONResponse(status_code=429, content={"error": "RATE_LIMITED"})


# ── Rate limits theo endpoint ─────────────────────────────────────────────────
#
# Dùng trực tiếp:
#   @limiter.limit(PREDICT_LIMIT)
#   async def predict(...):

UPLOAD_LIMIT   = "10/minute"     # upload nặng, giới hạn thấp
PREDICT_LIMIT  = "30/minute"     # scoring nhẹ hơn
ASK_LIMIT      = "20/minute"     # RAG tốn token
HEALTH_LIMIT   = "120/minute"    # health check thoải mái