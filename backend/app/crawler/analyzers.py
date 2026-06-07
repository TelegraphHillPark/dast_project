"""
Signature and Heuristic analyzers for HTTP responses.
"""
from __future__ import annotations

import logging
import shlex
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.models.vulnerability import VulnSeverity, VulnType

logger = logging.getLogger("dast.analyzer")

# ── CWE / OWASP mappings ───────────────────────────────────────────────────────

_CWE: dict[VulnType, str] = {
    VulnType.sqli:                    "CWE-89",
    VulnType.xss:                     "CWE-79",
    VulnType.ssrf:                    "CWE-918",
    VulnType.open_redirect:           "CWE-601",
    VulnType.header_injection:        "CWE-113",
    VulnType.broken_auth:             "CWE-287",
    VulnType.sensitive_data:          "CWE-200",
    VulnType.security_misconfiguration: "CWE-16",
    VulnType.other:                   "CWE-1035",
}

_OWASP: dict[VulnType, str] = {
    VulnType.sqli:                    "A03:2021 Injection",
    VulnType.xss:                     "A03:2021 Injection",
    VulnType.ssrf:                    "A10:2021 Server-Side Request Forgery",
    VulnType.open_redirect:           "A01:2021 Broken Access Control",
    VulnType.header_injection:        "A03:2021 Injection",
    VulnType.broken_auth:             "A07:2021 Identification and Authentication Failures",
    VulnType.sensitive_data:          "A02:2021 Cryptographic Failures",
    VulnType.security_misconfiguration: "A05:2021 Security Misconfiguration",
    VulnType.other:                   "A05:2021 Security Misconfiguration",
}

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
    VulnType.security_misconfiguration: VulnSeverity.low,
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
    VulnType.security_misconfiguration: (
        "Add the missing security header to all HTTP responses."
    ),
}

# ── Security headers catalogue ─────────────────────────────────────────────────

_SECURITY_HEADERS: list[dict] = [
    {
        "header": "content-security-policy",
        "display": "Content-Security-Policy",
        "severity": VulnSeverity.medium,
        "cwe": "CWE-1021",
        "recommendation": (
            "Add Content-Security-Policy header to restrict allowed sources "
            "of scripts, styles, and other resources. "
            "Example: Content-Security-Policy: default-src 'self'"
        ),
    },
    {
        "header": "x-frame-options",
        "display": "X-Frame-Options",
        "severity": VulnSeverity.medium,
        "cwe": "CWE-1021",
        "recommendation": (
            "Add X-Frame-Options: DENY or SAMEORIGIN to prevent clickjacking attacks."
        ),
    },
    {
        "header": "strict-transport-security",
        "display": "Strict-Transport-Security",
        "severity": VulnSeverity.medium,
        "cwe": "CWE-319",
        "recommendation": (
            "Add Strict-Transport-Security: max-age=31536000; includeSubDomains "
            "to enforce HTTPS connections."
        ),
    },
    {
        "header": "x-content-type-options",
        "display": "X-Content-Type-Options",
        "severity": VulnSeverity.low,
        "cwe": "CWE-16",
        "recommendation": (
            "Add X-Content-Type-Options: nosniff to prevent MIME-type sniffing."
        ),
    },
    {
        "header": "referrer-policy",
        "display": "Referrer-Policy",
        "severity": VulnSeverity.low,
        "cwe": "CWE-200",
        "recommendation": (
            "Add Referrer-Policy: strict-origin-when-cross-origin "
            "to control referrer information."
        ),
    },
    {
        "header": "permissions-policy",
        "display": "Permissions-Policy",
        "severity": VulnSeverity.low,
        "cwe": "CWE-16",
        "recommendation": (
            "Add Permissions-Policy header to restrict browser features "
            "such as camera, microphone, geolocation."
        ),
    },
]

# ── curl command builder ───────────────────────────────────────────────────────

def build_curl(
    method: str,
    url: str,
    data: dict | None = None,
    cookies: dict | None = None,
    headers: dict | None = None,
) -> str:
    parts = ["curl", "-X", method.upper(), shlex.quote(url)]

    if headers:
        for k, v in headers.items():
            if k.lower() != "user-agent":
                parts += ["-H", shlex.quote(f"{k}: {v}")]
    parts += ["-H", shlex.quote("User-Agent: DAST-Analyzer/0.1")]

    if cookies:
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        parts += ["-b", shlex.quote(cookie_str)]

    if data and method.upper() == "POST":
        form_str = "&".join(f"{k}={v}" for k, v in data.items())
        parts += ["--data", shlex.quote(form_str)]

    parts.append("-k")  # allow self-signed certs
    return " ".join(parts)


# ── Shared result type ─────────────────────────────────────────────────────────

@dataclass
class Finding:
    vuln_type: VulnType
    severity: VulnSeverity
    confidence: str          # "high" | "low"
    evidence: dict
    recommendation: str
    cwe: str = field(default="")
    owasp: str = field(default="")

    def __post_init__(self):
        if not self.cwe:
            self.cwe = _CWE.get(self.vuln_type, "")
        if not self.owasp:
            self.owasp = _OWASP.get(self.vuln_type, "")


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

        body_snippet = response.text[:500] if response.text else ""
        status = response.status_code

        if vuln_type == VulnType.sqli:
            for sig in _SQLI_SIGNATURES:
                if sig in body_lower:
                    return Finding(
                        vuln_type=vuln_type,
                        severity=VulnSeverity.high,
                        confidence="high",
                        evidence={
                            "signature": sig,
                            "status_code": status,
                            "body_snippet": body_snippet,
                        },
                        recommendation=_RECOMMENDATIONS[vuln_type],
                    )

        elif vuln_type == VulnType.xss:
            if payload.lower() in response.text.lower():
                return Finding(
                    vuln_type=vuln_type,
                    severity=VulnSeverity.medium,
                    confidence="high",
                    evidence={
                        "reflected_payload": payload,
                        "status_code": status,
                        "body_snippet": body_snippet,
                    },
                    recommendation=_RECOMMENDATIONS[vuln_type],
                )

        elif vuln_type == VulnType.open_redirect:
            for hist in response.history:
                loc = hist.headers.get("location", "")
                if loc and "evil.com" in urlparse(loc).netloc:
                    return Finding(
                        vuln_type=vuln_type,
                        severity=VulnSeverity.medium,
                        confidence="high",
                        evidence={
                            "location": loc,
                            "status_code": hist.status_code,
                            "body_snippet": body_snippet,
                        },
                        recommendation=_RECOMMENDATIONS[vuln_type],
                    )
            if "evil.com" in response.url.host:
                return Finding(
                    vuln_type=vuln_type,
                    severity=VulnSeverity.medium,
                    confidence="high",
                    evidence={
                        "final_url": str(response.url),
                        "status_code": status,
                        "body_snippet": body_snippet,
                    },
                    recommendation=_RECOMMENDATIONS[vuln_type],
                )

        elif vuln_type == VulnType.ssrf:
            payload_lower = payload.lower()
            for sig in _SSRF_SIGNATURES:
                if sig in body_lower and sig not in payload_lower:
                    return Finding(
                        vuln_type=vuln_type,
                        severity=VulnSeverity.high,
                        confidence="high",
                        evidence={
                            "signature": sig,
                            "status_code": status,
                            "body_snippet": body_snippet,
                        },
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
                        "status_code": status,
                        "body_snippet": body_snippet,
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
                "status_code": response.status_code,
                "body_snippet": response.text[:500] if response.text else "",
            },
            recommendation=_RECOMMENDATIONS.get(vuln_type, "Review manually.")
            + " (requires manual verification)",
        )


# ── Security headers analyzer ──────────────────────────────────────────────────

class SecurityHeadersAnalyzer:
    """
    Checks a single HTTP response for missing security headers.
    Returns one Finding per missing header.
    """

    def analyze(self, url: str, response: httpx.Response) -> list[Finding]:
        present = {k.lower() for k in response.headers}
        findings: list[Finding] = []

        for spec in _SECURITY_HEADERS:
            if spec["header"] not in present:
                findings.append(Finding(
                    vuln_type=VulnType.security_misconfiguration,
                    severity=spec["severity"],
                    confidence="high",
                    evidence={
                        "missing_header": spec["display"],
                        "status_code": response.status_code,
                        "url": url,
                        "curl": build_curl("GET", url),
                    },
                    recommendation=spec["recommendation"],
                    cwe=spec["cwe"],
                    owasp=_OWASP[VulnType.security_misconfiguration],
                ))

        return findings
