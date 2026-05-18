"""
Lightweight per-scan event logger that writes to Redis.
Frontend polls GET /scans/{id}/logs to read the list.
"""
from __future__ import annotations

from datetime import datetime, timezone

import redis.asyncio as aioredis

from app.config import settings

_MAX_ENTRIES = 1000
_TTL_SECONDS = 60 * 60 * 6   # 6 hours


def _redis_key(scan_id: str) -> str:
    return f"scan_logs:{scan_id}"


async def log(scan_id: str, message: str, phase: str = "info") -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    entry = f"[{ts}] [{phase.upper()}] {message}"
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        key = _redis_key(scan_id)
        await r.rpush(key, entry)
        await r.ltrim(key, -_MAX_ENTRIES, -1)
        await r.expire(key, _TTL_SECONDS)
    finally:
        await r.aclose()


async def get_logs(scan_id: str, offset: int = 0) -> list[str]:
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        raw = await r.lrange(_redis_key(scan_id), offset, -1)
        return [e.decode() for e in raw]
    finally:
        await r.aclose()


async def clear_logs(scan_id: str) -> None:
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        await r.delete(_redis_key(scan_id))
    finally:
        await r.aclose()
