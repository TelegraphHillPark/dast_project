from fastapi import APIRouter

router = APIRouter(prefix="/api/scans", tags=["scans"])


@router.post("")
async def create_scan():
    """Stub — будет реализован в Sprint 3."""
    return {"detail": "not implemented"}


@router.get("/{scan_id}")
async def get_scan(scan_id: str):
    """Stub — будет реализован в Sprint 3."""
    return {"detail": "not implemented", "scan_id": scan_id}


@router.post("/{scan_id}/pause")
async def pause_scan(scan_id: str):
    return {"detail": "not implemented", "scan_id": scan_id}


@router.post("/{scan_id}/resume")
async def resume_scan(scan_id: str):
    return {"detail": "not implemented", "scan_id": scan_id}


@router.get("/{scan_id}/report")
async def get_report_json(scan_id: str):
    """Stub — будет реализован в Sprint 5."""
    return {"detail": "not implemented", "scan_id": scan_id}


@router.get("/{scan_id}/report.pdf")
async def get_report_pdf(scan_id: str):
    """Stub — будет реализован в Sprint 5."""
    return {"detail": "not implemented", "scan_id": scan_id}
