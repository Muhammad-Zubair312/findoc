"""Auth flow: register -> login -> me -> refresh -> logout, plus failure modes."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from jose import jwt

from app.config import settings

pytestmark = pytest.mark.asyncio


def _unique_email() -> str:
    import uuid

    return f"user-{uuid.uuid4().hex[:12]}@example.com"


async def test_full_auth_flow(client: AsyncClient) -> None:
    email = _unique_email()
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": "Ada Lovelace"},
    )
    assert register_resp.status_code == 201
    body = register_resp.json()
    assert body["user"]["email"] == email
    assert "access_token" in body
    assert "refresh_token" in body
    assert "findoc_access" in client.cookies
    assert "findoc_refresh" in client.cookies

    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}
    )
    assert login_resp.status_code == 200

    me_resp = await client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == email

    old_refresh_cookie = client.cookies.get("findoc_refresh")
    refresh_resp = await client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 200
    new_access_token = refresh_resp.json()["access_token"]

    me_resp_2 = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access_token}"}
    )
    assert me_resp_2.status_code == 200

    # Refresh token rotation: the old refresh token must be revoked and no longer usable.
    rotated_refresh_cookie = client.cookies.get("findoc_refresh")
    client.cookies.set("findoc_refresh", old_refresh_cookie)
    reuse_old_refresh = await client.post("/api/v1/auth/refresh")
    assert reuse_old_refresh.status_code == 401
    client.cookies.set("findoc_refresh", rotated_refresh_cookie)

    logout_resp = await client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 200
    assert logout_resp.json() == {"success": True}

    # Refresh token was revoked on logout — a second refresh must fail.
    refresh_after_logout = await client.post("/api/v1/auth/refresh")
    assert refresh_after_logout.status_code == 401


async def test_register_rejects_weak_password(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": _unique_email(), "password": "short1", "full_name": "Bob"},
    )
    assert resp.status_code == 422


async def test_register_rejects_bad_email(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "password123", "full_name": "Bob"},
    )
    assert resp.status_code == 422


async def test_register_duplicate_email_conflict(client: AsyncClient) -> None:
    email = _unique_email()
    payload = {"email": email, "password": "password123", "full_name": "Bob"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


async def test_wrong_password_returns_generic_401(client: AsyncClient) -> None:
    email = _unique_email()
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": "Bob"},
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "wrongpassword1"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "invalid_credentials"


async def test_login_nonexistent_user_returns_same_generic_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": _unique_email(), "password": "whatever123"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "invalid_credentials"


async def test_expired_token_returns_token_expired_code(client: AsyncClient) -> None:
    expired_payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "type": "access",
        "iat": datetime.now(UTC) - timedelta(minutes=60),
        "exp": datetime.now(UTC) - timedelta(minutes=30),
    }
    expired_token = jwt.encode(
        expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "token_expired"


async def test_me_without_auth_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_login_rate_limit_fires(client: AsyncClient) -> None:
    email = _unique_email()
    for _ in range(10):
        resp = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "wrongpassword1"}
        )
        assert resp.status_code == 401

    limited_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "wrongpassword1"}
    )
    assert limited_resp.status_code == 429
    assert "Retry-After" in limited_resp.headers


async def test_cookies_not_secure_in_dev(client: AsyncClient) -> None:
    assert settings.ENV == "dev"
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": _unique_email(), "password": "password123", "full_name": "Bob"},
    )
    set_cookie_headers = resp.headers.get_list("set-cookie")
    assert any("findoc_access" in h for h in set_cookie_headers)
    for h in set_cookie_headers:
        assert "httponly" in h.lower()
        assert "secure" not in h.lower()
