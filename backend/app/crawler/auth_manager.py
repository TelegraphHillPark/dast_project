"""
Auth Manager — applies authentication to the crawler's HTTP client.
Strategies: none | cookie | basic | bearer | form
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("dast.auth_manager")


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

    async def perform_form_login(self, client: httpx.AsyncClient) -> None:
        if self.auth_type != "form" or not self.login_url or not self.username:
            return
        try:
            await client.post(
                self.login_url,
                data={
                    self.username_field: self.username,
                    self.password_field: self.password or "",
                },
            )
            logger.info("Form login completed for %s", self.login_url)
        except Exception as exc:
            logger.warning("Form login failed: %s", exc)
