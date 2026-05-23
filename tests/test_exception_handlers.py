"""
tests/test_exception_handlers.py
Tests cho global exception handlers.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from backend.exception_handlers import register_exception_handlers


# ── Test app với các route gây lỗi ───────────────────────────────────────────

@pytest.fixture(scope="module")
def error_app():
    """Mini FastAPI app chỉ để test exception handlers."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/ok")
    def ok():
        return {"status": "ok"}

    @app.get("/http-error/{code}")
    def http_error(code: int):
        raise HTTPException(status_code=code, detail=f"Test error {code}")

    @app.get("/unhandled")
    def unhandled():
        raise RuntimeError("Unexpected crash")

    @app.post("/validate")
    def validate(body: dict):
        return body

    return TestClient(app, raise_server_exceptions=False)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestHTTPExceptionHandler:

    def test_404_returns_json(self, error_app):
        r = error_app.get("/http-error/404")
        assert r.status_code == 404
        body = r.json()
        assert body["error"] == "NOT_FOUND"
        assert "message" in body

    def test_400_returns_json(self, error_app):
        r = error_app.get("/http-error/400")
        assert r.status_code == 400
        body = r.json()
        assert body["error"] == "BAD_REQUEST"
        assert "message" in body

    def test_403_returns_json(self, error_app):
        r = error_app.get("/http-error/403")
        assert r.status_code == 403
        assert r.json()["error"] == "FORBIDDEN"

    def test_401_returns_json(self, error_app):
        r = error_app.get("/http-error/401")
        assert r.status_code == 401
        assert r.json()["error"] == "UNAUTHORIZED"

    def test_409_returns_json(self, error_app):
        r = error_app.get("/http-error/409")
        assert r.status_code == 409
        assert r.json()["error"] == "CONFLICT"

    def test_response_has_error_and_message_keys(self, error_app):
        r = error_app.get("/http-error/400")
        body = r.json()
        assert "error" in body
        assert "message" in body

    def test_200_not_affected(self, error_app):
        r = error_app.get("/ok")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestUnhandledExceptionHandler:

    def test_500_returns_json(self, error_app):
        r = error_app.get("/unhandled")
        assert r.status_code == 500
        body = r.json()
        assert body["error"] == "INTERNAL_SERVER_ERROR"
        assert "message" in body

    def test_500_does_not_expose_traceback(self, error_app):
        r = error_app.get("/unhandled")
        body_str = r.text
        # Traceback không được leak ra response body
        assert "Traceback" not in body_str
        assert "RuntimeError" not in body_str


class TestStatusLabel:

    def test_known_codes(self):
        from backend.exception_handlers import _status_label
        assert _status_label(400) == "BAD_REQUEST"
        assert _status_label(401) == "UNAUTHORIZED"
        assert _status_label(403) == "FORBIDDEN"
        assert _status_label(404) == "NOT_FOUND"
        assert _status_label(409) == "CONFLICT"
        assert _status_label(429) == "RATE_LIMITED"
        assert _status_label(500) == "INTERNAL_SERVER_ERROR"

    def test_unknown_code_fallback(self):
        from backend.exception_handlers import _status_label
        assert _status_label(418) == "HTTP_418"
        assert _status_label(503) == "HTTP_503"


class TestValidationErrorHandler:

    def test_missing_field_returns_422_json(self, mock_heavy_services):
        from backend.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=False)

        # Thiếu field bắt buộc 'company'
        r = client.post("/predict", json={
            "financial_signals": [],
            "sentiment_signals": [],
            "macro_signals": [],
        })
        assert r.status_code == 422
        body = r.json()
        assert body["error"] == "VALIDATION_ERROR"
        assert "details" in body
        assert len(body["details"]) > 0

    def test_wrong_type_returns_422_json(self, mock_heavy_services):
        from backend.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=False)

        r = client.post("/predict", json={
            "company": "VNM",
            "top_k": "not_an_int",  # wrong type
        })
        assert r.status_code == 422

    def test_details_contain_field_and_msg(self, mock_heavy_services):
        from backend.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=False)

        r = client.post("/ask", json={"question": "ab"})  # min_length=3
        assert r.status_code == 422
        body = r.json()
        if body.get("details"):
            detail = body["details"][0]
            assert "field" in detail
            assert "msg" in detail"""
tests/test_exception_handlers.py
Tests cho global exception handlers.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from backend.exception_handlers import register_exception_handlers


# ── Test app với các route gây lỗi ───────────────────────────────────────────

@pytest.fixture(scope="module")
def error_app():
    """Mini FastAPI app chỉ để test exception handlers."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/ok")
    def ok():
        return {"status": "ok"}

    @app.get("/http-error/{code}")
    def http_error(code: int):
        raise HTTPException(status_code=code, detail=f"Test error {code}")

    @app.get("/unhandled")
    def unhandled():
        raise RuntimeError("Unexpected crash")

    @app.post("/validate")
    def validate(body: dict):
        return body

    return TestClient(app, raise_server_exceptions=False)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestHTTPExceptionHandler:

    def test_404_returns_json(self, error_app):
        r = error_app.get("/http-error/404")
        assert r.status_code == 404
        body = r.json()
        assert body["error"] == "NOT_FOUND"
        assert "message" in body

    def test_400_returns_json(self, error_app):
        r = error_app.get("/http-error/400")
        assert r.status_code == 400
        body = r.json()
        assert body["error"] == "BAD_REQUEST"
        assert "message" in body

    def test_403_returns_json(self, error_app):
        r = error_app.get("/http-error/403")
        assert r.status_code == 403
        assert r.json()["error"] == "FORBIDDEN"

    def test_401_returns_json(self, error_app):
        r = error_app.get("/http-error/401")
        assert r.status_code == 401
        assert r.json()["error"] == "UNAUTHORIZED"

    def test_409_returns_json(self, error_app):
        r = error_app.get("/http-error/409")
        assert r.status_code == 409
        assert r.json()["error"] == "CONFLICT"

    def test_response_has_error_and_message_keys(self, error_app):
        r = error_app.get("/http-error/400")
        body = r.json()
        assert "error" in body
        assert "message" in body

    def test_200_not_affected(self, error_app):
        r = error_app.get("/ok")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestUnhandledExceptionHandler:

    def test_500_returns_json(self, error_app):
        r = error_app.get("/unhandled")
        assert r.status_code == 500
        body = r.json()
        assert body["error"] == "INTERNAL_SERVER_ERROR"
        assert "message" in body

    def test_500_does_not_expose_traceback(self, error_app):
        r = error_app.get("/unhandled")
        body_str = r.text
        # Traceback không được leak ra response body
        assert "Traceback" not in body_str
        assert "RuntimeError" not in body_str


class TestStatusLabel:

    def test_known_codes(self):
        from backend.exception_handlers import _status_label
        assert _status_label(400) == "BAD_REQUEST"
        assert _status_label(401) == "UNAUTHORIZED"
        assert _status_label(403) == "FORBIDDEN"
        assert _status_label(404) == "NOT_FOUND"
        assert _status_label(409) == "CONFLICT"
        assert _status_label(429) == "RATE_LIMITED"
        assert _status_label(500) == "INTERNAL_SERVER_ERROR"

    def test_unknown_code_fallback(self):
        from backend.exception_handlers import _status_label
        assert _status_label(418) == "HTTP_418"
        assert _status_label(503) == "HTTP_503"


class TestValidationErrorHandler:

    def test_missing_field_returns_422_json(self, mock_heavy_services):
        from backend.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=False)

        # Thiếu field bắt buộc 'company'
        r = client.post("/predict", json={
            "financial_signals": [],
            "sentiment_signals": [],
            "macro_signals": [],
        })
        assert r.status_code == 422
        body = r.json()
        assert body["error"] == "VALIDATION_ERROR"
        assert "details" in body
        assert len(body["details"]) > 0

    def test_wrong_type_returns_422_json(self, mock_heavy_services):
        from backend.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=False)

        r = client.post("/predict", json={
            "company": "VNM",
            "top_k": "not_an_int",  # wrong type
        })
        assert r.status_code == 422

    def test_details_contain_field_and_msg(self, mock_heavy_services):
        from backend.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=False)

        r = client.post("/ask", json={"question": "ab"})  # min_length=3
        assert r.status_code == 422
        body = r.json()
        if body.get("details"):
            detail = body["details"][0]
            assert "field" in detail
            assert "msg" in detail