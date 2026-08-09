"""Thin, stdlib-only client for the City of Los Angeles' Socrata open-data
portal (data.lacity.org), used to fetch the LA Ethics Commission's campaign
finance datasets.

Two datasets are used, both public and unauthenticated (verified live):
  - m6g2-gc6c  "City Campaign Contributions (and Misc. Increases to Cash)"
  - br3a-db9a  "City Campaign Statements Filed"

An optional Socrata app token (free to request, raises the anonymous rate
limit) can be set via the SOCRATA_APP_TOKEN environment variable / GitHub
Actions secret. It is never required for these public datasets and this
module works with no token at all — see README "Source policy".

No third-party HTTP library: urllib.request is sufficient for a handful of
GET requests a few times a week, and it keeps the whole pipeline
dependency-light.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_URL = "https://data.lacity.org/resource/{resource_id}.json"
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3
DEFAULT_PAGE_SIZE = 5000


class SourceUnavailable(Exception):
    """Raised when a dataset can't be fetched and no usable cache exists."""


def _build_url(resource_id: str, params: dict) -> str:
    query = urllib.parse.urlencode(params)
    return f"{BASE_URL.format(resource_id=resource_id)}?{query}"


def _request(url: str, timeout: int, retries: int) -> list:
    token = os.environ.get("SOCRATA_APP_TOKEN")
    headers = {"Accept": "application/json"}
    if token:
        headers["X-App-Token"] = token

    last_error = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                return json.loads(body.decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(2 ** attempt, 10))
    raise SourceUnavailable(f"GET {url} failed after {retries} attempt(s): {last_error}")


def fetch_dataset(
    resource_id: str,
    where: str = None,
    cache_path: Path = None,
    use_cache_only: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> list:
    """Fetch every row of a Socrata dataset (paginating with $limit/$offset).

    - If `use_cache_only` is True, never hits the network — reads cache_path
      and raises SourceUnavailable if it's missing. Used by tests and by any
      offline/dry-run build.
    - On a network failure, falls back to `cache_path` if it exists (stale
      cache is better than a failed build), and only raises if there is no
      cache to fall back to.
    - On success, writes the fresh result to `cache_path` (if given) before
      returning it.
    """
    if use_cache_only:
        if cache_path and Path(cache_path).exists():
            return json.loads(Path(cache_path).read_text())
        raise SourceUnavailable(f"use_cache_only=True but no cache at {cache_path}")

    rows: list = []
    offset = 0
    try:
        while True:
            params = {"$limit": page_size, "$offset": offset}
            if where:
                params["$where"] = where
            page = _request(_build_url(resource_id, params), timeout, retries)
            rows.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
    except SourceUnavailable:
        if cache_path and Path(cache_path).exists():
            return json.loads(Path(cache_path).read_text())
        raise

    if cache_path:
        cache_path = Path(cache_path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(rows))
    return rows
