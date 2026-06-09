"""
Orchestrator — manages the full lifecycle of a single scan:
  Phase 1: Crawl (discover URLs, forms, JS routes)
  Phase 2: Attack (inject payloads, analyze responses, persist vulnerabilities)
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.crawler.analyzers import (
    Baseline,
    HeuristicAnalyzer,
    SecurityHeadersAnalyzer,
    SignatureAnalyzer,
    build_curl,
)
from app.crawler.auth_manager import AuthManager
from app.crawler.crawler import AsyncCrawler, CrawlResult
from app.crawler.payload_engine import PayloadEngine
from app.crawler.scan_logger import log as slog
from app.models.scan import Scan, ScanStatus
from app.models.vulnerability import Vulnerability

logger = logging.getLogger("dast.orchestrator")

# Cap total attack requests per scan to avoid runaway scans
_MAX_GET_ATTACK = 800
_MAX_POST_ATTACK = 400


class ScanOrchestrator:
    def __init__(self, scan: Scan, db: AsyncSession):
        self.scan = scan
        self.db = db
        self._stop_event = asyncio.Event()
        self._cancelled = False

    def stop(self, cancelled: bool = False) -> None:
        self._cancelled = cancelled
        self._stop_event.set()

    async def run(self) -> None:
        scan = self.scan

        try:
            scan.status = ScanStatus.running
            scan.started_at = datetime.now(timezone.utc)
            await self.db.commit()

            logger.info("Scan %s started → %s", scan.id, scan.target_url)
            await slog(scan.id, f"Сканирование запущено → {scan.target_url}", "init")

            # ── Phase 1: Crawl ──────────────────────────────────────────────
            await slog(scan.id, "Фаза 1: обход сайта (crawler)…", "crawl")
            async def _on_visit(url: str, depth: int) -> None:
                if depth < 0:
                    await slog(scan.id, url, "crawl")
                else:
                    await slog(scan.id, f"[глубина {depth}] {url}", "crawl")

            crawler = AsyncCrawler(
                target_url=scan.target_url,
                max_depth=scan.max_depth,
                excluded_paths=scan.excluded_paths or [],
                auth_config=scan.config or {},
                stop_event=self._stop_event,
                on_visit=_on_visit,
            )

            result = await asyncio.wait_for(
                crawler.crawl(),
                timeout=float(scan.timeout_seconds) * 0.6,
            )

            scan.config = {
                **(scan.config or {}),
                "crawl_stats": {
                    "visited_count": len(result.visited_urls),
                    "forms_count": len(result.forms),
                    "js_routes_count": len(result.js_routes),
                    "visited_urls": sorted(result.visited_urls)[:500],
                    "js_routes": result.js_routes[:100],
                    "forms": result.forms[:200],
                },
            }
            await self.db.commit()

            logger.info(
                "Scan %s crawl done — visited=%d forms=%d",
                scan.id, len(result.visited_urls), len(result.forms),
            )
            await slog(
                scan.id,
                f"Обход завершён: страниц={len(result.visited_urls)}, "
                f"форм={len(result.forms)}, JS-маршрутов={len(result.js_routes)}",
                "crawl",
            )
            for url in sorted(result.visited_urls)[:50]:
                await slog(scan.id, f"  ✓ {url}", "crawl")
            if len(result.visited_urls) > 50:
                await slog(scan.id, f"  … и ещё {len(result.visited_urls) - 50} страниц", "crawl")

            # ── Phase 1.5: Security headers check ──────────────────────────
            if not self._stop_event.is_set():
                await slog(scan.id, "Фаза 1.5: проверка заголовков безопасности…", "attack")
                await self._run_header_checks(scan, result)

            # ── Phase 2: Attack ─────────────────────────────────────────────
            if not self._stop_event.is_set():
                await slog(scan.id, "Фаза 2: атака (payload injection)…", "attack")
                await self._run_attacks(scan, result)

            if self._stop_event.is_set():
                # The API already wrote paused/cancelled to the DB — don't overwrite.
                # (Overwriting would race with a concurrent resume that sets status=pending.)
                # Just flush any pending vulnerability rows.
                await self.db.commit()
                msg = (
                    "Сканирование остановлено пользователем."
                    if self._cancelled
                    else "Сканирование приостановлено."
                )
                await slog(scan.id, msg, "info")
                logger.info(
                    "Scan %s stopped (cancelled=%s), status left to API",
                    scan.id, self._cancelled,
                )
            else:
                scan.status = ScanStatus.finished
                scan.finished_at = datetime.now(timezone.utc)
                await self.db.commit()
                await slog(scan.id, "Сканирование завершено.", "info")
                logger.info("Scan %s finished with status=%s", scan.id, scan.status)

        except asyncio.TimeoutError:
            scan.status = ScanStatus.failed
            scan.finished_at = datetime.now(timezone.utc)
            await self.db.commit()
            await slog(scan.id, "Превышен лимит времени (timeout).", "error")
            logger.warning("Scan %s timed out", scan.id)

        except Exception as exc:
            scan.status = ScanStatus.failed
            scan.finished_at = datetime.now(timezone.utc)
            await self.db.commit()
            await slog(scan.id, f"Ошибка: {exc}", "error")
            logger.error("Scan %s failed: %s", scan.id, exc, exc_info=True)

    # ── Private: attack phase ──────────────────────────────────────────────────

    async def _run_attacks(self, scan: Scan, result: CrawlResult) -> None:
        import os as _os
        from sqlalchemy import select as _select
        from app.models.wordlist import Wordlist

        wl_result = await self.db.execute(
            _select(Wordlist).where(
                Wordlist.owner_id == scan.owner_id,
                Wordlist.is_builtin == False,  # noqa: E712
            )
        )
        user_wordlists = wl_result.scalars().all()
        extra_paths = [w.file_path for w in user_wordlists if _os.path.exists(w.file_path)]
        if extra_paths:
            await slog(scan.id, f"Пользовательские словари ({len(extra_paths)}): {[_os.path.basename(p) for p in extra_paths]}", "attack")

        engine = PayloadEngine(extra_wordlist_paths=extra_paths)
        sig = SignatureAnalyzer()
        heur = HeuristicAnalyzer()

        # Exclude login URL from attack targets to avoid flooding auth endpoints
        login_url = ((scan.config or {}).get("login_url") or "").rstrip("/")

        get_targets = engine.generate_get_targets(result.visited_urls)[:_MAX_GET_ATTACK]
        post_targets = [
            t for t in engine.generate_post_targets(result.forms)
            if t.action and not (login_url and t.action.rstrip("/") == login_url)
        ][:_MAX_POST_ATTACK]

        total = len(get_targets) + len(post_targets)
        logger.info("Scan %s attack phase — %d GET + %d POST targets", scan.id, len(get_targets), len(post_targets))
        await slog(
            scan.id,
            f"Целей для атаки: {len(get_targets)} GET + {len(post_targets)} POST = {total} всего",
            "attack",
        )

        seen: set[tuple] = set()
        vuln_count = 0
        tested = 0

        # Build an authenticated attack client using the same auth config as the crawler.
        # For form login we need follow_redirects=True to complete the login flow,
        # then we freeze the session cookies into a follow_redirects=False client.
        auth_manager = AuthManager(scan.config or {})
        attack_cookies: dict = {}
        attack_headers: dict = {"User-Agent": "DAST-Analyzer/0.1"}
        attack_auth = None

        if auth_manager.auth_type == "form":
            # Do login with a temp client to harvest session cookies
            temp = auth_manager.build_client()
            async with temp:
                login_ok = await auth_manager.perform_form_login(temp)
                attack_cookies = dict(temp.cookies)
            if login_ok:
                await slog(scan.id, f"Атака: авторизовано через form login ({len(attack_cookies)} куков)", "attack")
            else:
                await slog(
                    scan.id,
                    "⚠ Атака: form login не удался (неверный пароль или URL входа). "
                    "Атака будет вестись без аутентификации — результаты ненадёжны. "
                    "Подсказка: если использовалась страница /vulnerabilities/csrf, "
                    "она могла изменить пароль. Сбросьте БД и исключите этот путь из скана.",
                    "error",
                )
                logger.warning("Scan %s: attack-phase form login failed", scan.id)
        elif auth_manager.auth_type == "cookie" and auth_manager.cookie:
            for pair in auth_manager.cookie.split(";"):
                if "=" in pair:
                    k, _, v = pair.strip().partition("=")
                    attack_cookies[k.strip()] = v.strip()
        elif auth_manager.auth_type == "bearer" and auth_manager.bearer_token:
            attack_headers["Authorization"] = f"Bearer {auth_manager.bearer_token}"
        elif auth_manager.auth_type == "basic" and auth_manager.username:
            attack_auth = (auth_manager.username, auth_manager.password or "")

        async with httpx.AsyncClient(
            verify=False,
            timeout=12.0,
            follow_redirects=True,
            cookies=attack_cookies,
            headers=attack_headers,
            auth=attack_auth,
        ) as client:
            # GET targets
            for target in get_targets:
                if self._stop_event.is_set():
                    break
                try:
                    baseline = await self._baseline_get(client, target.url)
                    if baseline is None:
                        continue

                    t0 = time.monotonic()
                    resp = await client.get(target.test_url)
                    elapsed = time.monotonic() - t0
                except Exception as e:
                    logger.debug("GET target error %s: %s", target.url, e)
                    continue

                tested += 1
                key = (target.url, target.param, target.vuln_type)
                if key in seen:
                    continue

                if tested % 20 == 0:
                    await slog(
                        scan.id,
                        f"GET [{tested}/{total}] тестирую {target.vuln_type.value} param={target.param} @ {target.url}",
                        "attack",
                    )

                finding = sig.analyze(target.vuln_type, target.payload, resp)
                if not finding:
                    finding = heur.analyze(target.vuln_type, target.payload, baseline, resp, elapsed)

                if finding:
                    seen.add(key)
                    await slog(
                        scan.id,
                        f"⚠ НАЙДЕНО {finding.vuln_type.value.upper()} [{finding.severity.value}] "
                        f"param={target.param} payload={target.payload!r} @ {target.url}",
                        "vuln",
                    )
                    self.db.add(Vulnerability(
                        scan_id=scan.id,
                        vuln_type=finding.vuln_type,
                        severity=finding.severity,
                        url=target.url,
                        parameter=target.param,
                        method="GET",
                        payload=target.payload,
                        evidence={
                            **finding.evidence,
                            "confidence": finding.confidence,
                            "request_url": target.test_url,
                            "curl": build_curl(
                                "GET", target.test_url,
                                cookies=attack_cookies,
                                headers={k: v for k, v in attack_headers.items()
                                         if k.lower() != "user-agent"},
                            ),
                            "cwe": finding.cwe,
                            "owasp": finding.owasp,
                        },
                        recommendation=finding.recommendation,
                    ))
                    vuln_count += 1

            # POST targets
            for target in post_targets:
                if self._stop_event.is_set():
                    break
                try:
                    baseline = await self._baseline_post(client, target.action, target.field, target.data)
                    if baseline is None:
                        continue

                    t0 = time.monotonic()
                    resp = await client.post(target.action, data=target.data)
                    elapsed = time.monotonic() - t0
                except Exception as e:
                    logger.debug("POST target error %s: %s", target.action, e)
                    continue

                tested += 1
                key = (target.action, target.field, target.vuln_type)
                if key in seen:
                    continue

                if tested % 20 == 0:
                    await slog(
                        scan.id,
                        f"POST [{tested}/{total}] тестирую {target.vuln_type.value} field={target.field} @ {target.action}",
                        "attack",
                    )

                finding = sig.analyze(target.vuln_type, target.payload, resp)
                if not finding:
                    finding = heur.analyze(target.vuln_type, target.payload, baseline, resp, elapsed)

                if finding:
                    seen.add(key)
                    await slog(
                        scan.id,
                        f"⚠ НАЙДЕНО {finding.vuln_type.value.upper()} [{finding.severity.value}] "
                        f"field={target.field} payload={target.payload!r} @ {target.action}",
                        "vuln",
                    )
                    self.db.add(Vulnerability(
                        scan_id=scan.id,
                        vuln_type=finding.vuln_type,
                        severity=finding.severity,
                        url=target.action,
                        parameter=target.field,
                        method=target.method,
                        payload=target.payload,
                        evidence={
                            **finding.evidence,
                            "confidence": finding.confidence,
                            "request_data": target.data,
                            "curl": build_curl(
                                "POST", target.action,
                                data=target.data,
                                cookies=attack_cookies,
                                headers={k: v for k, v in attack_headers.items()
                                         if k.lower() != "user-agent"},
                            ),
                            "cwe": finding.cwe,
                            "owasp": finding.owasp,
                        },
                        recommendation=finding.recommendation,
                    ))
                    vuln_count += 1

        await self.db.commit()
        await slog(scan.id, f"Атака завершена. Найдено уязвимостей: {vuln_count}", "attack")
        logger.info("Scan %s attack phase done — %d vulnerabilities found", scan.id, vuln_count)

    async def _run_header_checks(self, scan: Scan, result: CrawlResult) -> None:
        """
        Request each visited URL (up to 50) and report missing security headers.
        Deduplicates findings by (url, missing_header) pair.
        """
        from app.models.vulnerability import VulnType, VulnSeverity

        analyzer = SecurityHeadersAnalyzer()
        seen_headers: set[tuple[str, str]] = set()
        found = 0

        urls_to_check = sorted(result.visited_urls)[:50]
        if not urls_to_check:
            urls_to_check = [scan.target_url]

        async with httpx.AsyncClient(verify=False, timeout=10.0, follow_redirects=True) as client:
            for url in urls_to_check:
                if self._stop_event.is_set():
                    break
                try:
                    resp = await client.get(url)
                except Exception as e:
                    logger.debug("Header check failed for %s: %s", url, e)
                    continue

                for finding in analyzer.analyze(url, resp):
                    key = (url, finding.evidence.get("missing_header", ""))
                    if key in seen_headers:
                        continue
                    seen_headers.add(key)
                    self.db.add(Vulnerability(
                        scan_id=scan.id,
                        vuln_type=finding.vuln_type,
                        severity=finding.severity,
                        url=url,
                        parameter=None,
                        method="GET",
                        payload=None,
                        evidence={
                            **finding.evidence,
                            "confidence": finding.confidence,
                            "cwe": finding.cwe,
                            "owasp": finding.owasp,
                        },
                        recommendation=finding.recommendation,
                    ))
                    found += 1

        await self.db.commit()
        await slog(scan.id, f"Проверка заголовков завершена. Найдено: {found}", "attack")

    @staticmethod
    async def _baseline_get(client: httpx.AsyncClient, url: str) -> Baseline | None:
        try:
            t0 = time.monotonic()
            resp = await client.get(url)
            return Baseline(
                status=resp.status_code,
                body_size=len(resp.content),
                elapsed=time.monotonic() - t0,
            )
        except Exception:
            return None

    @staticmethod
    async def _baseline_post(
        client: httpx.AsyncClient, action: str, tested_field: str, data: dict
    ) -> Baseline | None:
        neutral = {k: ("test" if k == tested_field else v) for k, v in data.items()}
        try:
            t0 = time.monotonic()
            resp = await client.post(action, data=neutral)
            return Baseline(
                status=resp.status_code,
                body_size=len(resp.content),
                elapsed=time.monotonic() - t0,
            )
        except Exception:
            return None
