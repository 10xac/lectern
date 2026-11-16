"""The one door to the network for triage (jev) and the web tools (Exa, fetch_url).

Tests replace it with a fake, so they never touch the network. Real providers keep their own
``httpx`` calls (they are never used in tests either).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

import httpx

MAX_FETCH_BYTES = 200_000
RETRY_ONCE = frozenset({429, 529})  # rate limited or overloaded: worth one more try


class HttpStatusError(RuntimeError):
    """A non-2xx answer, with its status code (callers decide what each code means)."""

    def __init__(self, status: int, url: str) -> None:
        super().__init__(f"HTTP {status} from {url}")
        self.status = status


class Http(Protocol):
    def post_json(
        self, url: str, body: Mapping[str, Any], headers: Mapping[str, str], timeout: float
    ) -> dict[str, Any]: ...

    def get_text(self, url: str, timeout: float) -> str: ...


class HttpxPort:
    """The real port: JSON POSTs and size-capped, text-only GETs."""

    def post_json(
        self, url: str, body: Mapping[str, Any], headers: Mapping[str, str], timeout: float
    ) -> dict[str, Any]:
        resp = httpx.post(url, json=dict(body), headers=dict(headers), timeout=timeout)
        if resp.is_error:
            raise HttpStatusError(resp.status_code, url)
        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError(f"{url} did not return a JSON object")
        return data

    def get_text(self, url: str, timeout: float) -> str:
        if not url.startswith(("http://", "https://")):
            raise ValueError("only http(s) URLs can be fetched")
        with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as resp:
            resp.raise_for_status()
            kind = resp.headers.get("content-type", "")
            if not kind.startswith(("text/", "application/json")):
                raise ValueError(f"not text: {kind}")
            data = b""
            for chunk in resp.iter_bytes():
                data += chunk
                if len(data) >= MAX_FETCH_BYTES:
                    break
        return data[:MAX_FETCH_BYTES].decode("utf-8", errors="replace")
