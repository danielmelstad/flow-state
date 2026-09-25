"""Minimal Jira Cloud REST client (issue lookup, current user)."""

from __future__ import annotations

import base64
from urllib.parse import quote

from tempo_log.http import HttpError, Transport


class JiraClient:
    def __init__(self, site: str, email: str, token: str, transport: Transport):
        self.site = site.rstrip("/")
        self.transport = transport
        creds = base64.b64encode(f"{email}:{token}".encode()).decode()
        self.headers = {"Authorization": f"Basic {creds}"}

    def _get(self, path: str) -> dict:
        url = f"{self.site}{path}"
        status, body = self.transport.request("GET", url, self.headers, None)
        if status >= 400:
            raise HttpError(status, url, body)
        return body if isinstance(body, dict) else {}

    def issue(self, key: str) -> tuple[int, str]:
        body = self._get(f"/rest/api/3/issue/{quote(key)}?fields=summary")
        return int(body["id"]), str(body.get("fields", {}).get("summary", ""))

    def myself(self) -> tuple[str, str]:
        body = self._get("/rest/api/3/myself")
        return str(body["accountId"]), str(body.get("displayName", ""))
