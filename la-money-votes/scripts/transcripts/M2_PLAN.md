# Transcript RAG — M2 Plan

**Branch:** `computer/transcript-rag-m2` (forked from M1 head `bf0c58c`)
**Status:** M2.0 + M2.1 + M2.2 + M2.3 shipped on branch `computer/transcript-rag-m2` (Ask-AI transcript augmentation deferred). See per-milestone acceptance notes below.
**Non-goal for M2:** RAG-augmenting the Sonar-backed "Ask about ..." Q&A
widget to also consult transcripts. Deferred to a later milestone (M3+).

## What M1 shipped (context)

- 9 LA City Council meetings ingested, 5,003 chunks, 1,019 CM-attributed
- Speaker-turn chunking with sub-chunking for turns > 120 words
- Per-official transcript-search widget on `official.html`
- `search_transcripts` RPC with tuned similarity floor 0.25
- 20-query gold eval: parent@1 = 90%, parent@3 = 100%
- Draft PR #22 open, not merged

## M2 goals

M2 hardens the M1 corpus and fills three real gaps surfaced during M1
review. It does **not** expand the corpus, add new UI surfaces, or wire
transcripts into other product paths.

### G1. Real meeting dates
All 9 chunks currently carry `meeting_date = 2026-08-19` (the ingest
day). This blocks any date-range filter and makes the RPC's date args
functionally unused. M2 resolves each YouTube video to its actual meeting
date via PrimeGov and backfills.

### G2. Public-comment search
The RPC requires a non-null `p_official_id`, so the ~3,000 unattributed
public-comment chunks are unreachable. M2 adds `search_public_comment`
as a sibling RPC with the same shape but keyed on `chunk_type = 'public_comment'`
(or equivalent), plus a small frontend affordance to opt into it.

### G3. Sub-chunk metadata in RPC return
The RPC currently returns `chunk_idx` but not `sub_chunk_idx` /
`sub_chunk_of`, so the frontend can't show "part 3 of 5" when a long
turn was split. Purely additive column adds — no behavior change for
existing consumers.

## Explicitly out of scope for M2

- **Ask-AI transcript augmentation.** Deferred. The Ask-AI module today
  calls Perplexity Sonar with web-search grounding; wiring it to also
  consult our transcript corpus is a separate design decision (retrieval
  strategy, snippet formatting, cost profile, hallucination surface).
- **Corpus expansion.** No new meetings, no committee meetings, no LA
  County board, no historical backfill beyond the 9 already loaded.
- **Refresh cadence.** Transcripts stay one-shot in M2. Adding them to
  the monthly `refresh-data` GitHub Action is a separate milestone —
  requires YouTube API quota planning and PrimeGov date resolution to
  be stable first.
- **Ranking or embedding-model changes.** M1.4 established that the
  current model + floor 0.25 is fit for purpose. Do not re-embed or
  swap models in M2.

## Requirements

| # | Requirement | Priority | Rationale | Acceptance criterion |
|---|---|---|---|---|
| R1 | Backfill real `meeting_date` for all 9 videos | Must | Enables date filters; blocks calling the corpus "current" | Every row has a `meeting_date` matching PrimeGov's council-meeting date for that video |
| R2 | Add `search_public_comment` RPC | Must | Unlocks ~3,000 dormant chunks | RPC returns hits from public-comment chunks only; SECURITY INVOKER; anon read policy |
| R3 | Add sub-chunk metadata to `search_transcripts` return | Must | Frontend can show sub-chunk position | RPC returns `sub_chunk_idx` and `sub_chunk_of` columns |
| R4 | Frontend: show "part N of M" for sub-chunk results | Should | User-facing evidence of chunking | UI displays badge when `sub_chunk_of > 1` |
| R5 | Extend eval to cover public-comment queries | Should | Establishes baseline for the new RPC | 10-query public-comment gold set; report parent@1 and parent@3 |
| R6 | Cost/latency instrumentation on both RPCs | Should | Feeds the credits-optimization work | Log embedding-call and RPC-call counts per request |

## Architecture — deltas only

M2 does not change the M1 architecture. Deltas:

- **Backfill script**: `scripts/transcripts/backfill_meeting_dates.py`
  - Reads each `data/transcripts/*.json`, calls PrimeGov meeting-list
    for the associated council session, matches on YouTube video ID or
    date proximity, writes date into the JSON, then `UPDATE`s Supabase.
  - Idempotent: safe to re-run.
- **New RPC**: `search_public_comment` — same signature shape as
  `search_transcripts`, but ignores official filter and matches on
  chunk-type. Ships as migration `m2_public_comment_search.sql`.
- **RPC signature change (additive)**: `search_transcripts` gains two
  columns in the return table (`sub_chunk_idx`, `sub_chunk_of`). Existing
  callers ignoring extra columns keep working; API layer is updated
  to pass them through.
- **Frontend**: `transcript-search.js` gains a `part N of M` badge when
  present. Optional toggle to search public comments.

## Delivery plan

### M2.0 — PrimeGov date backfill (day 0)
- Write `backfill_meeting_dates.py`
- Verify against a known-good meeting first
- Apply to all 9 videos, update JSONs, `UPDATE transcript_chunks`
- Verify: `SELECT DISTINCT video_id, meeting_date FROM transcript_chunks`
  shows 9 distinct dates spread across the actual 10 most recent regular
  sessions

**Acceptance:** all 9 meetings have real dates in Supabase and in the
canonical JSONs.

### M2.1 — Public-comment RPC (day 0-1)
- Migration `m2_public_comment_search.sql` — CREATE FUNCTION with same
  security posture as `search_transcripts` (SECURITY INVOKER,
  transcript_chunks_read_anon policy already covers reads)
- Add `api/search-public-comment.js` (may share the search-transcripts
  handler with a query-param toggle to reduce duplication)
- Rate-limit shares the existing Upstash Redis store
- Small frontend affordance: a toggle "include public comments" on the
  transcript-search widget

**Acceptance:** public-comment queries return non-empty results for
seeded queries; existing per-official search behavior unchanged.

### M2.2 — Sub-chunk metadata + UI (day 1)
- Migration `m2_subchunk_in_rpc.sql` — CREATE OR REPLACE `search_transcripts`
  adding two columns to the return table
- Update `api/search-transcripts.js` to pass fields through
- Update `js/transcript-search.js` to render "part N of M" badge

**Acceptance:** eval q13 (Park + Palisades Larry, sub-chunk 24/26) now
shows "part 24 of 26" in the UI.

### M2.3 — Public-comment eval + instrumentation (day 1-2)
- Author 10 public-comment gold queries (topics: housing, budget,
  transit, homelessness, etc.)
- Extend `eval_transcript_rag.py` to accept `--rpc search_public_comment`
- Add per-request counters in the API handlers, log to Vercel logs
- Report both RPC eval results in a single `eval_results_m2.json`

**Acceptance:** eval report shows parent@1 ≥ 60% on public-comment set
(lower bar because attribution is coarser); instrumentation visible in
Vercel logs.

**M2.3 result (2026-08-19):** parent@1 = 70%, parent@3 = 80% on the
10-query public-comment gold set across all 5 floors
(0.15 → 0.35). `search_transcripts` re-run against the M1 20-query set
is unchanged at parent@1 = 90%, parent@3 = 100% — the runner refactor
is regression-free. Combined report in
`data/transcripts/eval_results_m2.json`. Per-request structured metrics
(`[metrics] endpoint=... outcome=... q_len=... count=... top1_sim=...
min_sim=... duration_ms=... official=... date_from=... date_to=...`)
emit on every request in both handlers via `logSearchMetrics` in
`api/_lib/transcript-search-lib.js`. Query text is never logged.

## Prioritized backlog

| ID | Task | Priority | Estimate | Deps | DoD |
|---|---|---|---|---|---|
| M2.0-1 | Write PrimeGov date-resolution helper | Must | 1h | — | Given a YouTube video ID, returns the meeting date |
| M2.0-2 | Backfill script + apply to 9 videos | Must | 30m | M2.0-1 | 9 distinct real dates in Supabase |
| M2.1-1 | `search_public_comment` migration | Must | 30m | — | Migration applied, RPC returns rows |
| M2.1-2 | `api/search-public-comment.js` handler | Must | 45m | M2.1-1 | 200 OK on seeded query |
| M2.1-3 | Frontend toggle for public comments | Should | 45m | M2.1-2 | Toggle visible, results render |
| M2.2-1 | Sub-chunk metadata in RPC return | Must | 20m | — | Return table gains 2 columns |
| M2.2-2 | UI "part N of M" badge | Should | 30m | M2.2-1 | q13 renders "24 of 26" |
| M2.3-1 | 10-query public-comment gold set | Should | 45m | M2.1-2 | JSON in data/transcripts/ |
| M2.3-2 | Extend eval runner + run sweep | Should | 30m | M2.3-1 | eval_results_m2.json committed |
| M2.3-3 | Per-request instrumentation | Should | 30m | — | Counters visible in logs |

Total estimate: ~6 hours of focused work.

## Testing and evaluation

- Unit tests for the date-backfill helper (offline fixture).
- Migration dry-run against a schema-only clone before applying to prod.
- Eval sweep on both RPCs before opening the PR.
- Live preview smoke on 3 queries per RPC (mirroring M1.5 practice).

## Decisions needed (from user, before starting)

1. **Public-comment attribution UI.** Public-comment chunks currently
   have `resolved_official_id = NULL`. When surfaced in the widget,
   should they show speaker cue as-is (e.g. "PUBLIC SPEAKER") or should
   we try harder to resolve individual public speakers (e.g. via
   sign-in card OCR)? **Recommend: cue as-is for M2.**
2. **Public-comment scope.** Show public comments on every councilmember
   page (since they may address any council item), or only on a global
   search page? **Recommend: opt-in toggle on the per-official widget;
   defer global search to a later milestone.**
3. **Date-backfill fallback.** If PrimeGov doesn't return a match for a
   YouTube video, do we (a) block the M2.0 milestone or (b) fall back
   to the video upload date? **Recommend: block M2.0 rather than fall
   back — real meeting dates matter for civic transparency.**
