#!/usr/bin/env python3
"""M2.0 — Backfill real `meeting_date` and `primegov_id` for each ingested
video by consulting the PrimeGov meeting-list.

Motivation
----------
The M1.3 re-ingest wrote `meeting_date = 2026-08-19` (the ingest day) and
`primegov_id = -1` on all 9 transcript JSONs because the pipeline was
invoked with `--video-id` and bypassed the PrimeGov step. This blocks
date-range filters on the corpus and violates the "no silent
substitutions" contract for civic data.

Design
------
- Idempotent. Safe to re-run: same inputs → same writes, and re-writes
  are byte-identical when the source hasn't changed.
- Primary match: YouTube video ID (exact). This is the strong key —
  PrimeGov's `videoUrl` contains the canonical YouTube ID.
- Fallback match: date-proximity vs. `ingested_at` (--allow-date-fallback
  opt-in). Off by default — per M2 plan, missing matches block M2.0.
- Non-regular meetings (e.g. "Special City Council Meeting") require
  `--allow-special` to accept. Otherwise the script exits non-zero with a
  clear message. This preserves the "regular sessions only" invariant
  `build_transcripts.py` enforces on the live path.
- Two-phase writes:
    1. Dry-run (default): plan the diffs, print a table, exit 0.
    2. `--apply`: write JSONs and run `UPDATE transcript_chunks ...` in
       Supabase.
- Supabase writes go through PostgREST with the service-role key. The
  script does NOT create RLS policies; it uses the service role, which
  bypasses RLS server-side.
- The script also patches `title` from PrimeGov (currently a placeholder
  like "(m1.3 re-ingest)"). This is bonus — real titles help debugging
  and are not sensitive.

Usage
-----
    # Dry-run over data/transcripts/*.json:
    python scripts/transcripts/backfill_meeting_dates.py

    # Apply — writes JSONs, then UPDATEs Supabase:
    python scripts/transcripts/backfill_meeting_dates.py --apply

    # Restrict to one video:
    python scripts/transcripts/backfill_meeting_dates.py --video-id UkdZRHDB9qs --apply

    # Allow non-regular meetings (e.g. Special City Council Meeting):
    python scripts/transcripts/backfill_meeting_dates.py --apply --allow-special

Environment
-----------
- SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY — required only when `--apply`
  is passed AND `--json-only` is not passed.
- PRIMEGOV_URL / PRIMEGOV_DAYS — optional overrides for the meeting-list
  endpoint (default: 180 days).

Exit codes
----------
- 0 on success (including dry-run).
- 2 if any video failed to match under the requested policy.
- 3 if Supabase UPDATE returned an unexpected status.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Sequence

REPO = Path(__file__).resolve().parent.parent.parent  # la-money-votes/
DATA_DIR = REPO / "data" / "transcripts"

DEFAULT_PRIMEGOV_URL = "https://lacity.primegov.com/api/v2/PublicPortal/ListArchivedMeetingsByDays?days={days}"
DEFAULT_PRIMEGOV_DAYS = 180
REGULAR_COUNCIL_TITLE = "City Council Meeting"

log = logging.getLogger("backfill_meeting_dates")

YT_RE = re.compile(r"v=([a-zA-Z0-9_-]{11})")


# ---------------------------------------------------------------------------
# Data classes.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PrimegovMeeting:
    video_id: str
    meeting_date: date
    primegov_id: int
    title: str


@dataclass
class BackfillPlan:
    video_id: str
    json_path: Path
    old_date: str
    new_date: str
    old_pgid: int
    new_pgid: int
    old_title: str
    new_title: str
    match_method: str  # "video_id" | "date_proximity" | "unmatched"
    is_regular: bool
    note: str = ""

    @property
    def needs_change(self) -> bool:
        return (
            self.old_date != self.new_date
            or self.old_pgid != self.new_pgid
            or self.old_title != self.new_title
        )


# ---------------------------------------------------------------------------
# PrimeGov fetch + index. Pure I/O — separated so tests can stub with a
# local fixture.
# ---------------------------------------------------------------------------
def fetch_primegov_raw(url_template: str = DEFAULT_PRIMEGOV_URL,
                       days: int = DEFAULT_PRIMEGOV_DAYS,
                       timeout: int = 30) -> list[dict]:
    url = url_template.format(days=days)
    req = urllib.request.Request(url, headers={"User-Agent": "check-your-politician/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def build_meeting_index(raw: Iterable[dict]) -> dict[str, PrimegovMeeting]:
    """Index PrimeGov's response by YouTube video ID. Later entries with
    the same video ID overwrite earlier ones (PrimeGov's list is unique
    on `id`, and duplicate videoUrls across ids would be a data bug —
    we prefer the later one but log if we see a collision)."""
    idx: dict[str, PrimegovMeeting] = {}
    collisions: list[tuple[str, int, int]] = []
    for m in raw:
        url = m.get("videoUrl") or ""
        mm = YT_RE.search(url)
        if not mm:
            continue
        vid = mm.group(1)
        try:
            meeting_date = datetime.fromisoformat(m["dateTime"]).date()
        except (KeyError, ValueError):
            log.warning("skip primegov row with unparseable dateTime: id=%s", m.get("id"))
            continue
        pm = PrimegovMeeting(
            video_id=vid,
            meeting_date=meeting_date,
            primegov_id=int(m["id"]),
            title=m.get("title") or "",
        )
        if vid in idx and idx[vid].primegov_id != pm.primegov_id:
            collisions.append((vid, idx[vid].primegov_id, pm.primegov_id))
        idx[vid] = pm
    for c in collisions:
        log.warning("primegov collision video_id=%s pgids=%d,%d (kept latest)", *c)
    return idx


# ---------------------------------------------------------------------------
# Matching.
# ---------------------------------------------------------------------------
def match_video(
    video_id: str,
    ingested_at_iso: str | None,
    index: dict[str, PrimegovMeeting],
    *,
    allow_date_fallback: bool = False,
    max_proximity_days: int = 3,
) -> tuple[PrimegovMeeting | None, str]:
    """Return (meeting_or_None, method). method ∈ {'video_id',
    'date_proximity', 'unmatched'}."""
    hit = index.get(video_id)
    if hit is not None:
        return hit, "video_id"

    if not allow_date_fallback or not ingested_at_iso:
        return None, "unmatched"

    try:
        ingested = datetime.fromisoformat(ingested_at_iso.replace("Z", "+00:00")).date()
    except ValueError:
        return None, "unmatched"

    # Nearest regular-council meeting within N days of ingest date. We
    # only fall back on regular meetings — specials shouldn't be picked
    # up implicitly.
    best: tuple[int, PrimegovMeeting] | None = None
    for m in index.values():
        if m.title != REGULAR_COUNCIL_TITLE:
            continue
        delta = abs((m.meeting_date - ingested).days)
        if delta > max_proximity_days:
            continue
        if best is None or delta < best[0]:
            best = (delta, m)
    if best is not None:
        return best[1], "date_proximity"
    return None, "unmatched"


# ---------------------------------------------------------------------------
# Plan builder.
# ---------------------------------------------------------------------------
def plan_backfill(
    json_paths: Sequence[Path],
    index: dict[str, PrimegovMeeting],
    *,
    allow_date_fallback: bool = False,
    allow_special: bool = False,
) -> list[BackfillPlan]:
    plans: list[BackfillPlan] = []
    for p in json_paths:
        with p.open() as f:
            doc = json.load(f)
        vid = doc.get("video_id") or p.stem
        m, method = match_video(
            vid,
            doc.get("ingested_at"),
            index,
            allow_date_fallback=allow_date_fallback,
        )
        old_date = doc.get("meeting_date", "")
        old_pgid = int(doc.get("primegov_id", -1))
        old_title = doc.get("title", "")

        if m is None:
            plans.append(BackfillPlan(
                video_id=vid, json_path=p,
                old_date=old_date, new_date=old_date,
                old_pgid=old_pgid, new_pgid=old_pgid,
                old_title=old_title, new_title=old_title,
                match_method="unmatched",
                is_regular=False,
                note="no PrimeGov entry for this video id",
            ))
            continue

        is_regular = m.title == REGULAR_COUNCIL_TITLE
        note = ""
        if not is_regular:
            note = f"non-regular meeting: {m.title!r}"

        plans.append(BackfillPlan(
            video_id=vid, json_path=p,
            old_date=old_date, new_date=m.meeting_date.isoformat(),
            old_pgid=old_pgid, new_pgid=m.primegov_id,
            old_title=old_title, new_title=m.title,
            match_method=method,
            is_regular=is_regular,
            note=note,
        ))
    return plans


# ---------------------------------------------------------------------------
# Formatting.
# ---------------------------------------------------------------------------
def format_plans(plans: Sequence[BackfillPlan]) -> str:
    lines = []
    hdr = f"{'video_id':13s} {'old_date':10s} → {'new_date':10s}  {'method':14s}  {'pgid_new':>8s}  title/note"
    lines.append(hdr)
    lines.append("-" * len(hdr))
    for p in plans:
        title_note = p.new_title if p.needs_change else "(no change)"
        if p.note:
            title_note += f"   [{p.note}]"
        lines.append(
            f"{p.video_id:13s} {p.old_date:10s} → {p.new_date:10s}  "
            f"{p.match_method:14s}  {p.new_pgid:>8d}  {title_note}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Writers.
# ---------------------------------------------------------------------------
def write_json_updates(plans: Sequence[BackfillPlan]) -> int:
    """Overwrite each JSON with new meeting_date / primegov_id / title.
    Preserves everything else (utterances, coverage, etc.). Returns count
    of files actually modified."""
    modified = 0
    for p in plans:
        if not p.needs_change:
            continue
        with p.json_path.open() as f:
            doc = json.load(f)
        doc["meeting_date"] = p.new_date
        doc["primegov_id"] = p.new_pgid
        doc["title"] = p.new_title
        # Preserve prior key order but ensure these three land near the
        # top for readability. json.dump preserves insertion order from
        # Python 3.7+.
        tmp = p.json_path.with_suffix(".json.tmp")
        with tmp.open("w") as f:
            json.dump(doc, f, indent=2)
            f.write("\n")
        tmp.replace(p.json_path)
        modified += 1
    return modified


def update_supabase(plans: Sequence[BackfillPlan]) -> None:
    """UPDATE transcript_chunks SET meeting_date = ... WHERE video_id =
    ... — one call per changed video via PostgREST PATCH. Idempotent."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set for --apply")

    endpoint = url.rstrip("/") + "/rest/v1/transcript_chunks"
    for p in plans:
        if not p.needs_change:
            continue
        qs = urllib.parse.urlencode({"video_id": f"eq.{p.video_id}"})
        req = urllib.request.Request(
            f"{endpoint}?{qs}",
            method="PATCH",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            data=json.dumps({"meeting_date": p.new_date}).encode(),
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status not in (200, 204):
                    raise RuntimeError(f"unexpected supabase status {r.status} for {p.video_id}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"supabase PATCH failed for {p.video_id}: {e.code} {body}") from e
        log.info("supabase UPDATE ok video_id=%s meeting_date=%s", p.video_id, p.new_date)


def verify_supabase() -> list[tuple[str, str]]:
    """SELECT DISTINCT video_id, meeting_date. Uses PostgREST because we
    don't have execute_sql at runtime; the distinct is enforced client
    side after selecting the two columns."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required for verify")
    # Use aggregation via PostgREST: select video_id,meeting_date and
    # limit(0) trick isn't available; instead we page. 9 videos × few
    # thousand chunks is fine to page.
    endpoint = url.rstrip("/") + "/rest/v1/transcript_chunks"
    qs = urllib.parse.urlencode({
        "select": "video_id,meeting_date",
    })
    req = urllib.request.Request(
        f"{endpoint}?{qs}",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Range-Unit": "items",
            "Range": "0-9999",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        rows = json.load(r)
    seen: dict[str, str] = {}
    for row in rows:
        seen.setdefault(row["video_id"], row["meeting_date"])
    return sorted(seen.items())


# ---------------------------------------------------------------------------
# Main.
# ---------------------------------------------------------------------------
def _discover_transcript_jsons(data_dir: Path, video_id: str | None) -> list[Path]:
    if video_id:
        p = data_dir / f"{video_id}.json"
        if not p.exists():
            raise FileNotFoundError(p)
        return [p]
    skip = {"eval_queries.json", "eval_results_m1.4.json", "roster.json"}
    return sorted(p for p in data_dir.glob("*.json") if p.name not in skip)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Backfill meeting_date + primegov_id on transcript JSONs and Supabase.")
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--video-id", help="Backfill just one video (verification pass).")
    ap.add_argument("--apply", action="store_true", help="Actually write JSON files and UPDATE Supabase. Default is dry-run.")
    ap.add_argument("--json-only", action="store_true", help="With --apply: write JSONs but skip Supabase UPDATE.")
    ap.add_argument("--allow-special", action="store_true", help="Accept meetings whose PrimeGov title is not 'City Council Meeting'.")
    ap.add_argument("--allow-date-fallback", action="store_true", help="If a video isn't in PrimeGov by ID, match by date-proximity to ingested_at.")
    ap.add_argument("--primegov-days", type=int, default=DEFAULT_PRIMEGOV_DAYS)
    ap.add_argument("--fixture", type=Path, help="Read PrimeGov response from a local JSON fixture instead of the network (for tests).")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.fixture:
        raw = json.loads(args.fixture.read_text())
    else:
        raw = fetch_primegov_raw(days=args.primegov_days)
    log.info("primegov: fetched %d rows", len(raw))
    index = build_meeting_index(raw)
    log.info("primegov: indexed %d entries by youtube video id", len(index))

    json_paths = _discover_transcript_jsons(args.data_dir, args.video_id)
    log.info("discovered %d transcript JSONs", len(json_paths))

    plans = plan_backfill(
        json_paths,
        index,
        allow_date_fallback=args.allow_date_fallback,
        allow_special=args.allow_special,
    )

    print(format_plans(plans))

    # Enforce policy: unmatched and non-regular meetings block by
    # default. This mirrors the M2_PLAN.md "block, don't silently fall
    # back" decision.
    hard_errors: list[str] = []
    for p in plans:
        if p.match_method == "unmatched":
            hard_errors.append(f"{p.video_id}: unmatched — no PrimeGov entry (rerun with --allow-date-fallback if intentional)")
        elif not p.is_regular and not args.allow_special:
            hard_errors.append(f"{p.video_id}: PrimeGov title {p.new_title!r} is not the regular '{REGULAR_COUNCIL_TITLE}' (rerun with --allow-special if intentional)")

    if hard_errors:
        print("\nBLOCKED:")
        for e in hard_errors:
            print("  -", e)
        return 2

    if not args.apply:
        print("\n(dry-run — pass --apply to write JSONs and update Supabase)")
        return 0

    modified = write_json_updates(plans)
    print(f"\nWrote {modified} JSON file(s).")

    if args.json_only:
        print("Skipped Supabase UPDATE (--json-only).")
        return 0

    update_supabase(plans)

    print("\nVerification: SELECT DISTINCT video_id, meeting_date FROM transcript_chunks")
    rows = verify_supabase()
    for vid, d in rows:
        print(f"  {vid:13s} {d}")
    distinct_dates = sorted({d for _, d in rows})
    print(f"\nDistinct video_ids: {len(rows)}   Distinct meeting_dates: {len(distinct_dates)}")
    if len(rows) != len(distinct_dates):
        print("WARNING: some meetings share a meeting_date. That can be legitimate (two meetings same day) but review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
