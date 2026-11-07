# Source and corpus verification, November 6, 2026

## Observed inventory

PrimeGov public metadata was read at 2026-11-07 02:13:47 UTC, November 6 at
18:13 Pacific. The nominal 90-day request spans August 8 at 19:14 Pacific through
November 6 at 18:14 Pacific. Boundary inclusivity is controlled by the API.
The API returned 241 rows and its latest returned meeting is October 28.
This response establishes the currently observed inventory and does not verify
that all meetings through November 6 are present.

The locked taxonomy admits 101 meetings, comprising 35 Council and 66 standing
committee rows. There are 76 unique recordings, 25 missing-video rows, and zero
shared-recording collisions within this response. Three recordings match local
canonical artifacts. Seventy-three recordings need caption preflight. The
legacy manifest field `already_published_videos` counts local artifact matches,
so live publication is still unverified. Six older canonical recordings remain
outside the discovery window and have been preserved.

Independent enumeration from the captured raw metadata matches the corrected
helper's newest ten regular Council sessions. The first two sessions have no
video, a case the previous implementation incorrectly excluded.

| Meeting date | PrimeGov ID | Recording |
| --- | --- | --- |
| 2026-10-28 | 23793 | Missing video URL |
| 2026-10-27 | 23794 | Missing video URL |
| 2026-10-23 | 23786 | rzdSGTDRRxI |
| 2026-10-21 | 18410 | byBa-j7vrUc |
| 2026-10-20 | 18416 | RmhXeARED3A |
| 2026-10-16 | 23773 | MHjaJx88dPw |
| 2026-10-14 | 23760 | wBhTMjTPb-Q |
| 2026-10-13 | 17727 | bXpwFA-NNCg |
| 2026-10-09 | 23734 | FSPxkA0oJl0 |
| 2026-10-07 | 23716 | jrIbCM6_jv0 |

Raw response SHA-256 is
`edc7ca4b278f0b498f39f422c4dbbb3d9ddd3463858c1a53f23d584a563d59d6`.
Safe local evidence is under `work/release/source/` in `primegov-90days.json`,
`corpus-current.json`, and `inventory-verification.json`. No published manifest
or canonical transcript was replaced.

## Executed engineering checks

The newest-ten regression failed against the inherited implementation, then
passed after removing the video filter. Eight discovery tests pass.

Six caption diagnostic regressions produced five failures and one error against
the inherited implementation. They cover stale file reuse, non-caption payloads,
invalid timing, missing speaker cues, listing failures, and unsafe error output.
After correction and additional language/timing/cache regressions, 30 caption
tests pass. Reports now contain payload hashes,
validated cue/speaker counts, actual process return codes, and unknown HTTP
status where appropriate. Signed URLs and raw error output are omitted. A cookie
source is not represented as proof of successful authentication.

The PostgreSQL runner passes shell syntax validation and now supports explicit
`PYTHON` and `PGBIN`. It refuses root rather than creating a helper system user.
The initial preflight found no PostgreSQL installation and collected 17 skipped
tests. After explicit owner approval, a workspace-only PostgreSQL 16.14 and
pgvector 0.8.2 installation executed all 17 tests successfully in 0.353 seconds,
with zero failures and zero skips. The temporary cluster listened on loopback
only, disabled Unix sockets, and was stopped and removed by the runner.
`work/release/source/pg-executed.log` contains the actual execution evidence.
The older skip log records only the initial environment state.

A current offline replay reproduced 30 of 36 queries with 234 of 234 pooled
candidates judged. The full-coverage command exits nonzero due to six missing
traces. Original judgments were preserved. Two additional grounded cases are authored
and schema-validated in `source-evaluation-cases.json` for
`QePVCuF0iAY` and `welTRe5_RH4`. The latter requires both historical PrimeGov
identities 17801 and 18451 while preserving uncertainty about which segment
belongs to which meeting. Full candidate keys are retained. These two cases
have no live traces or reviewed retrieved pools, and their provenance assertion
needs an online adapter. The final live expanded-corpus report is absent.

## Source and access blockers

The initial inspection found no downloader, database binaries, driver, or VTT
cache. Owner-approved dependencies were then installed only under
`work/release/tooling`. The active versions are yt-dlp 2026.10.26,
psycopg2-binary 2.9.11, PostgreSQL 16.14, and pgvector 0.8.2. PostgreSQL's
published SHA-256 and exact PyPI wheel digests were verified before use.
The official pgvector tag archive's SHA-256 was recorded, with no claim of an
independently published checksum. Download metadata is in
`work/release/tooling/download-manifest.json`.

All three probe descriptions were checked against the captured official
PrimeGov response before cookie access. The owner-approved single probe used
Chrome Default directly, only the `web` client, no automatic retries, and a
720-second process-group deadline. It completed in 2.53 seconds. Control
`MBjio010l60`, Council `rzdSGTDRRxI`, and Personnel and Hiring Committee
`DP_mNBtgH1s` each failed at listing with process return code 1. No track or
payload was obtained. No cookie export or usable VTT was created. The tool's
temporary material was removed and the remaining caption-probe directory is
empty. Exact reports are `caption-probe.json` and `caption-probe-execution.json`.

The implementation at probe time retained only error-presence flags, so raw
stderr was discarded and exact error causes cannot be recovered. A later
local correction adds fixed safe error categories for any separately approved
follow-up. Those categories are not retroactively claimed for this execution.
The historical report's recommendation to switch versions is superseded by
the active single-version approval boundary. Source absence is unproven.

A bounded read-only environment check confirms that Chrome Default exists,
Python sqlite3/ssl load, and the downloader version command works. Optional
Crypto/Cryptodome and yt_dlp_ejs modules are absent, but yt-dlp includes a
pure-Python AES fallback, so missing modules do not establish this failure's
cause. The final separately approved follow-up is recorded below.

The current shell has no `PERPLEXITY_API_KEY`, `SUPABASE_URL`,
`SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, or disposable database DSN.
This describes local configuration only. Applied migrations, live indexed
meetings, model dimensions, constraints, RLS/grants, and read/write behavior
remain unverified. Paid ingestion/evaluation and shared mutation remain gated.

`scripts/transcripts/ingest_verified.py` now connects the existing embedding and
transactional replacement seams for one reviewed recording. Its default is an
offline plan bound to source, implementation, target-review and checkpoint-path
hashes. Twenty-one offline tests cover approval binding, shared provenance,
concurrent execution, unknown outcomes, drift, and post-write verification.
No live adapter operation has run. Execution requires separately approved paid
calls/shared writes and independently established exclusive cohort ownership,
because the existing replacement RPC has no compare-and-swap precondition.
The legacy builder's client upsert remains unsuitable for replacement publication.

## Independent human review

`source-speaker-practice.md` contains 12 practice items with canonical meeting
identity, timestamped source links, surrounding text, and blank speaker/role/
unresolved/evidence fields. Sampling deliberately covers councilmember labels,
presiding language, procedural exchanges, public-comment boundaries, and fuzzy
labels across historical Council recordings. Committee practice remains pending
verified source material. This diagnostic worksheet is not the final held-out
sample and no independent labels have been received.

The separate resolver answer key lives in
`work/release/source/speaker-practice-answer-key.json`. Keep it hidden from the
reviewer until practice labeling ends. The final acceptance sample must be drawn
after the release corpus is fixed and must include committee material and at
least 100 turns. Report precision using predicted councilmember attributions as
the denominator, preserve unresolved human labels, and meet the locked 0.85 gate.

## Approved actions and next boundary

The owner approved the isolated dependencies and the exact three-video probe.
These actions have executed as described above. All installations remain in
`work/release/tooling`, with no system/profile changes, shared database calls,
paid API calls, ASR, ingestion, or persistent service.

Pinned sources were the official
[PostgreSQL source directory](https://www.postgresql.org/ftp/source/v16.14/),
[pgvector tag](https://github.com/pgvector/pgvector/tree/v0.8.2),
[yt-dlp release](https://github.com/yt-dlp/yt-dlp/releases/tag/2026.10.26), and
[psycopg2-binary release](https://pypi.org/project/psycopg2-binary/2.9.11/).

The owner subsequently approved one final follow-up with the same three videos,
version, web client, and Chrome Default profile. Before cookie access, 30 local
caption tests passed, including mock cookie, keychain, network, and unclassified
errors, private-string redaction, stages, and deadlines. The follow-up used a
separate report path and an explicit ignored cache for any valid payload. It
completed once in 2.23 seconds within the 720-second budget, then stopped.

| Video | Cookie access | Listing | Listing return code | Safe error category | Caption download | Parsing | Payload retrieved |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MBjio010l60 | Unknown | Attempted, failed | 1 | unclassified_tool_error | Not reached | Not reached | No |
| rzdSGTDRRxI | Unknown | Attempted, failed | 1 | unclassified_tool_error | Not reached | Not reached | No |
| DP_mNBtgH1s | Unknown | Attempted, failed | 1 | unclassified_tool_error | Not reached | Not reached | No |

`work/release/source/caption-final-followup.json` records each observed stage,
and `caption-final-followup-execution.json` records the 2.23-second execution.
The first report remains separate. No raw errors, cookies, request headers, or
signed caption URLs were written to either report. No usable payload exists to
parse, and the outcomes do not prove absent captions. The final follow-up is
closed. An identical retry is not proposed. A later investigation would require
materially different evidence and an appropriately scoped new action.

The release corpus remains unfixed. Six authored legacy-fixture queries plus
the two separately authored cases need live traces, committee cases need
verified material, and no independent human labels have been received.

## Resume commands

All paths below are relative to the repository root. These reproduce local
verification with the approved installed tools.

```bash
CYP_TOOLING="$PWD/work/release/tooling"
TMPDIR="$CYP_TOOLING/tmp" PGBIN="$CYP_TOOLING/postgres/bin" \
  PYTHON="$CYP_TOOLING/venv/bin/python" \
  bash la-money-votes/scripts/transcripts/run_pg_tests.sh -v
cd la-money-votes
PYTHONPATH=scripts ../work/release/tooling/venv/bin/python -m unittest -v \
  scripts.transcripts.tests.test_diagnose_captions \
  scripts.transcripts.tests.test_discover_corpus
```

The approved caption investigation is closed after the final follow-up. Preserve
the frozen metadata and both probe reports. Shared target identity and live read
access are separate outstanding requirements before migration planning or paid
ingestion can proceed.
