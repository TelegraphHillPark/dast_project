"""
Shared pytest fixtures.

Uses in-memory SQLite for the database and mocks Redis so tests run
without any external services.
"""
import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── Env vars BEFORE any app import ────────────────────────────────────────────
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-only-32ch")
os.environ.setdefault("UPLOADS_DIR", "/tmp/dast_test_uploads")
os.makedirs(os.environ["UPLOADS_DIR"], exist_ok=True)

from app.database import Base, get_db  # noqa: E402
from app.main import app               # noqa: E402
from app.core.limiter import limiter   # noqa: E402

# ── Shared in-memory SQLite engine ────────────────────────────────────────────

_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
_SessionFactory = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def _reset_state():
    """Recreate DB tables and clear rate-limiter counters before each test."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    limiter._storage.reset()
    yield


@pytest_asyncio.fixture()
async def client():
    """HTTP test client: SQLite DB + Redis mocked out."""

    async def _get_test_db():
        async with _SessionFactory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # Mock Redis so scan creation doesn't need a real Redis server
    mock_redis = AsyncMock()
    mock_redis.rpush = AsyncMock(return_value=1)
    mock_redis.aclose = AsyncMock()

    app.dependency_overrides[get_db] = _get_test_db

    with patch("app.services.scan.aioredis.from_url", return_value=mock_redis):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac

    app.dependency_overrides.clear()
