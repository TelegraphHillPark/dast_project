"""
Orchestrator — manages the lifecycle of a single scan.
Runs the crawler and persists the crawl graph to scan.config.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.crawler.crawler import AsyncCrawler
from app.models.scan import Scan, ScanStatus

logger = logging.getLogger("dast.orchestrator")


class ScanOrchestrator:
    def __init__(self, scan: Scan, db: AsyncSession):
        self.scan = scan
        self.db = db
        self._stop_event = asyncio.Event()

    def stop(self) -> None:
        """Signal the crawler to stop (called externally when scan is paused)."""
        self._stop_event.set()

    async def run(self) -> None:
        scan = self.scan

        try:
            scan.status = ScanStatus.running
            scan.started_at = datetime.now(timezone.utc)
            await self.db.commit()

            logger.info("Scan %s started → %s", scan.id, scan.target_url)

            crawler = AsyncCrawler(
                target_url=scan.target_url,
                max_depth=scan.max_depth,
                excluded_paths=scan.excluded_paths or [],
                auth_config=scan.config or {},
                stop_event=self._stop_event,
            )

            result = await asyncio.wait_for(
                crawler.crawl(),
                timeout=float(scan.timeout_seconds),
            )

            # Merge crawl stats into scan.config (preserve auth config)
            scan.config = {
                **(scan.config or {}),
                "crawl_stats": {
                    "visited_count": len(result.visited_urls),
                    "forms_count": len(result.forms),
                    "js_routes_count": len(result.js_routes),
                    # Keep at most 500 URLs to avoid bloating the JSON column
                    "visited_urls": sorted(result.visited_urls)[:500],
                    "js_routes": result.js_routes[:100],
                    "forms": result.forms[:200],
                },
            }

            if self._stop_event.is_set():
                scan.status = ScanStatus.paused
            else:
                scan.status = ScanStatus.finished
                scan.finished_at = datetime.now(timezone.utc)

            await self.db.commit()
            logger.info(
                "Scan %s → status=%s visited=%d forms=%d",
                scan.id, scan.status, len(result.visited_urls), len(result.forms),
            )

        except asyncio.TimeoutError:
            scan.status = ScanStatus.failed
            scan.finished_at = datetime.now(timezone.utc)
            await self.db.commit()
            logger.warning("Scan %s timed out", scan.id)

        except Exception as exc:
            scan.status = ScanStatus.failed
            scan.finished_at = datetime.now(timezone.utc)
            await self.db.commit()
            logger.error("Scan %s failed: %s", scan.id, exc, exc_info=True)
