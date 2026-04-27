"""
Worker — background scan processor.
Polls Redis queue 'scan_queue' and runs ScanOrchestrator for each pending scan.
Supports pause signaling: when the API sets scan.status=paused in the DB,
check_pause_signals() detects it and calls orchestrator.stop().
"""
from __future__ import annotations

import asyncio
import logging

import redis.asyncio as aioredis
from sqlalchemy import select

from app.config import settings
from app.crawler.orchestrator import ScanOrchestrator
from app.database import AsyncSessionLocal
from app.models.scan import Scan, ScanStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("dast.worker")

# scan_id → running orchestrator
_running: dict[str, ScanOrchestrator] = {}


async def process_scan(scan_id: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Scan).where(Scan.id == scan_id))
        scan = result.scalar_one_or_none()

        if not scan:
            logger.warning("Scan %s not found in DB", scan_id)
            return

        if scan.status not in (ScanStatus.pending, ScanStatus.running):
            logger.info("Scan %s has status=%s — skipping", scan_id, scan.status)
            return

        orchestrator = ScanOrchestrator(scan, db)
        _running[scan_id] = orchestrator
        try:
            await orchestrator.run()
        finally:
            _running.pop(scan_id, None)


async def check_pause_signals() -> None:
    """Detect scans paused via API and stop their running orchestrators."""
    if not _running:
        return
    async with AsyncSessionLocal() as db:
        for scan_id, orch in list(_running.items()):
            result = await db.execute(select(Scan).where(Scan.id == scan_id))
            scan = result.scalar_one_or_none()
            if scan and scan.status == ScanStatus.paused:
                logger.info("Pause signal detected for scan %s", scan_id)
                orch.stop()


async def main() -> None:
    r = aioredis.from_url(settings.REDIS_URL)
    logger.info("Worker started — listening on 'scan_queue'")

    try:
        while True:
            try:
                item = await r.blpop("scan_queue", timeout=2)
                if item:
                    _, scan_id_bytes = item
                    scan_id = scan_id_bytes.decode()
                    logger.info("Dequeued scan %s", scan_id)
                    asyncio.create_task(process_scan(scan_id))

                await check_pause_signals()

            except Exception as exc:
                logger.error("Worker loop error: %s", exc, exc_info=True)
                await asyncio.sleep(5)
    finally:
        await r.aclose()


if __name__ == "__main__":
    asyncio.run(main())
