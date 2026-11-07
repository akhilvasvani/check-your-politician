# Weekend release evidence packet

Prepared November 6, 2026 Pacific time. **Release decision is NO-GO.** Required
source, live-service, evaluation and independent attribution gates remain open.
This packet records completed local engineering and actual evidence.

## Reviewed implementation and scope

Application and ingestion implementation reviewed at
`842cef06d194aa001b5713c4173eba8068c93a58` on local branch
`release/weekend-2026-11-08`. The packet/documentation commit follows that
implementation. The final local HEAD is reported in the handoff. A subsequent
workflow-only correction removes an unnecessary Bash 4 glob option while
preserving every frozen path pattern; the actual guard passes on the local shell.

Fetched main is `25a51ebe617f5d24c4a7c405a6498c2104f1a2fd` and transcript head is
`35a6abebdb6e1569db1862245ff4fd03911622d3`, with merge base
`92da1619fd454d4ed1a6549823cc3fefa625a976`. Their ancestry-aware merge retained
current published finance/action/freshness bytes and both CI suites.

Local commits through the reviewed implementation include integration `e191962`,
CI/guard protection `f0620ce`, API/evidence corrections `47136d7`, source/ingestion
work `c1d8f44`, and credential/fallback corrections `842cef0`.

Changes cover canonical API identity, original-length/calendar validation,
anonymous read credentials, bounded cancellation, atomic durable-limit counters,
shared client ceilings, fail-closed outages, safe citations/logging, kill switches,
independent search settlement, accessible partial results, permanent scope
messages, honest totals/empty states, current discovery, caption diagnostics,
and a reviewed single-recording ingestion plan/execute adapter.

The original M1–M5 PRD was not recovered in the bounded checkout/local-project
search. Checked-in M2/M3 plans and the explicit mandate govern this work.
Transcript-grounded synthesis is unestablished as an original requirement.
Existing web-grounded Ask-AI and transcript evidence retrieval remain distinct.

## Milestone decision

| Work | State | Remaining dependency |
| --- | --- | --- |
| W0 integration/publication baseline | Local checks passed | Remote CI for this branch awaits push approval |
| W1 API/UI correctness | Mock and browser gates passed | Production credential, ingress and durable limiter verification |
| W2 inventory/captions | Metadata verified, captions blocked | No usable new manual-caption payload |
| W3 database/replacement | 17 disposable DB tests passed, adapter mock-tested | Exact live project, applied SQL/grants, read boundary and approved write scope |
| M3.1 corpus expansion | Blocked | Verified source captions, target review, approved cost/write plan |
| M3.2 live coverage | Unverified for release corpus | Reconcile live parent turns and distinct recordings after corpus establishment |
| M3.3 relevance | Incomplete | Six missing original traces, two supplemental cases, grounded committee cases and full live five-floor run |
| M3.4 attribution | Pending human review | Practice labels, release corpus, held-out stratified sample of at least 100 turns, precision ≥0.85 |
| M3.5 closeout | Blocked | Relevance, attribution, coverage and live integration gates |
| W5 finance/action evidence | Local corrections passed | Future factual changes require independent source review |
| W6 operations | Code/runbook prepared | Live counter verification, account spending bounds and connected service settings |
| Public M5-quality release | NO-GO | Required gates above plus reviewed preview and exact-SHA release approval |

## Executed checks

The distinct local test suites total **491 passed, 0 failed, 0 skipped**.
Earlier baseline collection skipped 17 DB tests, which were later actually
executed in the approved disposable environment. They are counted once below.

| Command from la-money-votes | Passed | Failed | Skipped | Evidence category |
| --- | ---: | ---: | ---: | --- |
| `python3 -m unittest discover -v` | 265 | 0 | 0 | Offline pipeline fixtures |
| Explicit seven transcript modules listed in OPERATIONS.md | 132 | 0 | 0 | Offline fixtures/mocks |
| `node --test tests/js/*.test.js tests/test-transcript-coverage.js` | 77 | 0 | 0 | API/frontend mocks |
| `bash scripts/transcripts/run_pg_tests.sh -v` with approved local PGBIN/PYTHON/TMPDIR | 17 | 0 | 0 | Disposable PostgreSQL/pgvector |

Additional passes include compileall, 16 individual JavaScript syntax checks,
committed-data schema/cross-reference validation, `git diff --check`, the actual
frozen-path guard, and the CI Node positive-test-count gate. CI now rejects
zero-test pipeline/transcript/Node runs and retains explicit required files.

The staged dry build passed with 16 successful record builders and 16 funding
builders skipped because the manual CSV is absent. It replaced zero files.
Published finance/action/freshness hashes remained identical, and those paths
still match main. Funding builder skips are distinct from skipped tests.

Local tests used existing Python 3.12.14 and Node 24.22.1. Configured CI uses
Python 3.11 and Node 22; this branch has not run on hosted CI.

Safe command/result logs are in `work/release/final/`, baseline logs in
`work/release/baseline/`, and actual DB results in
`work/release/source/pg-executed.log`. They are local and ignored by Git.

## CI and deployment observations

GitHub read inspection found successful existing main test job
[126431270716](https://github.com/akhilvasvani/check-your-politician/actions/runs/41786983571/job/126431270716).
Draft PR #22 remains open at the fetched transcript SHA, with successful
historical guard and test jobs. These runs predate this integration.

The public domain served index.html, official.html, js/app.js and freshness.json
byte-identical to fetched main during the November 6 read. GitHub's Vercel status
reports deployment `HqsZGeeJAKYML6H8X5fuj1cj5iXb` for
`team-politicheck/check-your-politician`. Sampled assets establish content parity,
while exact build-to-domain/environment configuration remains unverified.
No preview was created for this local branch. Production was not changed.

## Database evidence

Approved local versions are PostgreSQL 16.14, pgvector 0.8.2 and
psycopg2-binary 2.9.11. All 17 replacement tests executed, covering rollback,
model/cohort isolation, stale keys, exact intended keys/counts, duplicate indexes,
invalid dimensions, idempotence, coverage visibility and role grants.

The runner bound an isolated temporary cluster to loopback on an ephemeral port.
It stopped and removed the cluster after tests. Cleanup verification found zero
temporary files. Installed sources/binaries remain only under ignored
`work/release/tooling/`, outside the Vercel application root.

No shared Supabase project has been identified or queried in this session.
Local credentials are absent and legacy installed CLI binaries are incompatible.
Supabase and Vercel integrations were found available but uninstalled and await
connection. Live migration signatures, constraints, RLS/grants, indexed counts,
model/version and anon/authenticated boundaries remain unverified.

## Current inventory and source evidence

The observed 90-day PrimeGov response contains 101 in-scope meeting rows,
35 Council and 66 standing-committee meetings, 76 distinct recordings, 25
missing-video rows and zero shared recordings within that response. Three match
local canonical artifacts. Seventy-three require caption preflight. The newest
returned meeting is October 28, so completeness through November 6 is unknown.
Actual newest-ten enumeration includes October 28 and 27 sessions without video.

Nine historical canonical artifacts remain intact, with 5,003 chunks and
3,341 parent turns in the historical baseline. Those figures are not a fresh
live database inspection. The discovery window has not imposed retention or
removed any indexed history. Detailed dates, source identities and response
hash are in [source-status.md](source-status.md).

Two explicitly approved three-video probes ran, first in 2.53 seconds and final
follow-up in 2.23 seconds. Both used yt-dlp 2026.10.26, Chrome Default and one web
client. Final per-video evidence is identical for MBjio010l60, rzdSGTDRRxI and
DP_mNBtgH1s. Cookie success is unknown; listing failed with code 1 and fixed
category `unclassified_tool_error`; download/parsing were not reached; no payload
was retrieved. Probing is closed. Listing failure supplies no evidence of absent
captions. A further investigation would need a materially different source/access
method and specific approval, supported by this evidence.

Reports retain safe metadata/hashes only. No raw errors, cookies, authorization
headers or signed caption URLs were retained. No ASR substitution occurred.

## Evaluation and independent labels

Offline replay covers 30 of the original 36 queries, with 234/234 pooled candidates
judged. The require-full-coverage command exits nonzero for the six missing
traces. That is an expected incomplete evaluation gate. Historical judgments
were preserved. Two additional authored cases are saved in
[source-evaluation-cases.json](source-evaluation-cases.json), with no claimed live
traces or newly reviewed retrieval pools. The final live
`eval_results_m3_3.json` is absent.

The [12-item practice worksheet](source-speaker-practice.md) is ready. The owner
will supply labels separately. Predictions remain in a hidden local answer key.
Practice is diagnostic and will not enter the held-out acceptance denominator.
The final ≥100-turn stratified review cannot be sampled against an unestablished
release corpus. Attribution precision and false positives are unmeasured.

Before live acceptance, retain the locked M1 official-case and M2 public-comment
comparisons and complete pooled judgments. M3 defines graded reporting without
a numerical nDCG threshold. The recommended predeclared policy is to preserve
those locked comparisons and report all expanded classes and regressions, with
no retrospective numerical cutoff. Confirm this policy with the owner before
an acceptance run if an additional numerical gate is required.

## Security and operations

Mocks verify input/identity/date rejection, read-credential shape/privilege
checks, preflight before paid calls, proper publishable/JWT headers, safe citation
schemes, kill switches, timeout/disconnect cancellation, per-client aggregate
ceilings and atomic Redis increment/expiry-result validation. Production durable
counter behavior and trusted ingress remain live gates.

API request deadline is 28 seconds, browser deadline 35 seconds, provider limits
are documented in [OPERATIONS.md](OPERATIONS.md), and paid generation is capped
at 600 output tokens. Endpoints do not automatically retry. The ingestion
adapter retains the existing separately budgeted embedding retry policy.
Syntactically valid credentials still require live authentication verification.

The adapter binds source/code/review/target/work-directory hashes, locks local
execution, saves a before-image, checkpoints uncertain outcomes and verifies exact
replacement content. It requires independently established exclusive cohort
writer ownership covering the full deadline. The existing RPC lacks
compare-and-swap, so that operating constraint is a prerequisite to shared use.
All adapter execution tests were mocked. Its staged canonical artifact preserves
shared PrimeGov identities; canonical publication is a separate reviewed action.

Tracked artifacts passed pattern checks for common credential literals, private
keys, signed caption URLs and environment files. This is a bounded scan, with no
claim that pattern matching detects every possible secret encoding.

## Browser evidence

Local Chromium checks passed the homepage and all 16 profiles at 1280px and
390px. They exercised map markers, treemap selection, donor sorting/filtering/
expanded details, action filtering, freshness, intentional Mayor transcript
hiding, mobile Ask-AI focus, and absence of horizontal overflow and unhandled
rejections. API traffic was mocked. Leaflet assets and public map tiles were read.

Focused mocked checks passed thin/zero/unavailable coverage, freshness outage,
all four official/public success/failure combinations, accessible status updates,
public-comment separation, empty results, timestamp URLs and full-passage
expansion. Map-load failure and no-JavaScript data access passed. The last
freshness line cleared the mobile floating button by approximately 27 pixels
in the measured 390px viewport. Screenshots and result JSON live in
`work/release/browser/`. No deployed preview or paid endpoint smoke is claimed.

## External usage, release action and recovery

Observed paid Perplexity generation/embedding calls are zero. Shared database
writes, remote pushes/PR creation, workflow dispatch and deployment/promotion
operations are zero. Public metadata/assets and the approved package/caption
requests were read. Tool version/download hashes are recorded in
`work/release/tooling/download-manifest.json`; published PostgreSQL and Python
wheel hashes were verified, while the pgvector archive hash is recorded without
claiming an unavailable published checksum.

No executable merge/deployment action is proposed while required gates remain
open. After those gates pass, resolve the exact final SHA and preview identity,
then request explicit approval for that precise push/merge/promotion and its
Vercel deployment effects. Existing historical approvals confer no release
permission. Never bypass branch protection.

Recovery procedures are in OPERATIONS.md. Finance publication recovery uses its
existing journal/backup verification. Shared transcript recovery requires the
reviewed before-image and explicit mutation approval. Paid endpoint kill switches
are `ASK_AI_DISABLED=true` and `TRANSCRIPT_SEARCH_DISABLED=true`; Vercel environment
changes need an approved deployment to take effect. Production rollback would
require identifying and approving the exact prior deployment. None was initiated.

## Resume order

1. Read this packet, the local `work/release/LEDGER.md`, current HEAD and working tree.
2. Verify Supabase/Vercel connection state and perform only the authorized live
   reads to resolve exact project/schema/grant/corpus/build identity.
3. Obtain usable verified manual captions through a materially different,
   approved source/access path. No identical caption probe remains authorized.
4. Finish independent practice review, then prepare reviewed cohort plans and
   exact paid/write approval bounds once sources and targets are known.
5. Establish the release corpus, complete grounded committee/live relevance
   evaluation and independent ≥100-turn attribution gate.
6. Validate the approved preview, refresh this evidence packet against its exact
   SHA, request release approval, and perform approved production smoke.
