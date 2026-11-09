# Transcript ingestion and verification

The transcript feature retrieves passages from static canonical artifacts indexed
in Supabase PostgreSQL/pgvector. Query and document embeddings use
`pplx-embed-v1-0.6b`, 1,024 dimensions, embedding version 1. Speaker labels are
resolved deterministically through `roster.json` and role mappings. Public
comments use a separate search RPC. Web-grounded Ask-AI remains a separate
feature.

The operating owner is Akhil Vasvani. The supported execution host is a local,
unprivileged macOS or Linux shell with the required dependencies explicitly
approved and installed. Transcript refresh is a manually reviewed process.
Finance refresh keeps its existing workflow and schedule.

## Current evidence and gates

The nine checked-in canonical recordings contain 3,341 parent turns, with dates
from June 24 through August 14, 2026. Their existence proves local artifact
availability. Inspect the intended Supabase project before asserting live
index counts, migration status, grants, or current coverage.

M3.1 corpus expansion, M3.3 live evaluation, M3.4 independent speaker precision,
and M3.5 release acceptance remain open. The complete 234-candidate relevance
judgment pool and historical 30-query replay are preserved. Six authored queries
still lack traces, and committee cases require verified committee evidence.
The independent councilmember attribution precision gate is at least 0.85 on
the documented stratified sample of at least 100 turns. Practice labels are
separate from that acceptance sample.

## Dependencies and credentials

Inspect installed tools first. Installing packages, accessing browser cookies,
paid embedding/evaluation calls, and shared database writes each require the
owner's applicable approval for this release. Use a workspace virtual environment
and a local PostgreSQL prefix when approved. Avoid global package upgrades and
privileged helper-user creation.

Offline discovery, parsing, and evaluation helpers use Python standard-library
modules. Caption probing needs `yt-dlp`. Disposable database tests need
PostgreSQL 16, pgvector, and `psycopg2`. The legacy online builder imports
`supabase`, but it is not the approved replacement publication entry point.

| Credential | Purpose |
| --- | --- |
| `PERPLEXITY_API_KEY` | Approved embedding calls |
| `SUPABASE_URL` | Exact project target, verified before use |
| `SUPABASE_ANON_KEY` | Read-only search and coverage |
| `SUPABASE_SERVICE_ROLE_KEY` | Approved ingestion writes only |
| `TRANSCRIPT_TEST_PG_DSN` | Disposable test database only |

Keep secrets out of files, frontend assets, reports, and logs. Configure preview
and production independently. A credential being present does not establish
access, read/write boundaries, or applied migration state.

## Metadata inventory

Run from `la-money-votes/`, substituting the approved Python executable if the
shell's `python3` is unsuitable. Always choose a temporary output on the first
pass.

```bash
python3 scripts/transcripts/discover_corpus.py --days 90 \
  --output ../work/release/source/corpus-current.json
```

The newest-ten list includes regular Council sessions whose video URL is
missing. The discovery window follows the public PrimeGov API's archived-row
window. Record retrieval time, observed earliest/latest row dates, missing
videos, collisions, and excluded bodies. Search date bounds are separate from
discovery. Historical indexed rows remain subject to an explicit retention
policy, and must not be deleted merely because they are older than 90 days.

The manifest's legacy `already_published_videos` summary reflects local canonical
artifacts. Its `pipeline_state_basis` distinguishes this evidence. Reconcile live
rows independently before using publication counts in release claims.

## Caption feasibility

After tool and, if needed, cookie approval, probe the known control and explicit
current Council/committee samples. `--only-video` replaces the historical default
set. The following command runs one client and leaves cookie access disabled.

```bash
python3 scripts/transcripts/diagnose_captions.py \
  --out ../work/release/source/caption-probe.json \
  --workdir ../work/release/source/caption-probe \
  --only-video MBjio010l60 --only-video rzdSGTDRRxI \
  --only-video DP_mNBtgH1s --client web
```

Adding `--cookies-from-browser chrome` requires explicit approval. The diagnostic
ignores implicit yt-dlp configuration and automatic retry loops. Each subprocess
has a 120-second deadline. A single controlled follow-up may test the remaining
hypothesis after inspecting the first report. No automatic captions or ASR are
enabled.

`ok` requires an actual UTF-8 VTT payload, valid increasing cue times, nonempty
text, and speaker cues recognizable by the existing parser. The diagnostic
records payload hashes and counts, discards temporary VTTs, and keeps raw stderr
and signed URLs out of reports. Optional `--retain-usable-dir` preserves only
validated payloads in an explicitly approved ignored local cache. Cookie-source presence is reported without
claiming authentication succeeded. Listing failures are `fetch_failed`, not
proof that captions are `not_offered`. `zero_byte` and `empty_with_error` remain
separate outcomes. HTTP status remains unknown when the downloader does not
supply it. A failed control leaves environment/authentication/source ambiguity.

## Controlled publication

`m3_1_ingest.py` currently has an offline CLI that applies reviewed preflight
results to a local manifest. Inspect its supported arguments before use.
`--allow-partial` is explicit, with strict completeness by default.

`ingest_verified.py` uses `embed_and_index` and `TransactionalReplacementIndexer`
for one reviewed recording per invocation. Its default prepares an offline plan.
`--execute` requires an exact approved plan hash and a matching, independently
reviewed target receipt. The plan binds the execution directory, source hashes,
model/version, source identities and implementation hashes. Run `--help` for
receipt fields. Confirm target project, migration signatures, model/dimensions, security,
backup, exact keys/counts, cost bound, and recovery before requesting approval.
Demonstrate idempotence after the approved batch.

The legacy `build_transcripts.py` defaults to caption download, paid embedding,
and client upsert. Its `--no-embed` flag still downloads captions, may access
Chrome cookies, and writes canonical artifacts. Its `--video-id` path bypasses
meeting discovery. These are consequential operations and should not be used as
an offline verification shortcut or as the release replacement pipeline.

A SQL file in Git does not establish that it was applied. Inspect the target
schema and grants, propose only the exact missing migration, and obtain approval
before applying it. Never apply the whole SQL directory blindly.

## Tests and replay

From `la-money-votes/`, run the explicit offline modules used by CI.

```bash
PYTHONPATH=scripts python3 -m unittest -v \
  scripts.transcripts.tests.test_backfill_meeting_dates \
  scripts.transcripts.tests.test_diagnose_captions \
  scripts.transcripts.tests.test_discover_corpus \
  scripts.transcripts.tests.test_eval_metrics \
  scripts.transcripts.tests.test_eval_replay \
  scripts.transcripts.tests.test_m3_1_ingest \
  scripts.transcripts.tests.test_ingest_verified
node --test tests/test-transcript-coverage.js
node --test tests/js/*.test.js
```

For an already approved disposable PostgreSQL 16/pgvector installation, set
`PGBIN` to its `bin` directory and `PYTHON` to the environment containing
`psycopg2`, then run `bash scripts/transcripts/run_pg_tests.sh`. It uses a temporary
cluster and ephemeral localhost port, tears down on exit, and refuses root.
It does not install anything or create users on the machine. All 18 tests must
execute. Skips without a disposable DSN provide collection evidence only.
The tests execute coverage reads as both browser roles and replacement as
`service_role`, without implicit table grants. The bootstrap schema explicitly
grants public reads and service-role table/sequence access. Existing shared
grants must be inspected before proposing any migration; do not apply the
bootstrap file as a live repair.

Historical replay can be checked without paid calls.

```bash
PYTHONPATH=scripts python3 scripts/transcripts/eval_replay.py replay \
  --queries data/transcripts/eval_queries_m3_3.json \
  --trace data/transcripts/eval_results_m2.json \
  --out ../work/release/source/offline-replay-current.json \
  --require-full-coverage
```

This currently exits nonzero because only 30 of 36 queries have traces, even
though all 234 pooled candidates for those traces have judgments. It is not the
final expanded-corpus acceptance artifact.
