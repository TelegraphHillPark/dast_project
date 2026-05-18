"""
Signature and Heuristic analyzers for HTTP responses.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.models.vulnerability import VulnSeverity, VulnType

logger = logging.getLogger("dast.analyzer")

# ── Signature databases ────────────────────────────────────────────────────────

_SQLI_SIGNATURES = [
    "sql syntax", "mysql_fetch", "ora-", "sqlstate", "unclosed quotation",
    "syntax error", "sqlite_exception", "pg::syntaxerror", "psycopg2",
    "you have an error in your sql", "warning: mysql", "supplied argument is not",
    "invalid query", "pg_query()", "mssql_query", "odbc_exec", "jdbc",
]

_SSRF_SIGNATURES = [
    "ami-id", "instance-id", "iam/security-credentials",
    "ssh-rsa", "openssh",
    "220 ", "230 ",
    "root:x:0:0",
    "ec2-metadata",
]

_SEVERITY: dict[VulnType, VulnSeverity] = {
    VulnType.sqli: VulnSeverity.high,
    VulnType.xss: VulnSeverity.medium,
    VulnType.ssrf: VulnSeverity.high,
    VulnType.open_redirect: VulnSeverity.medium,
    VulnType.header_injection: VulnSeverity.medium,
}

_RECOMMENDATIONS: dict[VulnType, str] = {
    VulnType.sqli: (
        "Use parameterized queries / prepared statements. "
        "Never concatenate user input into SQL strings."
    ),
    VulnType.xss: (
        "HTML-encode all user-supplied output. "
        "Apply a strict Content-Security-Policy."
    ),
    VulnType.ssrf: (
        "Validate and whitelist allowed URL schemes and hosts. "
        "Block requests to internal/loopback addresses at the network layer."
    ),
    VulnType.open_redirect: (
        "Use a server-side whitelist of allowed redirect destinations. "
        "Never redirect to a URL supplied directly by the user."
    ),
    VulnType.header_injection: (
        "Strip or reject CR and LF characters from any value "
        "that will be placed into an HTTP response header."
    ),
}

# ── Shared result type ─────────────────────────────────────────────────────────

@dataclass
class Finding:
    vuln_type: VulnType
    severity: VulnSeverity
    confidence: str          # "high" | "low"
    evidence: dict
    recommendation: str


# ── Signature analyzer ─────────────────────────────────────────────────────────

class SignatureAnalyzer:
    """Matches response body / headers against known exploitation markers."""

    def analyze(
        self,
        vuln_type: VulnType,
        payload: str,
        response: httpx.Response,
    ) -> Optional[Finding]:
        body_lower = response.text.lower()
        headers = {k.lower(): v for k, v in response.headers.items()}

        if vuln_type == VulnType.sqli:
            for sig in _SQLI_SIGNATURES:
                if sig in body_lower:
                    return Finding(
                        vuln_type=vuln_type,
                        severity=VulnSeverity.high,
                        confidence="high",
                        evidence={"signature": sig, "status": response.status_code},
                        recommendation=_RECOMMENDATIONS[vuln_type],
                    )

        elif vuln_type == VulnType.xss:
            if payload.lower() in response.text.lower():
                return Finding(
                    vuln_type=vuln_type,
                    severity=VulnSeverity.medium,
                    confidence="high",
                    evidence={"reflected_payload": payload, "status": response.status_code},
                    recommendation=_RECOMMENDATIONS[vuln_type],
                )

        elif vuln_type == VulnType.open_redirect:
            # With follow_redirects=True the final response has no Location header.
            # Check redirect history instead: only flag when evil.com is the netloc
            # (real external redirect), not when it appears in the query string of
            # an Apache trailing-slash 301 like /path/?param=//evil.com.
            for hist in response.history:
                loc = hist.headers.get("location", "")
                if loc and "evil.com" in urlparse(loc).netloc:
                    return Finding(
                        vuln_type=vuln_type,
                        severity=VulnSeverity.medium,
                        confidence="high",
                        evidence={"location": loc, "status": hist.status_code},
                        recommendation=_RECOMMENDATIONS[vuln_type],
                    )
            # Fallback: scanner followed the redirect and landed on evil.com
            if "evil.com" in response.url.host:
                return Finding(
                    vuln_type=vuln_type,
                    severity=VulnSeverity.medium,
                    confidence="high",
                    evidence={"final_url": str(response.url), "status": response.status_code},
                    recommendation=_RECOMMENDATIONS[vuln_type],
                )

        elif vuln_type == VulnType.ssrf:
            payload_lower = payload.lower()
            for sig in _SSRF_SIGNATURES:
                # Skip if the signature appears only because the payload itself contains it
                # (e.g. a reflected SSRF URL payload like http://.../iam/security-credentials/)
                if sig in body_lower and sig not in payload_lower:
                    return Finding(
                        vuln_type=vuln_type,
                        severity=VulnSeverity.high,
                        confidence="high",
                        evidence={"signature": sig, "status": response.status_code},
                        recommendation=_RECOMMENDATIONS[vuln_type],
                    )

        elif vuln_type == VulnType.header_injection:
            if "x-injected" in headers:
                return Finding(
                    vuln_type=vuln_type,
                    severity=VulnSeverity.medium,
                    confidence="high",
                    evidence={
                        "injected_header_value": headers["x-injected"],
                        "status": response.status_code,
                    },
                    recommendation=_RECOMMENDATIONS[vuln_type],
                )

        return None


# ── Heuristic analyzer ─────────────────────────────────────────────────────────

@dataclass
class Baseline:
    status: int
    body_size: int
    elapsed: float


class HeuristicAnalyzer:
    """Detects anomalies by comparing baseline vs payload responses."""

    def analyze(
        self,
        vuln_type: VulnType,
        payload: str,
        baseline: Baseline,
        response: httpx.Response,
        elapsed: float,
    ) -> Optional[Finding]:
        anomalies: list[str] = []

        if response.status_code != baseline.status:
            anomalies.append(
                f"HTTP status changed {baseline.status} → {response.status_code}"
            )

        body_size = len(response.content)
        if baseline.body_size > 0:
            diff_pct = abs(body_size - baseline.body_size) / baseline.body_size
            # Require >50% size change AND >200 bytes absolute to reduce false positives
            if diff_pct > 0.50 and abs(body_size - baseline.body_size) > 200:
                anomalies.append(
                    f"Response body size changed {baseline.body_size} → {body_size} "
                    f"({diff_pct:.0%} difference)"
                )

        if elapsed - baseline.elapsed > 2.0:
            anomalies.append(
                f"Response time increased {baseline.elapsed:.2f}s → {elapsed:.2f}s "
                f"(possible time-based injection)"
            )

        if not anomalies:
            return None

        return Finding(
            vuln_type=vuln_type,
            severity=_SEVERITY.get(vuln_type, VulnSeverity.low),
            confidence="low",
            evidence={
                "anomalies": anomalies,
                "payload": payload,
                "status": response.status_code,
            },
            recommendation=_RECOMMENDATIONS.get(vuln_type, "Review manually.")
            + " (requires manual verification)",
        )
