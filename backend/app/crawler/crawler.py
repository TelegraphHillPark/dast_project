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
        on_visit=None,
    ):
        self.target_url = target_url.rstrip("/")
        self.max_depth = max_depth
        self.excluded_paths = [p for p in excluded_paths if p]
        self.auth_manager = AuthManager(auth_config)
        self.stop_event = stop_event or asyncio.Event()
        self.result = CrawlResult()
        self._base = urlparse(self.target_url)
        self._on_visit = on_visit

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
                ok = await self.auth_manager.perform_form_login(client)
                if self._on_visit:
                    msg = "Вход выполнен успешно" if ok else "⚠ Вход не удался — проверь логин/пароль и URL страницы входа"
                    await self._on_visit(f"[auth] {msg}", -1)

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
                if self._on_visit:
                    await self._on_visit(url, depth)

                html = await self._fetch(client, url)
                if html is None:
                    continue

                links = self._extract_links(url, html)
                self.result.graph[url] = links
                forms = self._extract_forms(url, html)
                self.result.forms.extend(forms)
                await self._fetch_js_files(client, url, html)

                # For GET forms: probe with a neutral value to discover param URLs
                for form in forms:
                    if form.get("method", "GET") == "GET":
                        probe_url = self._build_get_probe(form, url)
                        if probe_url and probe_url not in self.result.visited_urls:
                            if depth + 1 <= self.max_depth:
                                queue.append((probe_url, depth + 1))

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

    async def _fetch_js_files(self, client: httpx.AsyncClient, base_url: str, html: str) -> None:
        """Fetch inline <script src> files and harvest API routes from their content."""
        soup = BeautifulSoup(html, "lxml")
        script_srcs = [
            tag["src"] for tag in soup.find_all("script", src=True)
        ]
        for src in script_srcs[:20]:
            full_src = urljoin(base_url, src)
            if not self._in_scope(full_src):
                continue
            try:
                resp = await client.get(full_src)
                ct = resp.headers.get("content-type", "")
                if "javascript" not in ct and "text/plain" not in ct:
                    continue
                for route in self._extract_js_routes(resp.text):
                    full_route = urljoin(self.target_url, route)
                    if full_route not in self.result.js_routes:
                        self.result.js_routes.append(full_route)
                    # Add as a visitable URL so param-bearing paths get attacked
                    if "?" in full_route and full_route not in self.result.visited_urls:
                        self.result.visited_urls.add(full_route)
            except Exception:
                continue

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

    def _build_get_probe(self, form: dict, base_url: str) -> str | None:
        """Submit a GET form with neutral probe values to discover ?param=value URLs.

        Submit-type inputs are included with their declared value so that apps
        that gate SQL execution on isset($_REQUEST['Submit']) are exercised correctly.
        """
        from urllib.parse import urlencode, urlparse, parse_qs
        fields = [
            f for f in form.get("inputs", [])
            if f.get("name") and f.get("type") not in ("hidden", "file")
        ]
        if not fields:
            return None
        action = form.get("action", base_url)
        parsed = urlparse(action)
        existing = parse_qs(parsed.query, keep_blank_values=True)
        params = {}
        for f in fields:
            if f.get("type") == "submit":
                params[f["name"]] = f.get("value") or "Submit"
            else:
                params[f["name"]] = f.get("value") or "1"
        merged = {**existing, **{k: [v] for k, v in params.items()}}
        from urllib.parse import urlencode as _enc
        qs = _enc({k: v[0] for k, v in merged.items()})
        return parsed._replace(query=qs).geturl()
