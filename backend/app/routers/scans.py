from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.vulnerability import Vulnerability
from app.schemas.scan import ScanCreate, ScanListItem, ScanOut, VulnOut
from app.services.scan import (
    count_vulns,
    create_scan,
    get_scan,
    list_scans,
    pause_scan,
    resume_scan,
)

router = APIRouter(prefix="/api/scans", tags=["scans"])


@router.post("", response_model=ScanListItem, status_code=201)
async def create_scan_endpoint(
    data: ScanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scan = await create_scan(data, current_user.id, db)
    return ScanListItem(
        id=scan.id,
        target_url=scan.target_url,
        status=scan.status,
        max_depth=scan.max_depth,
        created_at=scan.created_at,
        vuln_count=0,
    )


@router.get("", response_model=list[ScanListItem])
async def list_scans_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scans = await list_scans(current_user.id, db)
    result = []
    for scan in scans:
        result.append(
            ScanListItem(
                id=scan.id,
                target_url=scan.target_url,
                status=scan.status,
                max_depth=scan.max_depth,
                created_at=scan.created_at,
                started_at=scan.started_at,
                finished_at=scan.finished_at,
                vuln_count=await count_vulns(scan.id, db),
            )
        )
    return result


@router.get("/{scan_id}", response_model=ScanOut)
async def get_scan_endpoint(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scan = await get_scan(scan_id, current_user.id, db)
    vulns_result = await db.execute(
        select(Vulnerability)
        .where(Vulnerability.scan_id == scan_id)
        .order_by(Vulnerability.created_at.desc())
    )
    vulns = list(vulns_result.scalars().all())
    return ScanOut(
        id=scan.id,
        target_url=scan.target_url,
        status=scan.status,
        max_depth=scan.max_depth,
        timeout_seconds=scan.timeout_seconds,
        excluded_paths=scan.excluded_paths or [],
        created_at=scan.created_at,
        started_at=scan.started_at,
        finished_at=scan.finished_at,
        vuln_count=len(vulns),
        vulnerabilities=[VulnOut.model_validate(v) for v in vulns],
        crawl_stats=scan.config.get("crawl_stats") if scan.config else None,
    )


@router.post("/{scan_id}/pause", response_model=ScanListItem)
async def pause_scan_endpoint(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scan = await pause_scan(scan_id, current_user.id, db)
    return ScanListItem(
        id=scan.id,
        target_url=scan.target_url,
        status=scan.status,
        max_depth=scan.max_depth,
        created_at=scan.created_at,
        started_at=scan.started_at,
    )


@router.post("/{scan_id}/resume", response_model=ScanListItem)
async def resume_scan_endpoint(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scan = await resume_scan(scan_id, current_user.id, db)
    return ScanListItem(
        id=scan.id,
        target_url=scan.target_url,
        status=scan.status,
        max_depth=scan.max_depth,
        created_at=scan.created_at,
        started_at=scan.started_at,
    )


@router.get("/{scan_id}/report")
async def get_report_json(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stub — Sprint 5."""
    return {"detail": "not implemented", "scan_id": scan_id}


@router.get("/{scan_id}/report.pdf")
async def get_report_pdf(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stub — Sprint 5."""
    return {"detail": "not implemented", "scan_id": scan_id}
