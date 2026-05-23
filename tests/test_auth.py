"""
tests/test_auth.py
Tests toàn diện cho auth middleware.
"""

from __future__ import annotations

import os
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from backend.auth import require_api_key, AccessLogMiddleware
from backend.exception_handlers import register_exception_handlers


# ── Helper: tạo app test có auth ─────────────────────────────────────────────

def make_auth_app(auth_enabled: bool = True, api_keys: str = "key1,key2"):
    os.environ["AUTH_ENABLED"] = str(auth_enabled).lower()
    os.environ["API_KEYS"]     = api_keys

    from backend.config import get_settings
    get_settings.cache_clear()

    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(AccessLogMiddleware)

    @app.get("/protected")
    async def protected(_: str = Depends(require_api_key)):
        return {"access": "granted"}

    @app.get("/public")
    async def public():
        return {"access": "public"}

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset_settings():
    yield
    from backend.config import get_settings
    get_settings.cache_clear()


# ── Auth enabled ──────────────────────────────────────────────────────────────

class TestAuthEnabled:

    def test_valid_key_grants_access(self):
        client = make_auth_app()
        r = client.get("/protected", headers={"X-API-Key": "key1"})
        assert r.status_code == 200
        assert r.json()["access"] == "granted"

    def test_second_valid_key_also_works(self):
        client = make_auth_app()
        r = client.get("/protected", headers={"X-API-Key": "key2"})
        assert r.status_code == 200

    def test_invalid_key_returns_403(self):
        client = make_auth_app()
        r = client.get("/protected", headers={"X-API-Key": "wrong-key"})
        assert r.status_code == 403
        assert r.json()["error"] == "FORBIDDEN"

    def test_missing_header_returns_401(self):
        client = make_auth_app()
        r = client.get("/protected")
        assert r.status_code == 401
        assert r.json()["error"] == "UNAUTHORIZED"

    def test_empty_key_returns_401(self):
        client = make_auth_app()
        r = client.get("/protected", headers={"X-API-Key": ""})
        assert r.status_code == 401

    def test_whitespace_key_returns_401_or_403(self):
        client = make_auth_app()
        r = client.get("/protected", headers={"X-API-Key": "   "})
        assert r.status_code in (401, 403)

    def test_case_sensitive_key(self):
        client = make_auth_app(api_keys="MySecretKey")
        # Sai case → từ chối
        r = client.get("/protected", headers={"X-API-Key": "mysecretkey"})
        assert r.status_code == 403
        # Đúng case → cho phép
        r2 = client.get("/protected", headers={"X-API-Key": "MySecretKey"})
        assert r2.status_code == 200

    def test_bearer_prefix_not_supported(self):
        client = make_auth_app()
        r = client.get("/protected", headers={"X-API-Key": "Bearer key1"})
        assert r.status_code == 403  # "Bearer key1" ≠ "key1"


# ── Auth disabled ─────────────────────────────────────────────────────────────

class TestAuthDisabled:

    def test_no_key_passes_when_disabled(self):
        client = make_auth_app(auth_enabled=False)
        r = client.get("/protected")
        assert r.status_code == 200

    def test_wrong_key_still_passes_when_disabled(self):
        client = make_auth_app(auth_enabled=False)
        r = client.get("/protected", headers={"X-API-Key": "garbage"})
        assert r.status_code == 200

    def test_public_endpoint_always_accessible(self):
        client = make_auth_app(auth_enabled=True)
        r = client.get("/public")
        assert r.status_code == 200


# ── Key management ────────────────────────────────────────────────────────────

class TestKeyParsing:

    def test_single_key(self):
        os.environ["API_KEYS"] = "single-key"
        from backend.config import get_settings
        get_settings.cache_clear()
        s = get_settings()
        assert "single-key" in s.valid_api_keys

    def test_multiple_keys_comma_separated(self):
        os.environ["API_KEYS"] = "key-a,key-b,key-c"
        from backend.config import get_settings
        get_settings.cache_clear()
        s = get_settings()
        assert s.valid_api_keys == {"key-a", "key-b", "key-c"}

    def test_keys_with_spaces_stripped(self):
        os.environ["API_KEYS"] = "key-a , key-b , key-c"
        from backend.config import get_settings
        get_settings.cache_clear()
        s = get_settings()
        assert "key-a" in s.valid_api_keys
        assert "key-b" in s.valid_api_keys

    def test_empty_api_keys_string(self):
        os.environ["API_KEYS"] = ""
        from backend.config import get_settings
        get_settings.cache_clear()
        s = get_settings()
        assert s.valid_api_keys == set()

    def test_all_keys_accepted(self):
        client = make_auth_app(api_keys="alpha,beta,gamma")
        for key in ("alpha", "beta", "gamma"):
            r = client.get("/protected", headers={"X-API-Key": key})
            assert r.status_code == 200, f"Key '{key}' should be accepted"


# ── AccessLogMiddleware ───────────────────────────────────────────────────────

class TestAccessLogMiddleware:

    def test_middleware_does_not_block_requests(self):
        client = make_auth_app(auth_enabled=False)
        r = client.get("/public")
        assert r.status_code == 200

    def test_middleware_passes_response_through(self):
        client = make_auth_app(auth_enabled=False)
        r = client.get("/public")
        assert r.json() == {"access": "public"}

    def test_middleware_with_protected_endpoint(self):
        client = make_auth_app(api_keys="test-key")
        r = client.get("/protected", headers={"X-API-Key": "test-key"})
        assert r.status_code == 200