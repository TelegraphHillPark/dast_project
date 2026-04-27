"""
Async Crawler — discovers URLs, forms, and JS routes in a target web application.
Builds an application graph stored per-scan in PostgreSQL (via scan.config).
"""
from __future__ import annotations

import asyncio
import logging
import re
from collections import deque
from dataclasses import dataclass, field
from urllib.parse import urljoin, urldefrag, urlparse

import httpx
from bs4 import BeautifulSoup

from app.crawler.auth_manager import AuthManager

logger = logging.getLogger("dast.crawler")

# Matches path literals in JS: fetch('/api/...'), href: '/path', url: '/path'
_JS_PATH_RE = re.compile(
    r"""(?:fetch|axios(?:\.\w+)?|href|url|src)\s*[=:(,]\s*['"`](/[^'"`\s?#]{1,200})['"`]"""
)


@dataclass
class CrawlResult:
    visited_urls: set[str] = field(default_factory=set)
    forms: list[dict] = field(default_factory=list)
    js_routes: list[str] = field(default_factory=list)
    graph: dict[str, list[str]] = field(default_factory=dict)


class AsyncCrawler:
    def __init__(
        self,
        target_url: str,
        max_depth: int,
        excluded_paths: list[str],
        auth_config: dict,
        stop_event: asyncio.Event | None = None,
    ):
        self.target_url = target_url.rstrip("/")
        self.max_depth = max_depth
        self.excluded_paths = [p for p in excluded_paths if p]
        self.auth_manager = AuthManager(auth_config)
        self.stop_event = stop_event or asyncio.Event()
        self.result = CrawlResult()
        self._base = urlparse(self.target_url)

    # ── scope helpers ──────────────────────────────────────────────────────────

    def _in_scope(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.netloc and parsed.netloc != self._base.netloc:
            return False
        for excluded in self.excluded_paths:
            if parsed.path.startswith(excluded):
                return False
        return parsed.scheme in ("http", "https", "")

    @staticmethod
    def _normalize(url: str) -> str:
        url, _ = urldefrag(url)
        return url.rstrip("/") or "/"

    # ── main crawl loop ────────────────────────────────────────────────────────

    async def crawl(self) -> CrawlResult:
        client = self.auth_manager.build_client()

        async with client:
            if self.auth_manager.auth_type == "form":
                await self.auth_manager.perform_form_login(client)

            queue: deque[tuple[str, int]] = deque([(self.target_url, 0)])

            while queue and not self.stop_event.is_set():
                url, depth = queue.popleft()
                url = self._normalize(url)

                if url in self.result.visited_urls:
                    continue
                if not self._in_scope(url):
                    continue
                if depth > self.max_depth:
                    continue

                self.result.visited_urls.add(url)
                logger.debug("[depth=%d] crawling %s", depth, url)

                html = await self._fetch(client, url)
                if html is None:
                    continue

                links = self._extract_links(url, html)
                self.result.graph[url] = links
                self.result.forms.extend(self._extract_forms(url, html))

                for route in self._extract_js_routes(html):
                    full = urljoin(self.target_url, route)
                    if full not in self.result.js_routes:
                        self.result.js_routes.append(full)

                for link in links:
                    if link not in self.result.visited_urls:
                        queue.append((link, depth + 1))

        return self.result

    # ── HTTP fetch ─────────────────────────────────────────────────────────────

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str | None:
        try:
            resp = await client.get(url)
            ct = resp.headers.get("content-type", "")
            if "text/html" not in ct and "text/plain" not in ct:
                return None
            return resp.text
        except Exception as exc:
            logger.debug("fetch failed %s: %s", url, exc)
            return None

    # ── extractors ────────────────────────────────────────────────────────────

    def _extract_links(self, base_url: str, html: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        seen: set[str] = set()
        links: list[str] = []

        candidates = [
            tag["href"]
            for tag in soup.find_all(["a", "link"], href=True)
        ] + [
            form.get("action", base_url)
            for form in soup.find_all("form")
        ]

        for href in candidates:
            full = self._normalize(urljoin(base_url, href))
            if full not in seen and self._in_scope(full):
                seen.add(full)
                links.append(full)

        return links

    def _extract_forms(self, page_url: str, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        forms = []
        for form in soup.find_all("form"):
            action = urljoin(page_url, form.get("action", page_url))
            method = form.get("method", "GET").upper()
            inputs = [
                {
                    "name": inp.get("name"),
                    "type": inp.get("type", "text"),
                    "value": inp.get("value", ""),
                }
                for inp in form.find_all(["input", "textarea", "select"])
                if inp.get("name")
            ]
            forms.append({"action": action, "method": method, "inputs": inputs, "page": page_url})
        return forms

    def _extract_js_routes(self, html: str) -> list[str]:
        return list({m.group(1) for m in _JS_PATH_RE.finditer(html)})
