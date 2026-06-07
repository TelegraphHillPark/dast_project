"""
Tests for /api/auth/* endpoints.
"""
import pytest
from httpx import AsyncClient


REGISTER_URL = "/api/auth/register"
LOGIN_URL = "/api/auth/login"
REFRESH_URL = "/api/auth/refresh"
LOGOUT_URL = "/api/auth/logout"

USER = {
    "email": "testuser@example.com",
    "username": "testuser",
    "password": "TestPass123!",
}


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    r = await client.post(REGISTER_URL, json=USER)
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == USER["email"]
    assert data["username"] == USER["username"]
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    await client.post(REGISTER_URL, json=USER)
    r = await client.post(REGISTER_URL, json=USER)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    r = await client.post(REGISTER_URL, json={**USER, "password": "123"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient):
    r = await client.post(REGISTER_URL, json={**USER, "email": "not-an-email"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post(REGISTER_URL, json=USER)
    r = await client.post(LOGIN_URL, json={
        "email": USER["email"],
        "password": USER["password"],
    })
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post(REGISTER_URL, json=USER)
    r = await client.post(LOGIN_URL, json={
        "email": USER["email"],
        "password": "wrongpassword",
    })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client: AsyncClient):
    r = await client.post(LOGIN_URL, json={
        "email": "nobody@example.com",
        "password": "whatever",
    })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    await client.post(REGISTER_URL, json=USER)
    login = await client.post(LOGIN_URL, json={
        "email": USER["email"],
        "password": USER["password"],
    })
    refresh_token = login.json()["refresh_token"]

    r = await client.post(REFRESH_URL, json={"refresh_token": refresh_token})
    assert r.status_code == 200
    assert "access_token" in r.json()


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    await client.post(REGISTER_URL, json=USER)
    login = await client.post(LOGIN_URL, json={
        "email": USER["email"],
        "password": USER["password"],
    })
    refresh_token = login.json()["refresh_token"]

    r = await client.post(LOGOUT_URL, json={"refresh_token": refresh_token})
    assert r.status_code == 200

    # Refresh with spent token should fail
    r2 = await client.post(REFRESH_URL, json={"refresh_token": refresh_token})
    assert r2.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient):
    r = await client.get("/api/users/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_with_token(client: AsyncClient):
    await client.post(REGISTER_URL, json=USER)
    login = await client.post(LOGIN_URL, json={
        "email": USER["email"],
        "password": USER["password"],
    })
    token = login.json()["access_token"]

    r = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == USER["email"]
