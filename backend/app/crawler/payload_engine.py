"""
Payload Engine — loads payloads from built-in and user-uploaded dictionaries,
generates injection targets (GET params, POST form fields) from crawl results.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.models.vulnerability import VulnType

logger = logging.getLogger("dast.payload_engine")

BUILTIN_DIR = Path(__file__).parent.parent / "payloads"

_VULN_FILES: dict[VulnType, str] = {
    VulnType.sqli: "sqli.txt",
    VulnType.xss: "xss.txt",
    VulnType.ssrf: "ssrf.txt",
    VulnType.open_redirect: "open_redirect.txt",
    VulnType.header_injection: "header_injection.txt",
}

MAX_GET_URLS = 100
MAX_POST_FORMS = 50
MAX_FIELDS_PER_FORM = 5
MAX_PAYLOADS_PER_TYPE = 10


@dataclass
class GetTarget:
    url: str
    param: str
    payload: str
    vuln_type: VulnType
    test_url: str


@dataclass
class PostTarget:
    action: str
    method: str
    field: str
    payload: str
    vuln_type: VulnType
    data: dict


class PayloadEngine:
    def __init__(self, extra_wordlist_paths: list[str] | None = None):
        self._extra_paths = extra_wordlist_paths or []
        self._cache: dict[VulnType, list[str]] = {}

    def load_payloads(self, vuln_type: VulnType) -> list[str]:
        if vuln_type in self._cache:
            return self._cache[vuln_type]

        payloads: list[str] = []

        fname = _VULN_FILES.get(vuln_type)
        if fname:
            path = BUILTIN_DIR / fname
            if path.exists():
                payloads.extend(self._read_lines(path))

        for extra in self._extra_paths:
            if os.path.exists(extra):
                payloads.extend(self._read_lines(extra))

        self._cache[vuln_type] = payloads[:MAX_PAYLOADS_PER_TYPE]
        logger.debug("Loaded %d payloads for %s", len(self._cache[vuln_type]), vuln_type)
        return self._cache[vuln_type]

    @staticmethod
    def _read_lines(path) -> list[str]:
        lines = []
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.rstrip("\n\r")
                if line and not line.startswith("#"):
                    lines.append(line)
        return lines

    def generate_get_targets(self, visited_urls: set[str]) -> list[GetTarget]:
        # Deduplicate by base path so multiple crawled variants of the same
        # endpoint (instructions.php?doc=readme, ?doc=PDF …) don't monopolise
        # the budget.  /vulnerabilities/ URLs are put first.
        seen_bases: set[str] = set()
        prioritised: list[str] = []
        for vuln_first in (True, False):
            for u in sorted(visited_urls):
                if "?" not in u:
                    continue
                p = urlparse(u)
                base = f"{p.scheme}://{p.netloc}{p.path}"
                if (("/vulnerabilities/" in u) == vuln_first) and base not in seen_bases:
                    seen_bases.add(base)
                    prioritised.append(u)

        urls_with_params = prioritised[:MAX_GET_URLS]

        # Build per-URL target lists, then interleave them round-robin so the
        # attack budget is spread evenly across all endpoints instead of being
        # exhausted on the first few URLs alphabetically.
        per_url: list[list[GetTarget]] = []
        for url in urls_with_params:
            parsed = urlparse(url)
            params = parse_qs(parsed.query, keep_blank_values=True)
            if not params:
                continue
            url_targets: list[GetTarget] = []
            for param_name in list(params.keys()):
                for vuln_type in _VULN_FILES:
                    for payload in self.load_payloads(vuln_type):
                        new_params = {k: v for k, v in params.items()}
                        new_params[param_name] = [payload]
                        test_url = urlunparse(parsed._replace(query=urlencode(new_params, doseq=True)))
                        url_targets.append(GetTarget(
                            url=url,
                            param=param_name,
                            payload=payload,
                            vuln_type=vuln_type,
                            test_url=test_url,
                        ))
            if url_targets:
                per_url.append(url_targets)

        # Round-robin interleave: one target from each URL per round
        result: list[GetTarget] = []
        max_len = max((len(t) for t in per_url), default=0)
        for i in range(max_len):
            for url_targets in per_url:
                if i < len(url_targets):
                    result.append(url_targets[i])
        return result

    def generate_post_targets(self, forms: list[dict]) -> list[PostTarget]:
        targets: list[PostTarget] = []
        for form in forms[:MAX_POST_FORMS]:
            fields = [
                f for f in form.get("inputs", [])
                if f.get("name") and f.get("type") != "file"
            ][:MAX_FIELDS_PER_FORM]
            if not fields:
                continue
            for field in fields:
                field_name = field["name"]
                for vuln_type in _VULN_FILES:
                    for payload in self.load_payloads(vuln_type):
                        data = {
                            f["name"]: payload if f["name"] == field_name else (f.get("value") or "")
                            for f in fields
                        }
                        targets.append(PostTarget(
                            action=form["action"],
                            method=form.get("method", "POST").upper(),
                            field=field_name,
                            payload=payload,
                            vuln_type=vuln_type,
                            data=data,
                        ))
        return targets
