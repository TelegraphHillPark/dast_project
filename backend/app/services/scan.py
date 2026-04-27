from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
import redis.asyncio as aioredis

from app.config import settings
from app.core.uuid7 import uuid7_str
from app.models.scan import Scan, ScanStatus
from app.models.vulnerability import Vulnerability
from app.schemas.scan import ScanCreate


async def create_scan(data: ScanCreate, owner_id: str, db: AsyncSession) -> Scan:
    scan = Scan(
        id=uuid7_str(),
        owner_id=owner_id,
        target_url=data.target_url,
        max_depth=data.max_depth,
        timeout_seconds=data.timeout_seconds,
        excluded_paths=data.excluded_paths,
        config=data.auth_config.model_dump(),
        status=ScanStatus.pending,
    )
    db.add(scan)
    await db.flush()
    await db.refresh(scan)

    r = aioredis.from_url(settings.REDIS_URL)
    try:
        await r.rpush("scan_queue", scan.id)
    finally:
        await r.aclose()

    return scan


async def get_scan(scan_id: str, owner_id: str, db: AsyncSession) -> Scan:
    result = await db.execute(
        select(Scan).where(Scan.id == scan_id, Scan.owner_id == owner_id)
    )
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


async def list_scans(owner_id: str, db: AsyncSession) -> list[Scan]:
    result = await db.execute(
        select(Scan).where(Scan.owner_id == owner_id).order_by(Scan.created_at.desc())
    )
    return list(result.scalars().all())


async def pause_scan(scan_id: str, owner_id: str, db: AsyncSession) -> Scan:
    scan = await get_scan(scan_id, owner_id, db)
    if scan.status != ScanStatus.running:
        raise HTTPException(status_code=400, detail="Scan is not running")
    scan.status = ScanStatus.paused
    return scan


async def resume_scan(scan_id: str, owner_id: str, db: AsyncSession) -> Scan:
    scan = await get_scan(scan_id, owner_id, db)
    if scan.status != ScanStatus.paused:
        raise HTTPException(status_code=400, detail="Scan is not paused")
    scan.status = ScanStatus.pending

    r = aioredis.from_url(settings.REDIS_URL)
    try:
        await r.rpush("scan_queue", scan.id)
    finally:
        await r.aclose()

    return scan


async def count_vulns(scan_id: str, db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count(Vulnerability.id)).where(Vulnerability.scan_id == scan_id)
    )
    return result.scalar() or 0
