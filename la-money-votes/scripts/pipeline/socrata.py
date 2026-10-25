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

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BASE_URL = "https://data.lacity.org/resource/{resource_id}.json"
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3
DEFAULT_PAGE_SIZE = 5000


class SourceUnavailable(Exception):
    """Raised when a dataset can't be fetched and no usable cache exists."""


# --- fetch outcome log and cache provenance (additive; fetch_dataset's
# signature and return value are unchanged, so existing callers are
# unaffected) ---
#
# Every fetch_dataset() call records one FetchOutcome, keyed by resource_id,
# in a module-level dict. build_all.py resets the log at the start of every
# orchestration run and reads the contributions and statements outcomes
# separately right after loading them. Because the key is the resource id, a
# statements fetch can never overwrite the contributions outcome. The log is
# process-local and not thread-safe; the pipeline is single-threaded.
#
# origin values:
#   ORIGIN_LIVE            every page fetched from the network this call
#   ORIGIN_CACHE_FALLBACK  the network failed and the cache file was returned
#   ORIGIN_CACHE_ONLY      use_cache_only=True; the network was never tried
#   ORIGIN_UNAVAILABLE     neither network nor cache; SourceUnavailable raised
#
# retrieved_at is the UTC time of the live retrieval that produced the rows
# returned. For ORIGIN_LIVE it is "now". For a cached origin it comes only
# from the cache's provenance sidecar (<cache>.meta.json), and only if the
# sidecar names the same resource and filter and its SHA-256 matches the
# cache bytes exactly; otherwise it is None and retrieved_at_verified is
# False. A cache file's mtime is never used.
ORIGIN_LIVE = "live"
ORIGIN_CACHE_FALLBACK = "cache_fallback"
ORIGIN_CACHE_ONLY = "cache_only"
ORIGIN_UNAVAILABLE = "unavailable"
CACHE_META_VERSION = 1


@dataclass(frozen=True)
class FetchOutcome:
    resource_id: str
    origin: str
    retrieved_at: Optional[str] = None
    retrieved_at_verified: bool = False


_FETCH_OUTCOMES: dict = {}
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$")


def _utcnow() -> datetime:
    """Seam for tests; production code always uses the real UTC clock."""
    return datetime.now(timezone.utc)


def _record_outcome(resource_id, origin, retrieved_at=None) -> None:
    _FETCH_OUTCOMES[resource_id] = FetchOutcome(resource_id, origin, retrieved_at, retrieved_at is not None)


def get_fetch_outcome(resource_id: str):
    """The FetchOutcome of the most recent fetch_dataset() call for
    resource_id since the last reset_fetch_outcomes(), or None."""
    return _FETCH_OUTCOMES.get(resource_id)


def reset_fetch_outcomes() -> None:
    _FETCH_OUTCOMES.clear()


def cache_meta_path(cache_path) -> Path:
    cache_path = Path(cache_path)
    return cache_path.with_name(cache_path.name + ".meta.json")


def _valid_ts(value) -> bool:
    if not isinstance(value, str) or not _TS_RE.match(value):
        return False
    try:
        datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return False
    return True


def _read_cache(resource_id, where, cache_path):
    """Return (rows, verified_retrieved_at_or_None) for an existing cache."""
    raw = Path(cache_path).read_bytes()
    rows = json.loads(raw.decode("utf-8"))
    try:
        meta = json.loads(cache_meta_path(cache_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return rows, None
    trusted = (
        isinstance(meta, dict)
        and meta.get("meta_version") == CACHE_META_VERSION
        and meta.get("resource_id") == resource_id
        and meta.get("where") == where
        and meta.get("sha256") == hashlib.sha256(raw).hexdigest()
        and isinstance(rows, list)
        and meta.get("row_count") == len(rows)
        and _valid_ts(meta.get("retrieved_at"))
    )
    return rows, (meta["retrieved_at"] if trusted else None)


def _write_cache(resource_id, where, cache_path, rows, retrieved_at) -> None:
    """Write the cache and then its provenance sidecar. The old sidecar is
    removed first, so a crash between the two writes leaves an unverified
    cache rather than a mismatched timestamp."""
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path = cache_meta_path(cache_path)
    meta_path.unlink(missing_ok=True)
    data = json.dumps(rows).encode("utf-8")
    cache_path.write_bytes(data)
    meta = {
        "meta_version": CACHE_META_VERSION,
        "resource_id": resource_id,
        "where": where,
        "retrieved_at": retrieved_at,
        "row_count": len(rows),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    tmp = meta_path.with_name(meta_path.name + ".tmp")
    tmp.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    tmp.replace(meta_path)


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
    - Every call records where its rows came from; see get_fetch_outcome().
      Any earlier outcome for this resource is discarded first, so a call
      that raises (e.g. an unreadable cache) never leaves a stale one.
    """
    _FETCH_OUTCOMES.pop(resource_id, None)
    if use_cache_only:
        if cache_path and Path(cache_path).exists():
            rows, cached_at = _read_cache(resource_id, where, cache_path)
            _record_outcome(resource_id, ORIGIN_CACHE_ONLY, cached_at)
            return rows
        _record_outcome(resource_id, ORIGIN_UNAVAILABLE)
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
            cached_rows, cached_at = _read_cache(resource_id, where, cache_path)
            _record_outcome(resource_id, ORIGIN_CACHE_FALLBACK, cached_at)
            return cached_rows
        _record_outcome(resource_id, ORIGIN_UNAVAILABLE)
        raise
    retrieved_at = _utcnow().astimezone(timezone.utc).replace(microsecond=0).isoformat()

    if cache_path:
        _write_cache(resource_id, where, cache_path, rows, retrieved_at)
    _record_outcome(resource_id, ORIGIN_LIVE, retrieved_at)
    return rows
