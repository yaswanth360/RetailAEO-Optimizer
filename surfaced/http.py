"""Tiny HTTP helper with retries, so engines stay dependency-light."""
from __future__ import annotations

import time
from typing import Any

import httpx


def post_json(url: str, headers: dict[str, str], body: dict[str, Any], timeout: float = 90.0,
              retries: int = 3) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = httpx.post(url, headers=headers, json=body, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 529):
                raise httpx.HTTPStatusError(f"{r.status_code} {r.text[:200]}", request=r.request, response=r)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"request to {url.split('?')[0]} failed: {last}")
