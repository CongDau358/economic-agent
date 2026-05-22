"""
backend/exception_handlers.py  (TẠO MỚI)

Global exception handlers — đăng ký vào app trong main.py:

    from .exception_handlers import register_exception_handlers
    register_exception_handlers(app)
"""

from __future__ import annotations

import traceback

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .services.logger import get_logger

log = get_logger("economic_agent.exceptions")


def register_exception_handlers(app: FastAPI) -> None:

    # ── 422 Validation error ──────────────────────────────────────────────────
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        errors = []
        for err in exc.errors():
            field = " → ".join(str(x) for x in err["loc"])
            errors.append({"field": field, "msg": err["msg"], "type": err["type"]})

        log.warning(
            "validation_error",
            extra={"path": request.url.path, "errors": errors},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Dữ liệu đầu vào không hợp lệ",
                "details": errors,
            },
        )

    # ── 404 / 40x HTTP errors ─────────────────────────────────────────────────
    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        log.warning(
            "http_error",
            extra={"path": request.url.path, "status": exc.status_code, "detail": exc.detail},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": _status_label(exc.status_code),
                "message": exc.detail,
            },
        )

    # ── 500 Unhandled exception ───────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        tb = traceback.format_exc()
        log.error(
            "unhandled_error",
            extra={
                "path": request.url.path,
                "method": request.method,
                "error": str(exc),
                "traceback": tb,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Lỗi server nội bộ. Vui lòng thử lại sau.",
            },
        )


def _status_label(code: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        429: "RATE_LIMITED",
        500: "INTERNAL_SERVER_ERROR",
    }.get(code, f"HTTP_{code}")