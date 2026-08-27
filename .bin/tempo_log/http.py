"""Tiny JSON-over-HTTP transport with a swappable interface for tests."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Protocol


class TokenError(Exception):
    pass


class HttpError(Exception):
    def __init__(self, status: int, url: str, body: object, hint: str = ""):
        self.status, self.url, self.body = status, url, body
        detail = _extract_message(body)
        prefix = "network error" if status == 0 else f"HTTP {status}"
        msg = f"{prefix} from {url}" + (f": {detail}" if detail else "")
        super().__init__(msg + (f" ({hint})" if hint else ""))


def _extract_message(body: object) -> str:
    if isinstance(body, dict):
        for key in ("errorMessages", "errors", "message", "error"):
            val = body.get(key)
            if isinstance(val, list):
                parts = [v.get("message", str(v)) if isinstance(v, dict) else str(v) for v in val]
                return "; ".join(parts)
            if isinstance(val, str):
                return val
            if isinstance(val, dict):
                return "; ".join(f"{k}: {v}" for k, v in val.items())
    return ""


def token_from_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise TokenError(f"environment variable {name} is not set; export it before running tempo-log")
    return value


class Transport(Protocol):
    def request(self, method: str, url: str, headers: dict[str, str], body: dict | None) -> tuple[int, object]: ...


class UrllibTransport:
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    def request(self, method: str, url: str, headers: dict[str, str], body: dict | None) -> tuple[int, object]:
        data = json.dumps(body).encode() if body is not None else None
        hdrs = {"Accept": "application/json", **headers}
        if data is not None:
            hdrs["Content-Type"] = "application/json"
        for attempt in (1, 2):
            req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.status, _decode(resp.read())
            except urllib.error.HTTPError as exc:
                payload = _decode(exc.read())
                if exc.code >= 500 and attempt == 1:
                    time.sleep(1.0)
                    continue
                return exc.code, payload
            except urllib.error.URLError as exc:
                if attempt == 1:
                    time.sleep(1.0)
                    continue
                raise HttpError(0, url, {"message": str(exc.reason)}, hint="network error after retry") from exc
        raise RuntimeError("unreachable")


def _decode(raw: bytes) -> object:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"message": raw[:200].decode("utf-8", "replace")}
