"""
Tests for /api/scans/* endpoints.
"""
import pytest
from httpx import AsyncClient


REGISTER_URL = "/api/auth/register"
LOGIN_URL = "/api/auth/login"
SCANS_URL = "/api/scans"

_USER_COUNTER = 0


async def _register_and_login(client: AsyncClient) -> str:
    """Create a unique user and return an access token."""
    global _USER_COUNTER
    _USER_COUNTER += 1
    user = {
        "email": f"scanuser{_USER_COUNTER}@example.com",
        "username": f"scanuser{_USER_COUNTER}",
        "password": "TestPass123!",
    }
    await client.post(REGISTER_URL, json=user)
    r = await client.post(LOGIN_URL, json={
        "email": user["email"],
        "password": user["password"],
    })
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_create_scan(client: AsyncClient):
    token = await _register_and_login(client)
    r = await client.post(
        SCANS_URL,
        json={"target_url": "http://example.com", "max_depth": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["target_url"] == "http://example.com"
    assert data["status"] == "pending"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_scan_invalid_url(client: AsyncClient):
    token = await _register_and_login(client)
    r = await client.post(
        SCANS_URL,
        json={"target_url": "not-a-url", "max_depth": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_scan_requires_auth(client: AsyncClient):
    r = await client.post(
        SCANS_URL,
        json={"target_url": "http://example.com"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_scans_empty(client: AsyncClient):
    token = await _register_and_login(client)
    r = await client.get(SCANS_URL, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_list_scans_returns_own_only(client: AsyncClient):
    token_a = await _register_and_login(client)
    token_b = await _register_and_login(client)

    # User A creates a scan
    await client.post(
        SCANS_URL,
        json={"target_url": "http://example.com"},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # User B should see 0 scans
    r = await client.get(SCANS_URL, headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 200
    assert len(r.json()) == 0


@pytest.mark.asyncio
async def test_get_scan_not_found(client: AsyncClient):
    token = await _register_and_login(client)
    r = await client.get(
        f"{SCANS_URL}/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_scan_another_users(client: AsyncClient):
    token_a = await _register_and_login(client)
    token_b = await _register_and_login(client)

    create_r = await client.post(
        SCANS_URL,
        json={"target_url": "http://example.com"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    scan_id = create_r.json()["id"]

    # User B cannot access user A's scan
    r = await client.get(
        f"{SCANS_URL}/{scan_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code == 404
