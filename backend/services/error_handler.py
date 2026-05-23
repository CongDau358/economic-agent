"""
backend/services/error_handler.py
Backward-compat redirect → dùng backend.exception_handlers thay thế.
File này chỉ giữ để không break import cũ nếu có.
"""
from backend.exception_handlers import register_exception_handlers, _status_label

__all__ = ["register_exception_handlers", "_status_label"]