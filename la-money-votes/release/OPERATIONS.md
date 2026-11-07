# Release operations

Akhil Vasvani owns release approval, external spending approval and independent
speaker review. The local release operator executes the documented commands,
records results and prepares the evidence packet. Future transcript maintenance
is proposed for the owner-operated local host once a weekly cadence is approved.
This document specifies procedures. The release ledger records which procedures
actually ran and the remaining gates.

The November 6 bounded search found the checked-in M2/M3 plans, with no original
M1–M5 PRD in the checkout or available local project documents. Transcript
retrieval and the existing web-grounded Ask-AI are implemented as separate
surfaces. Transcript-grounded answer synthesis remains outside the verified
release implementation.

## Evidence and release identity

Record the exact Git SHA, environment, command, start/end time, exit status,
executed/pass/fail/skip counts and safe evidence path for each check. Classify
evidence as source inspection, historical report, mock, disposable database,
live read, preview or production. A migration file proves proposed SQL only.
An offline replay proves scoring against its recorded traces only.

The November 6 public-domain read found `index.html`, `official.html`,
`js/app.js` and `data/freshness.json` byte-identical to `main` at
`25a51ebe617f5d24c4a7c405a6498c2104f1a2fd`. GitHub's Vercel status identifies
deployment `HqsZGeeJAKYML6H8X5fuj1cj5iXb`, team `team-politicheck`, project
`check-your-politician`. These are sampled content and status observations.
The exact deployment-to-domain mapping and project settings still require
verification before release. Connected project listing subsequently resolved
project ID `prj_I1kOylFB27M1pABXw5luy5pgkjXv` and team ID
`team_aPlAJHap7jEuwyrs7qWcc9OL`. Scoped inspection requires owner team consent.

The connected Supabase account lists project `pwbothxnfjnxkhrcxyvd` in the
`la-politician` Free-plan organization. Its reported state is `INACTIVE` and
the migration read timed out. Target association, live schema, grants and corpus
counts remain unverified. Do not resume it without explicit approval for that
service-state change. Confirm restoration eligibility and repeat runtime/schema
verification afterward; the inactive metadata is not a live database result.

## Finance and public actions

The checked-in snapshot was generated at `2026-11-02T23:07:36+00:00`.
All 16 funding entries use `automated_api`, all have the employer/occupation
warning, and all 480 displayed donors have null employer fields. Every
public-action entry has `reviewed_through: null`.

Funding covers the committees listed in each `funding.json` source block and
at most the 30 donors with the largest eligible itemized totals. Amounts are
grouped by reported name. The report's committee ID is not a transaction ID.
Any employer enrichment first requires verified transaction keys and amendment/
duplicate semantics. Reporting-period ends describe filings represented by the
source rows. They do not certify complete campaign coverage.

Action fixtures include individually sourced proposals, seconding, explicit
votes and mayoral directives/orders. Roles, outcomes, recorded action dates and
term classifications are separate fields. Empty results describe the curated
sample. New `reviewed_through` attestations require a human review of the defined
official discovery sources. Successful rebuilds leave absent attestations unknown.

For coordinated publication, use `build_all.py`. The standalone funding/record
builders write published paths directly and bypass snapshot coordination.
The monthly finance workflow remains independent of transcript work.

From `la-money-votes/`, a local validation run uses an explicit report path.

```bash
python3 scripts/build_all.py --skip-freshness --report-path /tmp/release-build-report.json
git diff --exit-code -- data/officials data/freshness.json
```

Publication stages and validates the effective snapshot under a lock, verifies
backups, journals file replacements and hashes the complete published snapshot.
Handled failures before the verified commit point trigger rollback. Interrupted
runs must be recovered before another build. Inspect the journal and user changes
first, retain recovery evidence, then use the applicable approved recovery action.

```bash
python3 scripts/build_all.py --recover
python3 scripts/build_all.py --verify-run RUN_ID --report-path /path/to/the-run-report.json
```

`--recover` can restore files or remove completed run remnants. It refuses unsafe
or conflicting journal state. `--verify-run` is read-only. Never delete lock files,
backups or journals to force a build through. The full contract is in
[CONTRACT.md](../CONTRACT.md).

## Paid endpoints and outages

Generation uses Sonar. Transcript search uses `pplx-embed-v1-0.6b` plus the
Supabase read RPC. The read credential is `SUPABASE_ANON_KEY`. Service-role
credentials belong only in the explicitly approved ingestion environment.

| Boundary | Deadline | Automatic retries |
| --- | --- | --- |
| Each durable limiter request | 2 seconds | 0 |
| Query embedding request | 12 seconds | 0 |
| Supabase read RPC | 5 seconds | 0 |
| Web-answer generation | 22 seconds | 0 |

The overall server request deadline is 28 seconds and the browser deadline is
35 seconds. Sonar responses are capped at 600 output tokens.
Deadlines cover response parsing as well as headers. Client disconnects cancel
in-flight fetches. The checked-in Vercel ceilings are 30 seconds for paid
endpoints and 10 seconds for coverage. An upstream failure requires a deliberate
new user request. There is no automatic retry loop.

Ask-AI defaults to 5 requests per client in 600 seconds across officials.
Transcript endpoints share 10 requests per client per minute and 60 per hour.
Every paid endpoint also uses the shared 60-per-client hourly ceiling. The
Upstash counter increments and establishes/validates expiry through one atomic
script. A lost response can consume a slot. A missing, malformed or unavailable
limiter returns service unavailable before a paid call.

`ALLOW_IN_MEMORY_LIMITER=true` is restricted to local development and is refused
on Vercel or in production. Durable behavior, concurrent calls and the deployment
IP trust boundary still require an approved preview check. Per-client limits
alone do not establish a total external spending bound across all clients.
The owner must approve account-level budgets and the release's paid-call scope
before activation. No external spending amount is authorized by this runbook.

`ASK_AI_DISABLED=true` stops paid generation and
`TRANSCRIPT_SEARCH_DISABLED=true` stops paid transcript search. Static profiles
remain available. Vercel environment changes take effect through a new deployment,
so a production kill-switch operation must include its deployment approval.

JSON operational logs contain generated request IDs, endpoint, HTTP status,
duration and provider-call counts. They omit raw political questions, credentials,
provider bodies and transcript passages. Retain logs only through the configured
platform retention policy, and export aggregate results or redacted request IDs
for release evidence. Review error and latency rates without logging user content.

## Transcript maintenance

The supported source workflow is a local, nonprivileged Python environment with
the documented dependencies and an explicitly approved caption downloader.
Cookie access needs separate approval for the named browser/profile. Cookies,
signed caption URLs and raw VTT files remain outside Git and release artifacts.
The Linux-oriented disposable database runner needs an installed PostgreSQL/
pgvector environment or an approved adaptation on macOS.

Proposed cadence is one owner-operated metadata review per week, followed by a
bounded caption pass for new recordings after payloads become available. Keep
that cadence manual until approved. Discover a rolling 90-day Council and
standing-committee window and independently include the newest ten regular
Council sessions even when video is missing. Record exact window boundaries and
execution time in the manifest report. Discovery scope does not impose search
bounds or authorize deletion of older indexed recordings.

For each new unique video, require usable caption bytes, valid timing/text and
speaker cues. Retain safe source identity, downloader version, byte length and
hash evidence. Preserve every PrimeGov meeting identity sharing a recording.
Use the exact video ID for the join. Keep `ok`, `zero_byte`, `empty_with_error`,
`fetch_failed` and `not_offered` distinct. When the known-good control fails,
record the environment/authentication uncertainty.

For missing or delayed captions, record the specific blocked boundary and leave
the existing corpus available with its coverage dates and incomplete-record
message. After an initial bounded pass, permit one controlled diagnostic follow-up
only under the applicable approvals. Resume unresolved recordings at the next
approved source pass. Do not silently choose auto-generated captions or ASR.

Before any embedding or shared write, prepare the exact cohort, source hashes,
model/version, token/request estimate, owner-approved spend bound, Supabase
project ID, applied migrations/RPC signatures, grants/RLS and recovery backup.
A configured URL is insufficient proof of applied SQL or correct row counts.
Run all 17 replacement-RPC tests in a disposable PostgreSQL/pgvector environment.
Use transactional replacement, checkpoint each cohort, reconcile intended keys,
parent turns and distinct recordings, and demonstrate an idempotent rerun.
Resume from verified checkpoints with the same manifest and model/version.

The older nine-artifact corpus is historical evidence. Current live indexed
coverage must be independently read and reconciled before it is described as
current. The final expanded-corpus relevance artifact and held-out speaker sample
remain separate gates. At least 100 stratified turns require independent labels,
with councilmember attribution precision at least 0.85 using the predicted-
attribution denominator. Practice labels are diagnostic material only.

## Test commands

Run from `la-money-votes/` with supported Python and Node on `PATH`.
Fail if any expected module/file is missing or no tests execute.

```bash
python3 -m compileall -q scripts
python3 -m unittest discover -v
python3 scripts/validate_data.py
python3 scripts/build_all.py --skip-freshness --report-path /tmp/release-build-report.json
node --test tests/js/*.test.js
node --test tests/test-transcript-coverage.js
PYTHONPATH=scripts python3 -m unittest -v \
  scripts.transcripts.tests.test_backfill_meeting_dates \
  scripts.transcripts.tests.test_diagnose_captions \
  scripts.transcripts.tests.test_discover_corpus \
  scripts.transcripts.tests.test_eval_metrics \
  scripts.transcripts.tests.test_eval_replay \
  scripts.transcripts.tests.test_m3_1_ingest \
  scripts.transcripts.tests.test_ingest_verified
PYTHONPATH=scripts python3 -m unittest -v \
  scripts.transcripts.tests.test_replace_transcript_chunks
for file in api/*.js api/_lib/*.js js/*.js tests/js/*.test.js tests/test-transcript-coverage.js; do
  node --check "$file" || exit 1
done
git diff --check
```

The replacement tests need `TRANSCRIPT_TEST_PG_DSN` pointing to a disposable
PostgreSQL/pgvector database. Their 17 skips without a DSN count as unexecuted.
CI intentionally collects these as expected skips and cannot satisfy the database
release gate. Record the actual test counts in the release ledger, and run focused
browser checks separately with mock/preview/production evidence labels.

## Preparing a verified ingest operation

Use `scripts/transcripts/ingest_verified.py` for one recording. The default CLI
reads local inputs and emits a plan. Its required input files are a current
manifest, a valid manual CART VTT, hash-bound human caption review, and an
independently reviewed target receipt. Use `--help` for their exact fields.
The target receipt includes the prior cohort count/hash, schema/migration hashes,
model/version/dimensions, RPC/grant evidence files and their hashes. Source text
and unknown speaker labels require review before embeddings.

```bash
python3 scripts/transcripts/ingest_verified.py \
  --manifest /path/to/reviewed-manifest.json \
  --video-id VERIFIED_ID \
  --vtt /path/to/approved-caption.vtt \
  --caption-evidence /path/to/caption-review.json \
  --target-verification /path/to/target-review.json \
  --work-dir /path/to/ignored-cohort-directory
```

This command is a template, not a prepared or approved live operation. Source
captions and target access are still missing. Review the emitted plan hash,
maximum embedding attempts/input bytes, exact project and before-image evidence
before approving any paid/shared action. Execution adds `--execute` and
`--approved-plan-sha256` to the reviewed command with matching environment
configuration. These switches record operator intent and do not confer approval.

The inherited embedding client handles at most 100 texts per batch, with a
60-second socket timeout and up to five attempts for 429/transient server errors.
The plan reserves all attempts and a hard overall Unix signal deadline.
Generation/search endpoint retry policy remains separate. No corpus-wide cache
is introduced. A completed cohort reuses its verified local checkpoint, while
an interrupted embedding attempt requires spending reconciliation and a new
reviewed approval before more paid work.

The receipt must independently attest exclusive cohort writer ownership until
at least the full execution deadline. The existing RPC has no compare-and-swap
precondition, so that operating constraint is required across the last read and
write. The adapter verifies the current cohort both before embedding and directly
before replacement. A local nonblocking lock protects the approved execution
directory. Changed targets stop execution. An unknown write outcome is resolved
by reading and matching the checkpoint, with no blind replacement retry.

A successful replacement is checked against exact normalized rows, keys and
counts. The before-image and staged canonical artifact remain in the ignored
execution directory. All shared-recording PrimeGov identities are retained in
the artifact. The current table has no `source_meetings` column. Canonical-file
and manifest publication requires its own reviewed step and must not be inferred
from the database operation. An inconsistent post-write state requires review of
the checkpoint and before-image before an explicitly approved recovery action.
