# Weekend release evidence packet

Prepared November 6, 2026 Pacific time. **Release decision is NO-GO.** Required
source, shared-SQL, deployment, evaluation and independent attribution gates remain open.
This packet records completed local engineering and actual evidence.

**November 8 update:** [Change A committed](database-review/A-RESULT.md) after
exact-hash and fresh prior-state checks. Browser roles now retain table SELECT
only and no sequence privileges. All reviewed read-only postflight checks
passed, with counts unchanged at 5,003 chunks / 3,341 parent turns / 9 recordings.
Change B remains absent and unapproved; release remains NO-GO.

## Reviewed implementation and scope

Current implementation reviewed at
`040cf6f2203a479f745f691cec9895534350b681` on local branch
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
work `c1d8f44`, credential/fallback corrections `842cef0`, and explicit database
bootstrap grants with actual role execution tests `040cf6f`. API/frontend/ingestion
code is unchanged since `842cef0`. The bootstrap correction received a bounded
independent source review with no actionable findings.

Changes cover canonical API identity, original-length/calendar validation,
anonymous read credentials, bounded cancellation, atomic durable-limit counters,
shared client ceilings, fail-closed outages, safe citations/logging, kill switches,
independent search settlement, accessible partial results, permanent scope
messages, honest totals/empty states, current discovery, caption diagnostics,
and a reviewed single-recording ingestion plan/execute adapter.

The original M1–M5 PRD was not recovered in the bounded checkout/local-project
search or the subsequent bounded history/GitHub-artifact search. Checked-in
M2/M3 plans and the explicit mandate supply the proposed traceability matrix.
Transcript-grounded synthesis is unestablished as an original requirement.
Existing web-grounded Ask-AI and transcript evidence retrieval remain distinct.

## Milestone decision

| Work | State | Remaining dependency |
| --- | --- | --- |
| W0 integration/publication baseline | Local checks passed | Remote CI for this branch awaits push approval |
| W1 API/UI correctness | Mock and browser gates passed | Production credential, ingress and durable limiter verification |
| W2 inventory/captions | Metadata verified, captions blocked | No usable new manual-caption payload |
| W3 database/replacement | A committed November 8; read-only postflight passed; prior disposable A/B suite 45/45 on PG16.14 and 45/45 on PG17.6 | B absent and awaiting separate exact-SQL/target approval; no replacement invocation authorized |
| M3.1 corpus expansion | Blocked | Verified source captions, target review, approved cost/write plan |
| M3.2 live coverage | Existing 9-recording baseline reconciled live | Expanded release corpus remains unestablished |
| M3.3 relevance | Incomplete | Six missing original traces, two supplemental cases, grounded committee cases and full live five-floor run |
| M3.4 attribution | Revised practice annotations frozen and compared; diagnostic holds remain | Verified release corpus, held-out stratified sample of at least 100 turns, independent precision ≥0.85 |
| M3.5 closeout | Blocked | Relevance, attribution, coverage and live integration gates |
| W5 finance/action evidence | Local corrections passed | Future factual changes require independent source review |
| W6 operations | Code/runbook prepared | Live counter verification, account spending bounds and connected service settings |
| Public M5-quality release | NO-GO | Required gates above plus reviewed preview and exact-SHA release approval |

## Decision-ready follow-up — November 7

[Consolidated decision report](DECISION_REPORT.md) contains the practice import,
separate full-SQL [A](database-review/A-APPROVAL.md) and
[B](database-review/B-APPROVAL.md) approval packets, fresh read-only evidence,
[remote preflight](REMOTE_PREFLIGHT.md), and remaining gates. A/B forward/recovery
SQL and all recorded test inputs are unchanged; the45/45 results on PostgreSQL
16.14 and17.6 are reused, not rerun. The fresh privilege inventory exactly matches
prior state. No replacement overload or transcript row trigger exists. Existing
PostgREST DDL triggers can notify schema-cache reload on B creation/removal; this
platform side effect is now explicit in the B packet.

The standard Preview URL still identifies the existing Supabase project. Current
production/build/branch rules remain omitted by connectors; the now-available
browser reaches sign-in, not authenticated settings. Push remains blocked until
those rules are verified. No secret environment value, cookie, paid call,
ingestion, shared mutation or remote publication occurred. Annotation/report
commits require a new final source SHA in the external approval record.

## Bounded preparation follow-up

The owner accepted the preceding local completion and live read inspection and
kept NO-GO. The next review consists of four independently tracked items:

| Item | Concrete evidence / proposal | Still unresolved |
| --- | --- | --- |
| Exact database changes | [A/B review packet](database-review/README.md), forward/recovery SQL, prior-state inventory, SHA-256 manifest and read-only postflight | Approval for A and B separately on `pwbothxnfjnxkhrcxyvd`; no shared write performed |
| Release requirements | [Proposed traceability matrix](REQUIREMENTS_TRACEABILITY.md), 25 grouped requirements and bounded repository/history/GitHub search | Original M1/M4/M5 definitions and transcript-synthesis requirement remain unknown, unwaived |
| Remote validation | [Remote action plan](REMOTE_VALIDATION_PLAN.md) and [draft PR text](REMOTE_PR_DRAFT.md) | Final SHA bound in external approval record; push/PR/possible-preview authorization and unresolved deployment settings |
| Independent human review | [12 revised practice labels imported](practice-review/README.md), frozen before practice predictions were revealed | Target/boundary holds; final ≥100-turn held-out review against verified release corpus remains required |

Approved PostgreSQL 17.6 installation completed with official source checksum
verification and separate pgvector 0.8.2 build. Final review runs passed 45 tests
each on PostgreSQL 16.14 and 17.6, with zero failures/skips. Each includes the
existing 18 cases, their 18-case replay against proposed B, and nine focused
privilege/recovery/availability cases. Counts are configuration-specific, not
90 new unique app tests; the full application suite was not rerun. Both local
clusters stopped and were removed. Installation and test evidence is indexed
in [validation.json](database-review/validation.json).

Fresh live catalog reads identify direct broad browser grants, no PUBLIC grants
on the table/sequence, no parent role memberships, and broad creator defaults
that could reintroduce access on recreation. Service RPC prerequisites are
present. Counts remain 5,003 chunks / 3,341 parent turns / nine recordings.
A preserves SELECT and all three read RPCs; B installs only the tested function
with pinned contract/search_path and service-only execution. These remain local
review files. No live destructive/write-denial test or replacement invocation ran.

Caption probing stays closed with listing-stage `unclassified_tool_error`,
cookie access unknown and no retrieved payload. The offline recommendation in
[source-status.md](source-status.md) does not authorize another probe.

## Executed checks

The previously reported application baseline totals **492 passed, 0 failed, 0 skipped**.
Earlier baseline collection skipped 17 DB tests, which were later actually
executed in the approved disposable environment. A follow-up strengthened the
read-role test and added a service-role execution test, bringing that suite to
18. After the bootstrap fix, all 18 executed successfully. Unchanged suites
retain their preceding verified results; repeated runs are not double-counted.

| Command from la-money-votes | Passed | Failed | Skipped | Evidence category |
| --- | ---: | ---: | ---: | --- |
| `python3 -m unittest discover -v` | 265 | 0 | 0 | Offline pipeline fixtures |
| Explicit seven transcript modules listed in OPERATIONS.md | 132 | 0 | 0 | Offline fixtures/mocks |
| `node --test tests/js/*.test.js tests/test-transcript-coverage.js` | 77 | 0 | 0 | API/frontend mocks |
| `bash scripts/transcripts/run_pg_tests.sh -v` with approved local PGBIN/PYTHON/TMPDIR | 18 | 0 | 0 | Disposable PostgreSQL/pgvector |

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
`team-politicheck/check-your-politician`. After owner team authorization,
authenticated Vercel inspection verified project ID
`prj_I1kOylFB27M1pABXw5luy5pgkjXv` under team
`team_aPlAJHap7jEuwyrs7qWcc9OL` (`team-politicheck`). The public alias maps to
`dpl_HqsZGeeJAKYML6H8X5fuj1cj5iXb`, READY for production, with GitHub commit
`25a51ebe617f5d24c4a7c405a6498c2104f1a2fd` and ref `main`. The public domain
and `check-your-politician.vercel.app` are verified without branch-specific
domain bindings. This independently resolves the sampled build/domain identity.

The project specifies Node `24.x`, matching the major version used locally.
Configured root-directory and production-branch settings were not returned by
the connector. No preview was created for this local branch. Production was
not changed. Safe evidence is in `work/release/live-services/vercel-verified.json`.

The initial environment names/scopes inspection did not decrypt or retain values.
`SUPABASE_URL` and `SUPABASE_ANON_KEY` exist only in Preview, leaving production
transcript configuration incomplete. Limiter `KV_REST_API_URL`/`KV_REST_API_TOKEN`
and `PERPLEXITY_API_KEY` names exist in Preview and Production. Neither
`ASK_AI_DISABLED` nor `TRANSCRIPT_SEARCH_DISABLED` is configured. Credential
validity, deployed function environment snapshots, store behavior and spending
controls remain unverified. No environment changes were made.

## Database evidence

Approved local versions are PostgreSQL 16.14, pgvector 0.8.2 and
psycopg2-binary 2.9.11. All 18 replacement tests executed, covering rollback,
model/cohort isolation, stale keys, exact intended keys/counts, duplicate indexes,
invalid dimensions, idempotence, coverage visibility and role grants. Stronger
role tests first reproduced two permission failures without implicit grants.
Explicit bootstrap SELECT grants for browser roles and table/sequence grants
for the service role fixed both. The suite now executes coverage reads as anon
and authenticated and replacement as service_role. Its BYPASSRLS setting exists
only in the disposable test fixture. No bootstrap SQL was applied remotely.

The latest executed log is `work/release/source/pg-explicit-grants-after.log`
(18 passed in 0.147 seconds). The preceding failure is preserved separately.
This follows Supabase's [new-table grant change](https://supabase.com/changelog/45329-breaking-change-tables-not-exposed-to-data-and-graphql-api-automatically).
The platform change does not by itself establish that the existing transcript
table is broken. The subsequent live read confirmed that its read grants work.

The runner bound an isolated temporary cluster to loopback on an ephemeral port.
It stopped and removed the cluster after tests. Cleanup verification found zero
temporary files. Installed sources/binaries remain only under ignored
`work/release/tooling/`, outside the Vercel application root.

The owner approved a narrow Preview URL read and one conditional restore.
`SUPABASE_URL` identified `pwbothxnfjnxkhrcxyvd.supabase.co`, with no override for
`release/weekend-2026-11-08`. This confirmed project `pwbothxnfjnxkhrcxyvd` in
the `la-politician` Free-plan organization (`lkcaqfydvsheedqghupd`), `us-west-2`.
Its refreshed state was INACTIVE. One `restore_project` call succeeded; the
project reached ACTIVE_HEALTHY by 03:21:08 UTC on November 7 (November 6 Pacific).
It was left active as instructed. No plan change or additional repair occurred.

Nine bounded SQL inspections used read-only transactions and 10-second statement
limits. They invoked no application functions and returned safe metadata or
aggregates. Actual runtime is PostgreSQL 17.6 with pgvector 0.8.2. The table uses
`vector(1024)`, model `pplx-embed-v1-0.6b`, version 1, and a unique key on
`(video_id, chunk_idx, embedding_model)`. The checked integrity aggregates found
zero duplicate full keys and zero invalid timing/subchunk/empty-text rows.

Five applied migration records run through `20260820042036_m3_transcript_coverage`.
The three read RPCs are STABLE and SECURITY INVOKER, and their body hashes match
the checked-in SQL. The transactional `replace_transcript_chunks` RPC is absent.
Its migration still needs separate review and approval before ingestion.

The original live reads found 5,003 chunks and 3,341 parent turns under both
anon and authenticated, with SELECT-only RLS but excessive object grants.
Approved Change A on November 8 removed those browser write/destructive and
sequence privileges. Its reviewed read-only postflight confirms SELECT only
and no sequence access for both roles, unchanged read RPCs/service access, and
5,003 chunks / 3,341 parent turns / 9 recordings under each browser role.
See [the exact execution receipt](database-review/A-execution-2026-11-08.json).
No corpus rows, RLS policy or read functions were changed. No live write or
destructive probe was run. SQL-role reads do not establish HTTP API-key or
deployed-endpoint authentication.

The security advisor returned four warning types: mutable function search path,
extension in public, and anon/authenticated execution of a SECURITY DEFINER
function. Catalog inspection identifies that definer as `rls_auto_enable`, an
event-trigger function attached to `ensure_rls` on `ddl_command_end`, with
`search_path=pg_catalog`; neither browser role can CREATE in public. It was not
invoked or modified. See the [search-path warning](https://supabase.com/docs/guides/database/database-linter?lint=0011_function_search_path_mutable),
[extension warning](https://supabase.com/docs/guides/database/database-linter?lint=0014_extension_in_public),
and [definer warning](https://supabase.com/docs/guides/database/database-linter?lint=0028_anon_security_definer_function_executable)
for context before proposing changes. No `cron.job` table or pg_cron/pg_net
extension was found; activity by other clients was not measured.

`work/release/live-services/database-verified.json` contains the safe live
findings. `database-restore-receipt.json` records the single restore. These and
`vercel-verified.json` supersede the initial access-blocked report. No key/token
values were read. The only inspected environment value was the approved URL.

## Current inventory and source evidence

The observed 90-day PrimeGov response contains 101 in-scope meeting rows,
35 Council and 66 standing-committee meetings, 76 distinct recordings, 25
missing-video rows and zero shared recordings within that response. Three match
local canonical artifacts. Seventy-three require caption preflight. The newest
returned meeting is October 28, so completeness through November 6 is unknown.
Actual newest-ten enumeration includes October 28 and 27 sessions without video.

The post-restore live read independently confirmed the nine historical recordings,
5,003 chunks and 3,341 parent turns, dated June 24 through August 14. Per-video
parent counts match all nine canonical artifacts. This is now a verified live
baseline, not an expanded or current rolling corpus. CD8 has zero resolved
district-attributed turns; generic presiding turns remain separate, and this is
not evidence of silence. The discovery window has not imposed retention or
removed history. Detailed dates, identities and response hash are in
[source-status.md](source-status.md).

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

The [12-item practice worksheet](source-speaker-practice.md) is preserved. The
owner’s revised annotations were frozen before comparison with the previously
hidden practice key on November7; [import and diagnostics](practice-review/README.md)
preserve the original submission, corrections, name spellings and target intervals.
No identity accuracy is calculated:10 named submissions include target/boundary
holds;2 items retain unresolved identities. Practice contributes zero held-out
acceptance items and its predictions are now unblinded for diagnostics only.
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

Agent-initiated paid Perplexity generation/embedding calls are zero. One approved
shared object-privilege change (A) committed November 8; no shared corpus-row or
function/schema-definition change occurred. Remote pushes/PR creation, workflow
dispatch and deployment/promotion operations are zero. One explicitly approved
Supabase service restore completed earlier. It may reactivate other clients;
their activity or cost was not measured. Public metadata/assets and the approved package/caption
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
2. Keep the restored Supabase project active. Do not repeat restoration or A.
   A committed and passed read-only postflight. The missing replacement-RPC
   change B still needs separate exact-SQL/target approval and fresh preflight;
   its installation does not authorize invocation or ingestion. Production
   transcript configuration,
   HTTP credential verification, live limiter behavior and spending bounds remain
   gates for later approved configuration and preview work.
3. Obtain usable verified manual captions through a materially different,
   approved source/access path. No identical caption probe remains authorized.
4. Resolve practice target/boundary holds, then prepare reviewed cohort plans and
   exact paid/write approval bounds once sources and targets are known.
5. Establish the release corpus, complete grounded committee/live relevance
   evaluation and independent ≥100-turn attribution gate.
6. Validate the approved preview, refresh this evidence packet against its exact
   SHA, request release approval, and perform approved production smoke.
