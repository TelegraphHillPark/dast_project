from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.core.deps import get_current_user
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


def _build_pdf_html(scan, vulns: list) -> str:
    sev_colors = {
        "critical": "#7c3aed", "high": "#dc2626",
        "medium": "#d97706", "low": "#2563eb", "info": "#64748b",
    }
    vuln_labels = {
        "sqli": "SQL-инъекция", "xss": "XSS", "ssrf": "SSRF",
        "open_redirect": "Открытый редирект", "header_injection": "Header Injection",
    }

    by_severity: dict[str, int] = {}
    for v in vulns:
        by_severity[v.severity.value] = by_severity.get(v.severity.value, 0) + 1

    rows = []
    for v in vulns:
        sev = v.severity.value
        color = sev_colors.get(sev, "#64748b")
        confidence = (v.evidence or {}).get("confidence", "-")
        label = vuln_labels.get(v.vuln_type.value, v.vuln_type.value)
        rec = v.recommendation or "-"
        param = v.parameter or "-"
        row = (
            "<tr>"
            f"<td>{label}</td>"
            f'<td><span style="color:{color};font-weight:bold">{sev.upper()}</span></td>'
            f"<td>{confidence}</td>"
            f'<td style="font-family:monospace;font-size:10px;word-break:break-all">{v.url}</td>'
            f"<td>{param}</td>"
            f"<td>{v.method}</td>"
            f'<td style="font-size:10px">{rec}</td>'
            "</tr>"
        )
        rows.append(row)

    summary_rows = "".join(
        f"<tr><td>{k.upper()}</td><td>{cnt}</td></tr>"
        for k, cnt in sorted(by_severity.items())
    )
    summary_total = f"<tr style='font-weight:bold'><td>Всего</td><td>{len(vulns)}</td></tr>"

    crawl_stats = scan.config.get("crawl_stats") if scan.config else None
    crawl_section = ""
    if crawl_stats:
        vc = crawl_stats.get("visited_count", 0)
        fc = crawl_stats.get("forms_count", 0)
        jc = crawl_stats.get("js_routes_count", 0)
        crawl_section = (
            "<h2>Статистика сканирования</h2>"
            "<table><tr><th>Параметр</th><th>Значение</th></tr>"
            f"<tr><td>Страниц обойдено</td><td>{vc}</td></tr>"
            f"<tr><td>Форм найдено</td><td>{fc}</td></tr>"
            f"<tr><td>JS-маршрутов</td><td>{jc}</td></tr>"
            "</table>"
        )

    started_line = ""
    if scan.started_at:
        started_line = f"<strong>Начало:</strong> {scan.started_at.strftime('%d.%m.%Y %H:%M:%S UTC')}<br>"
    finished_line = ""
    if scan.finished_at:
        finished_line = f"<strong>Завершено:</strong> {scan.finished_at.strftime('%d.%m.%Y %H:%M:%S UTC')}<br>"

    if rows:
        vuln_section = (
            "<table>"
            "<tr><th>Тип</th><th>Критичность</th><th>Уверенность</th>"
            "<th>URL</th><th>Параметр</th><th>Метод</th><th>Рекомендация</th></tr>"
            + "".join(rows)
            + "</table>"
        )
    else:
        vuln_section = "<p>Уязвимостей не обнаружено.</p>"

    vuln_count = len(vulns)
    return (
        "<!DOCTYPE html><html lang='ru'><head><meta charset='UTF-8'><style>"
        "body{font-family:Arial,sans-serif;font-size:12px;color:#1e293b;margin:40px}"
        "h1{font-size:22px;color:#0f172a;border-bottom:2px solid #1e40af;padding-bottom:8px}"
        "h2{font-size:16px;color:#1e293b;margin-top:28px}"
        "table{width:100%;border-collapse:collapse;margin-top:10px}"
        "th{background:#1e293b;color:#f1f5f9;padding:7px 10px;text-align:left;font-size:11px}"
        "td{padding:6px 10px;border-bottom:1px solid #e2e8f0;vertical-align:top}"
        "tr:nth-child(even) td{background:#f8fafc}"
        ".meta{color:#64748b;font-size:11px;margin-bottom:20px}"
        "</style></head><body>"
        "<h1>Отчёт о безопасности DAST</h1>"
        "<div class='meta'>"
        f"<strong>Цель:</strong> {scan.target_url}<br>"
        f"<strong>ID:</strong> {scan.id}<br>"
        f"<strong>Статус:</strong> {scan.status.value}<br>"
        f"{started_line}{finished_line}"
        f"<strong>Глубина обхода:</strong> {scan.max_depth}"
        "</div>"
        f"{crawl_section}"
        "<h2>Итоги по уязвимостям</h2>"
        "<table style='width:auto'>"
        "<tr><th>Критичность</th><th>Количество</th></tr>"
        f"{summary_rows}{summary_total}"
        "</table>"
        f"<h2>Детальный список уязвимостей ({vuln_count})</h2>"
        f"{vuln_section}"
        "</body></html>"
    )


@router.get("/{scan_id}/report.pdf")
async def get_report_pdf(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """PDF report via WeasyPrint."""
    from weasyprint import HTML

    scan = await get_scan(scan_id, current_user.id, db)

    vulns_result = await db.execute(
        select(Vulnerability)
        .where(Vulnerability.scan_id == scan_id)
        .order_by(Vulnerability.severity, Vulnerability.created_at)
    )
    vulns = list(vulns_result.scalars().all())

    html_content = _build_pdf_html(scan, vulns)
    pdf_bytes = HTML(string=html_content).write_pdf()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="scan_{scan_id}_report.pdf"'},
    )
