# Proposed release requirements traceability

Prepared November 6, 2026 Pacific time. **Release decision remains NO-GO.**
This is a proposed traceability matrix assembled from recovered plans, the
owner's weekend mandate and subsequent owner decisions. It is not a recovered
original M1–M5 PRD, a new acceptance policy, or permission to release.

The implementation snapshot is `040cf6f2203a479f745f691cec9895534350b681`.
The evidence/documentation snapshot used below is local commit
`f0c0c40f8536720b7fb057efa02440e38518f945` on
`release/weekend-2026-11-08`. Later work must update evidence against its exact
reviewed SHA; a pass recorded here is not automatically inherited by a new diff.

## Recovery result and limits

The original M1–M5 PRD was **not recovered**. The bounded search inspected tracked
checkout documentation; document/plan filenames and milestone commit messages
across all 78 reachable local commits; the known owner attachment; and the
[GitHub all-state issue/PR collection][issues] (27 records returned, below the
100-record page limit). It then inspected [PR #22][pr22], its one Vercel bot
discussion comment and the early transcript milestone commit bodies. The
available refs were main `25a51ebe617f5d24c4a7c405a6498c2104f1a2fd`, transcript
`35a6abebdb6e1569db1862245ff4fd03911622d3`, and the local release branch.

The recovered planning documents are M2_PLAN.md, M3_PLAN.md and the M3.1
reconciliation plan. No original M4/M5 definition was found. Search connector
queries for PRD, M4, M5, requirements, milestone and transcript returned no
records, including transcript despite known PR #22; those empty search results
were not treated as proof of absence. The direct collection read supplied the
bounded GitHub cross-check. The local search receipt is
`work/release/requirements/search-receipt.json` (ignored operational evidence).

This search did not inspect unreachable Git objects, deleted remote branches,
unrelated filesystem locations, other workspaces/discussion systems, or the
hidden speaker answer key. It establishes absence within this search scope,
not absence everywhere. Existing implementation reports are not substitutes
for approved requirements.

Milestone names changed during development. Early [M1 ingestion][early-m1] and
[M2 search-panel][early-m2] commits precede the later M1.1–M1.4 and M2.0–M2.3
sequence. These labels cannot reconstruct a missing original M1–M5 roadmap.
The early M1 embedding choice was also superseded by the M2 search-panel
commit and the [locked M3 scope][m3-scope]. No retired model or destructive
re-embedding instruction is revived by this matrix.

## Source identities and evidence rules

| Source | Exact version and locator | Authority and limits |
| --- | --- | --- |
| M2 | [M2_PLAN.md][m2], transcript commit `35a6abebdb6e1569db1862245ff4fd03911622d3`, lines 1–182; initially introduced in `cebb4b124c75ef3f63a761c51ae1fbe12a5036f8` | Recovered plan. Requirements/acceptance text is usable; August result claims remain historical unless independently reverified. |
| M3 | [M3_PLAN.md][m3], same transcript commit, lines 1–310 | Recovered plan with locked scope and gates. Its August status paragraphs do not establish current service state. Both M2/M3 files are unchanged between that feature SHA and the evidence snapshot. |
| U1 | Owner attachment, *CHECK YOUR POLITICIAN — WEEKEND RELEASE EXECUTION MANDATE*, prepared November 6, 2026; 897 lines; SHA-256 `2638d63a11fe744885c28ba571ae04580a2cff16f1f631b5d039a38967b40a3e` | Primary owner instruction, not a Git blob or public URL. Section/line references below identify the supplied text exactly. It directs use of M2/M3 plus explicit release requirements when the PRD is unavailable (§2, lines 93–100). |
| U2 | Owner follow-up after the approved Supabase restore/read, recorded by the integrator in this release conversation | Primary continuation decision, not a recovered PRD: keep NO-GO; prepare two separate DB proposals and a remote preparation plan; stop caption probes; preserve hidden predictions; practice does not replace ≥100 held-out turns; no paid/ingestion/shared/remote mutations. No invented message URL or approval is supplied. |
| P | [RELEASE_PACKET.md](RELEASE_PACKET.md), snapshot `f0c0c40f8536720b7fb057efa02440e38518f945`; line ranges below refer to that snapshot | Evidence index, not requirement authority. Reports actual local/mock, disposable DB and live-read observations; it does not prove unexecuted preview or release behavior. Use `git show f0c0c40:la-money-votes/release/RELEASE_PACKET.md` for frozen line references if the current packet advances. |
| O | [OPERATIONS.md](OPERATIONS.md), same evidence snapshot | Proposed procedures and configured local behavior; not proof those procedures were executed or that ongoing maintenance/spending was approved. |
| G | [PR #22][pr22], read during this preparation; head `35a6abebdb6e1569db1862245ff4fd03911622d3`, updated October 19, 2026 06:24:49 UTC | Historical implementation report with stale fields and an unresolved Q&A/retrieval inconsistency. The single bot comment supplies no owner acceptance decision. |

Evidence categories are **source inspection**, **historical report**, **mock**
(including offline fixtures/local browser with mocked APIs), **disposable DB**,
**live read**, **preview**, and **production**. “Local passed” means the cited
packet records a pass in its stated category. It does not mean deployed or
accepted. This documentation pass did not rerun those checks. Current live
findings in P supersede older status paragraphs in the historical plans and
earlier operational notes. No preview of this release branch exists in the
cited evidence.

## Requirements matrix

Identifiers beginning `T-` are navigation labels introduced by this matrix,
not recovered milestone numbers. U1 line references are to the attachment
identified above. Exact plan links point to immutable GitHub blobs.

| ID / requirement | Requirement source and acceptance | Evidence and current status | Remaining gate or explicit unknown |
| --- | --- | --- | --- |
| T-01 Original scope and M5 quality | U1 §2 lines 77–100; §1 line 32. Recover original acceptance if available; otherwise use M2/M3 and explicit mandate without fabricating completion. | **Source inspection: incomplete recovery.** Search above found plans, not original PRD. | Original M1, M4 and M5 definitions remain unknown. M5 is the owner's quality target, not an inferred historical feature checklist. No milestone is waived. |
| T-02 Retrieval versus answer synthesis | [M2 lines 4–6, 41–46][m2-synthesis]; U1 §3 lines 117–128 and §12 lines 648–660. If originally required, synthesis is release work; otherwise prioritize verified retrieval and existing gates. | **Source inspection / historical report: unresolved.** G opening describes transcript Q&A backed by Sonar; G API/frontend section and current code describe retrieval. M2 explicitly defers augmentation. P lines 35–38 records no synthesis implementation. | Original synthesis requirement is unknown, not waived. M2 deferral establishes only M2 scope. If required/approved: define retrieval/answer contract, evidence-bound validated citations, distinct web/transcript claims, abstention and adversarial/outage tests before activation. No new paid answering surface authorized. |
| T-03 Preserve architecture and 16-profile product | U1 §2 lines 63–91; §3 lines 130–140. Preserve static UI/JSON, Python pipeline, Vercel APIs and Supabase; Mayor plus CD1–15. | **Source inspection / mock: local passed.** P lines 18–33, 269–283. | No framework/database/model migration, new geography, exhaustive roll-call, employer enrichment or ideology assessment inferred from missing PRD. Factual roster changes require current official-source verification. |
| T-04 Integrate current main and preserve publication | U1 §7 lines 293–339. Retain latest published bytes, freshness UI, staged publication/rollback, both CI suites and frozen-path guards; fail zero-test runs. | **Source inspection / mock: local passed.** P lines 16–26, 59–84: ancestry-aware merge, 492 distinct executed tests overall; dry build replaced zero files and published hashes match main. | Hosted CI for the integrated branch is pending approved push. Existing main/feature CI is historical, not current integration proof. The 16 missing-CSV funding builder skips are not skipped tests. |
| T-05 Calendar dates and source identity | [M2 R1, lines 61 and 89–98][m2-dates]; [M3 locked scope, lines 37–48][m3-scope]; U1 §10 lines 506–509. All nine baseline dates must match source meetings; exact video ID, no silent title/date/upload-date fallback. | **Historical report / live read: baseline reconciled.** P lines 153–163, 199–205 verifies nine indexed videos, dates and per-video parent counts against canonical artifacts. | Expanded corpus dates/provenance await verified captions and approved ingestion. M2's early “date proximity” proposal at line 75 is superseded by locked M3 and U1 exact-ID rules. |
| T-06 Public-comment retrieval | [M2 R2, lines 62 and 100–111][m2-public]. Separate public-comment RPC, SECURITY INVOKER, anonymous reads, seeded results; existing official search preserved. | **Source inspection / mock / live read: partial.** P lines 160–172 verifies read RPC bodies and actual browser SQL-role reads; lines 277–283 records separate result rendering and partial-failure checks with mocked APIs. | Seeded deployed endpoint/API-key smoke has not run for this release. Public comments must remain semantically separate from official speech. SQL-role SELECT is not HTTP RPC authentication. |
| T-07 Sub-chunk evidence | [M2 R3/R4, lines 63–64 and 113–120][m2-subchunks]. Return metadata and render part N of M; q13 example part 24 of 26. | **Historical report / source inspection / mock: implemented.** M2 reports shipped behavior; P lines 28–33, 269–283 covers local evidence UI. | Historical q13 live smoke in G does not satisfy current release preview smoke. Preserve full passage inspection and timestamp links. |
| T-08 M2 public relevance baseline and metrics | [M2 R5/R6, lines 65–66, 122–142][m2-eval]. Ten public-comment gold cases; parent@1 ≥0.60; parent@1/@3 reporting; embedding/RPC counts visible in logs. | **Historical report / mock: baseline retained.** M2 reports public 0.70/0.80 and official 0.90/1.00; P lines 222–241, 245–255 distinguishes replay from live evidence. | No new live evaluation/log verification. Official 0.90/1.00 is a reported locked comparison, not an invented original acceptance threshold. |
| T-09 Input, identity and read-credential safety | U1 §8 A–D, lines 348–368. Validate original trimmed length, real calendar dates/order and canonical official IDs; no service-role read fallback. | **Source inspection / mock: local passed.** P lines 28–33, 245–255. Invalid/malformed/privileged credentials fail before paid calls. | Syntactically valid credentials still need approved live authorization checks; production transcript environment is incomplete (P lines 114–120). |
| T-10 Bounded request lifecycle and durable abuse control | U1 §8 E/I, lines 370–373, 391–396; §13 lines 666–675. Deadlines/cancellation, defined retries, trusted client identity, atomic expiring durable counters, safe limiter outage. | **Source inspection / mock: local passed.** P lines 245–255; O lines 109–146. Server 28s/browser 35s; no endpoint automatic retries; shared 60/client/hour plus endpoint limits; missing limiter fails closed. | Live durable expiry/concurrency and deployment ingress behavior remain unverified. Per-client limits are not account spending caps. In-memory development fallback does not satisfy production. |
| T-11 Partial failures and evidence states | U1 §8 F–H, lines 375–389; §12 lines 640–646. Settle both sources independently; retain partial success; distinguish no match/zero/thin/unavailable/no roster; permanent incomplete-record message; similarity is not factual confidence. | **Mock: local passed.** P lines 269–283 records four official/public success/failure combinations, accessible statuses, coverage states, timestamps and passage expansion. | Needs approved deployed-preview verification. Mayor hides the transcript widget intentionally; empty results never prove silence. |
| T-12 Current discovery and taxonomy | [M3 lines 6–8, 35–68][m3-discovery]; U1 §9 lines 415–436. Council + standing committees including special meetings, explicit exclusions, exact identities, all states/missing reasons and actual newest ten including no-video sessions. | **Source inspection / mock / live read: observed inventory verified.** P lines 190–206 and [source inventory](source-status.md#observed-inventory): 101 in-scope rows, 35 Council/66 committee, 76 videos, 25 no-video, three window matches to canonical/live baseline. | Latest returned meeting is October 28; response completeness through November 6 unknown. Discovery is not retention or permission to delete six older recordings. Metadata-only inventory is not usable corpus evidence. |
| T-13 Usable captions and controlled diagnosis | [M3 lines 70–81][m3-ingest]; U1 §9 lines 438–464; U2 stops probes. Require payload bytes, valid timing/text/speaker cues and safe provenance; distinguish failure from source absence. | **Mock / live read: blocked.** P lines 208–218: two approved three-video probes completed; final listing code 1 / `unclassified_tool_error`; cookie success unknown; download/parsing not reached; no payload. | Probing is closed. No new cookie/video/client/version permutations, ASR or automatic-caption substitution authorized. Only offline recommendations may proceed now. Marking every meeting blocked does not satisfy committee retrieval/evaluation. |
| T-14 Corpus expansion and provenance | [M3 lines 83–105][m3-ingest]; U1 §10 lines 506–518. Newest ten published or reviewed source-specific missing reason; every in-scope 90-day meeting published or blocked; preserve every shared-video PrimeGov identity; never complete unknown sources. | **Source inspection / mock / live read: blocked.** P lines 199–205 verifies historical nine-video baseline only. Guarded adapter exists; no new corpus has been ingested. | Verified approved captions, exact target/cost/write approval and release-corpus freeze are missing. All-blocked status cannot substitute for required committee content. |
| T-15 Replacement integrity and disposable DB execution | U1 §10 lines 473–489, 510–515; [M3 reconciliation boundary, lines 83–97][m3-ingest]. Transactional cohort/model-scoped replacement, stale-key deletion, rollback, keys/counts, valid embeddings and idempotence. | **Disposable DB / mock: local passed.** [Recorded validation](database-review/validation.json): approved PG17.6 compatibility run and PG16.14 each passed 45/45 with vector0.8.2, including 18 original contract tests, the same 18 against B and 9 hardening/recovery/concurrent-read cases; no failures/skips. Existing adapter checkpoint/exclusivity/provenance mocks remain separate. | Adapter/replacement has not executed live; B remains absent. An exclusive cohort-writer window is required because RPC lacks compare-and-swap. Canonical artifact publication is a separate reviewed action. No suite rerun is claimed for November 8's documentation update. |
| T-16 Live target, least privilege and migration state | U1 §10 lines 491–504. Exact project, applied migrations/signatures, dimensions/model/version, constraints/counts/dates, RLS/grants and actual browser-role boundaries before any write. | **Partly complete: approved A committed November 8.** [Execution result](database-review/A-RESULT.md): fresh prior-state checks matched; browser SELECT only/no sequence privileges; all reviewed read-only postflight checks passed with unchanged read RPCs, service access and counts 5003/3341/9. | B remains absent after cancelled/expired confirmations; another submission needs a new explicit instruction and fresh preflight. HTTP credentials and deployed read behavior remain unverified. Creator defaults remain unchanged and require review on object recreation. A does not authorize B, recovery, replacement invocation or ingestion. |
| T-17 Coverage reconciliation and thin threshold | [M3 lines 107–153][m3-coverage]; U1 §10 lines 517–518. Parent turns and distinct recordings, pinned model, visible pre-search incompleteness; threshold derived from expanded distribution. | **Mock / live read: baseline reconciled, expansion pending.** P lines 49, 199–205. Nine-recording 5,003-child/3,341-parent baseline reconciles; CD8 direct count remains zero and generic presiding speech separate. | Provisional <20 turns or <5 meetings is historical, not validated for expanded corpus. Recompute after expansion. No unverified reassignment of all Council President turns. |
| T-18 Final M3 relevance coverage and execution | [M3 lines 241–271][m3-eval]; U1 §11 lines 533–557. Six untraced cases, grounded committee/chair/staff/procedural cases, entity/date/long-turn/low-signal/per-official coverage, QePVCuF0iAY and welTRe5_RH4 cases; mixed-RPC five-floor live run and final artifact. | **Historical report / mock: incomplete.** P lines 222–228: 30/36 replayable; 234/234 pooled candidates judged; two supplemental cases authored but unexecuted; final `eval_results_m3_3.json` absent. | Source-dependent committee cases, six original plus two supplemental live traces/pools, full run and final artifact remain. Existing 234 judgments must not be reauthored merely to show activity. |
| T-19 Relevance integrity and thresholds | [M3 lines 182–202, 226–235, 259–271][m3-eval-integrity]; U1 §11 lines 542–563. Full candidate key `(video_id, chunk_idx, sub_chunk_idx)`, stale-trace detection, no default-zero judgments, q06/q19 outcomes, graded/parent metrics and segmented regressions. | **Source inspection / mock: implemented, final acceptance open.** P lines 222–241. Strict replay reports missing traces instead of claiming full coverage. | M2 explicitly sets public parent@1 ≥0.60. M3 specifies graded reporting but no numerical nDCG cutoff. Any additional numerical threshold must be resolved before the acceptance run; no post-hoc cutoff or silent threshold waiver. |
| T-20 Independent practice review | U1 §11 lines565–582; U2 preserves blindness until completed labels; November7 owner revision authorizes comparison after freeze. | **Human submission / offline comparison: imported.** [Frozen revision and diagnostics](practice-review/README.md),12 items, original text preserved, exact source intervals retained. Key opened only after freeze. | [November8 adjudication](practice-review/adjudication-2026-11-08.json) supersedes01/03 with reviewer-reported exact-target Harris-Dawson labels, preserving the old freeze/predictions and Gemini provenance for03. Both differ from recorded personal-name predictions; no overall accuracy inferred. Item10 retains a target/identity hold;11/12 retain boundary limits. No twelve-item accuracy; practice contributes zero final acceptance items. Committee practice still needs verified material. |
| T-21 Held-out attribution precision | [M3 lines 273–285][m3-speaker]; U1 §11 lines 584–601. ≥100 stratified expanded-corpus turns; independent labels across Council/committee/presiding/procedural/fuzzy/public boundaries; councilmember attribution precision ≥0.85 with predicted-attribution denominator and false positives. | **Source inspection: not executed.** P lines 230–234: release corpus unfixed; no final sample or independent precision measured. | Establish corpus, record sampling/composition and held-out separation, obtain human labels and report unresolved cases. Mixed-item accuracy or agent self-labeling cannot satisfy this gate. Failure blocks M3. |
| T-22 Finance and public-action trust | U1 §2 lines 82–91; §12 lines 610–633. Explain selected committees/cycles, top 30, itemized totals/reporting period, employer gaps; separate motion/seconding/vote/outcome/date/term; preserve curated-sample disclosure under failure and unknown review dates. | **Source inspection / mock: local corrections passed.** P lines 53, 269–283; O lines 58–74. All 16 automated funding entries warn unavailable employer/occupation; 480 displayed employers null; all action review dates null. | No enrichment or invented review dates. Reliable transaction keys/amendment/duplicate semantics must precede enrichment. Current-source verification required before any factual roster/election change. |
| T-23 Operations, cost, outage and documentation | U1 §13 lines 666–705. Query-safe logs/IDs/durations/counts, safe rendering and secret handling, kill switches/static availability; named owner/host/cadence/source-delay/retry/manifest/staleness/recovery; distinct environments and real deployment identity. | **Source inspection / mock / live read: partly complete.** P lines 97–120, 243–267; O lines 3–8, 109–193. Production main/alias verified; release implementation/runbook and bounded secret scan prepared. | Production Supabase variables absent; HTTP key authorization, live limiter and spending controls unverified; kill switches not configured. Owner-operated weekly cadence is proposed, not approved. No cookies in Actions or finance schedule repurposing. |
| T-24 All-profile and accessibility regression | U1 §16 lines 802–818. Homepage/all16, desktop/390px, map/treemap/table/fallbacks, donor/actions/freshness, transcript states, source links, keyboard/live regions, clearance, no overflow/exceptions/rejections. | **Mock: local browser passed.** P lines 269–283 records all16 local Chromium profiles and targeted negative states; API traffic mocked, public tiles/assets read. | Approved exact-SHA preview and relevant real endpoint smoke remain. Local screenshots are not production evidence; no paid smoke is claimed. |
| T-25 Closeout, CI, exact-SHA release and recovery | [M3 lines 287–298][m3-closeout]; U1 §16 lines 820–856. Relevance, attribution, coverage/integration/browser gates; complete evidence packet; exact reviewed SHA/action/side effects, rollback/kill-switch plan, explicit approval and post-deploy identity/data/smoke. | **Source inspection: NO-GO.** P lines 40–55, 285–325. Local packet/runbook exists, but required source, evaluation, attribution, security, preview and operations gates remain. | U2 permits preparing exact branch/head/draft-PR target/workflow/Vercel effects only. No push, PR creation, dispatch, environment edit, merge or deployment/promotion is authorized. Only A was separately approved and executed; further shared SQL is unapproved. Final release and production checks remain unexecuted. |

## Decisions still unresolved

1. **Original acceptance scope:** original M1–M5 PRD, especially M4/M5 and
   transcript-grounded synthesis, is unavailable. The contradictory PR #22
   introduction is evidence to resolve if original scope becomes available;
   it is neither sufficient approval nor evidence of a waiver. Continue the
   explicit retrieval/M3/operations critical path under U1.
2. **Additional graded-ranking threshold:** M3 has no documented numerical
   nDCG acceptance value. Preserve documented M2 acceptance and locked
   comparisons, report all classes/regressions, and resolve any additional
   numerical policy before running acceptance. P lines 236–241 records a
   recommendation, not owner approval.
3. **Sources and independent acceptance:** current inventory completeness,
   usable committee captions, frozen release corpus, live relevance evidence
   and held-out human precision are unresolved. Diagnostic practice and
   historical replay cannot waive them.
4. **Live security, operations and release:** A closed the reviewed browser
   grant issue on November 8; the absent replacement RPC still needs separate
   approval. Live authentication,
   durable controls, spend bounds, approved maintenance cadence and exact-SHA
   preview/release remain pending. Corpus rows are unchanged; only A's exact
   object-privilege change has been applied.

The two database changes and remote preparation plan are independently tracked.
A's separately approved execution is recorded in its receipt; this matrix does
not grant approval for B or remote publication, or convert the release to GO.

Preparation addendum: [the A/B SQL packet](database-review/README.md) now contains
exact forward/recovery scripts, effective-privilege evidence and read-only
postflight checks. Its final disposable suite passed 45/45 on each of PostgreSQL
16.14 and 17.6, with no failures/skips. A subsequently committed under separate
November 8 approval; B remains absent after its separately approved submissions were cancelled/expired. The
[remote plan](REMOTE_VALIDATION_PLAN.md) records workflow/preview effects and
unresolved settings; no push or PR occurred. These findings supplement the
frozen P/O references above and do not close unknown requirements or human gates.

[issues]: https://api.github.com/repos/akhilvasvani/check-your-politician/issues?state=all&per_page=100
[pr22]: https://github.com/akhilvasvani/check-your-politician/pull/22
[early-m1]: https://github.com/akhilvasvani/check-your-politician/commit/660d188498d27354e75662fd7c743c1a8d1a09df
[early-m2]: https://github.com/akhilvasvani/check-your-politician/commit/f945e7dd800d1e3c5f74a2fac114ac80c953ecc2
[m2]: https://github.com/akhilvasvani/check-your-politician/blob/35a6abebdb6e1569db1862245ff4fd03911622d3/la-money-votes/scripts/transcripts/M2_PLAN.md
[m2-synthesis]: https://github.com/akhilvasvani/check-your-politician/blob/35a6abebdb6e1569db1862245ff4fd03911622d3/la-money-votes/scripts/transcripts/M2_PLAN.md#L41-L46
[m2-dates]: https://github.com/akhilvasvani/check-your-politician/blob/35a6abebdb6e1569db1862245ff4fd03911622d3/la-money-votes/scripts/transcripts/M2_PLAN.md#L89-L98
[m2-public]: https://github.com/akhilvasvani/check-your-politician/blob/35a6abebdb6e1569db1862245ff4fd03911622d3/la-money-votes/scripts/transcripts/M2_PLAN.md#L100-L111
[m2-subchunks]: https://github.com/akhilvasvani/check-your-politician/blob/35a6abebdb6e1569db1862245ff4fd03911622d3/la-money-votes/scripts/transcripts/M2_PLAN.md#L113-L120
[m2-eval]: https://github.com/akhilvasvani/check-your-politician/blob/35a6abebdb6e1569db1862245ff4fd03911622d3/la-money-votes/scripts/transcripts/M2_PLAN.md#L122-L142
[m3]: https://github.com/akhilvasvani/check-your-politician/blob/35a6abebdb6e1569db1862245ff4fd03911622d3/la-money-votes/scripts/transcripts/M3_PLAN.md
[m3-scope]: https://github.com/akhilvasvani/check-your-politician/blob/35a6abebdb6e1569db1862245ff4fd03911622d3/la-money-votes/scripts/transcripts/M3_PLAN.md#L35-L48
[m3-discovery]: https://github.com/akhilvasvani/check-your-politician/blob/35a6abebdb6e1569db1862245ff4fd03911622d3/la-money-votes/scripts/transcripts/M3_PLAN.md#L35-L68
[m3-ingest]: https://github.com/akhilvasvani/check-your-politician/blob/35a6abebdb6e1569db1862245ff4fd03911622d3/la-money-votes/scripts/transcripts/M3_PLAN.md#L70-L105
[m3-coverage]: https://github.com/akhilvasvani/check-your-politician/blob/35a6abebdb6e1569db1862245ff4fd03911622d3/la-money-votes/scripts/transcripts/M3_PLAN.md#L107-L153
[m3-eval]: https://github.com/akhilvasvani/check-your-politician/blob/35a6abebdb6e1569db1862245ff4fd03911622d3/la-money-votes/scripts/transcripts/M3_PLAN.md#L241-L271
[m3-eval-integrity]: https://github.com/akhilvasvani/check-your-politician/blob/35a6abebdb6e1569db1862245ff4fd03911622d3/la-money-votes/scripts/transcripts/M3_PLAN.md#L174-L271
[m3-speaker]: https://github.com/akhilvasvani/check-your-politician/blob/35a6abebdb6e1569db1862245ff4fd03911622d3/la-money-votes/scripts/transcripts/M3_PLAN.md#L273-L285
[m3-closeout]: https://github.com/akhilvasvani/check-your-politician/blob/35a6abebdb6e1569db1862245ff4fd03911622d3/la-money-votes/scripts/transcripts/M3_PLAN.md#L287-L298
