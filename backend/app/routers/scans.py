from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Request


from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.database import get_db
from app.models.user import User
from app.models.vulnerability import Vulnerability
from app.schemas.scan import ScanCreate, ScanListItem, ScanOut, VulnOut
from app.services.scan import (
    cancel_scan,
    count_vulns,
    create_scan,
    get_scan,
    list_scans,
    pause_scan,
    resume_scan,
)

router = APIRouter(prefix="/api/scans", tags=["scans"])


@router.post("", response_model=ScanListItem, status_code=201)
@limiter.limit("10/minute")
async def create_scan_endpoint(
    request: Request,
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


@router.post("/{scan_id}/cancel", response_model=ScanListItem)
async def cancel_scan_endpoint(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scan = await cancel_scan(scan_id, current_user.id, db)
    return ScanListItem(
        id=scan.id,
        target_url=scan.target_url,
        status=scan.status,
        max_depth=scan.max_depth,
        created_at=scan.created_at,
        started_at=scan.started_at,
        finished_at=scan.finished_at,
    )


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


@router.get("/{scan_id}/logs")
async def get_scan_logs(
    scan_id: str,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return scan log lines from Redis. Use ?offset=N to get only new lines."""
    await get_scan(scan_id, current_user.id, db)  # ownership check
    from app.crawler.scan_logger import get_logs
    lines = await get_logs(scan_id, offset)
    return {"lines": lines, "total": offset + len(lines)}


@router.get("/{scan_id}/report")
async def get_report_json(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """JSON report: scan metadata + all vulnerabilities + summary."""
    scan = await get_scan(scan_id, current_user.id, db)

    vulns_result = await db.execute(
        select(Vulnerability)
        .where(Vulnerability.scan_id == scan_id)
        .order_by(Vulnerability.severity, Vulnerability.created_at)
    )
    vulns = list(vulns_result.scalars().all())

    by_severity: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for v in vulns:
        by_severity[v.severity.value] = by_severity.get(v.severity.value, 0) + 1
        by_type[v.vuln_type.value] = by_type.get(v.vuln_type.value, 0) + 1

    return {
        "scan_id": scan.id,
        "target_url": scan.target_url,
        "status": scan.status.value,
        "max_depth": scan.max_depth,
        "created_at": scan.created_at.isoformat(),
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "finished_at": scan.finished_at.isoformat() if scan.finished_at else None,
        "crawl_stats": scan.config.get("crawl_stats") if scan.config else None,
        "summary": {
            "total_vulnerabilities": len(vulns),
            "by_severity": by_severity,
            "by_type": by_type,
        },
        "vulnerabilities": [
            {
                "id": v.id,
                "vuln_type": v.vuln_type.value,
                "severity": v.severity.value,
                "confidence": (v.evidence or {}).get("confidence", "unknown"),
                "url": v.url,
                "parameter": v.parameter,
                "method": v.method,
                "payload": v.payload,
                "evidence": v.evidence,
                "recommendation": v.recommendation,
                "found_at": v.created_at.isoformat(),
            }
            for v in vulns
        ],
    }


