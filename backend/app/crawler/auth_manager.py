"""
Auth Manager — applies authentication to the crawler's HTTP client.
Strategies: none | cookie | basic | bearer | form
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("dast.auth_manager")


def _canonical_url(url: str) -> str:
    """Normalize URL for comparison: strip default port and trailing slash."""
    p = urlparse(url.rstrip("/"))
    netloc = p.netloc
    if p.scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    elif p.scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]
    return f"{p.scheme}://{netloc}{p.path}"


class AuthManager:
    def __init__(self, config: dict):
        self.auth_type: str = config.get("type", "none")
        self.cookie: str | None = config.get("cookie")
        self.username: str | None = config.get("username")
        self.password: str | None = config.get("password")
        self.bearer_token: str | None = config.get("bearer_token")
        self.login_url: str | None = config.get("login_url")
        self.username_field: str = config.get("username_field", "username")
        self.password_field: str = config.get("password_field", "password")

    def build_client(self) -> httpx.AsyncClient:
        kwargs: dict = {
            "follow_redirects": True,
            "timeout": httpx.Timeout(10.0, connect=5.0),
            "headers": {"User-Agent": "DAST-Analyzer/0.1"},
        }

        if self.auth_type == "basic" and self.username:
            kwargs["auth"] = (self.username, self.password or "")

        elif self.auth_type == "bearer" and self.bearer_token:
            kwargs["headers"] = {
                **kwargs["headers"],
                "Authorization": f"Bearer {self.bearer_token}",
            }

        elif self.auth_type == "cookie" and self.cookie:
            cookies: dict[str, str] = {}
            for pair in self.cookie.split(";"):
                pair = pair.strip()
                if "=" in pair:
                    key, _, value = pair.partition("=")
                    cookies[key.strip()] = value.strip()
            kwargs["cookies"] = cookies

        return httpx.AsyncClient(**kwargs)

    async def perform_form_login(self, client: httpx.AsyncClient) -> bool:
        if self.auth_type != "form" or not self.login_url or not self.username:
            return False
        try:
            from bs4 import BeautifulSoup

            # Step 1: GET the login page to collect hidden CSRF fields
            resp = await client.get(self.login_url)
            hidden: dict[str, str] = {}
            submit_fields: dict[str, str] = {}
            if "text/html" in resp.headers.get("content-type", ""):
                soup = BeautifulSoup(resp.text, "lxml")
                # Find the login form (pick the one most likely to be the auth form)
                form = None
                for f in soup.find_all("form"):
                    inputs = {i.get("name", "") for i in f.find_all("input")}
                    if self.username_field in inputs and self.password_field in inputs:
                        form = f
                        break
                if form is None:
                    form = soup.find("form")

                if form:
                    for inp in form.find_all("input"):
                        name = inp.get("name")
                        if not name:
                            continue
                        t = inp.get("type", "text").lower()
                        if t == "hidden":
                            hidden[name] = inp.get("value", "")
                        elif t == "submit":
                            submit_fields[name] = inp.get("value", "")

            post_data = {
                **hidden,
                **submit_fields,
                self.username_field: self.username,
                self.password_field: self.password or "",
            }

            # Step 2: POST credentials
            login_resp = await client.post(self.login_url, data=post_data)

            # Step 3: Detect failure — if we're back on the login page, login failed.
            # Compare canonical URLs so http://host:80/login == http://host/login.
            final_url = str(login_resp.url)
            if _canonical_url(final_url) == _canonical_url(self.login_url):
                logger.warning("Form login appears to have failed (redirected back to login page): %s", final_url)
                return False

            logger.info(
                "Form login succeeded for %s → landed on %s (hidden=%s)",
                self.login_url, final_url, list(hidden.keys()),
            )
            return True

        except Exception as exc:
            logger.warning("Form login exception: %s", exc)
            return False
