# Change A committed — release remains NO-GO

On November 8, 2026, the owner-approved Change A committed successfully on
Supabase `pwbothxnfjnxkhrcxyvd`, organization `la-politician`, `us-west-2`,
database/executor `postgres`. One execution attempt returned successfully at
08:29:42 UTC; all reviewed read-only postflight checks passed by 08:30:37 UTC
(00:30 Pacific). No verification failed or was ambiguous. Do not execute A again.

The unchanged [forward SQL](A-forward.sql) has SHA-256
`245a2122c42d14e315895ef9b0de6d079030f42beb6ece04017d42ee811cb415`.
Its bytes matched the SQL in [the approval packet](A-APPROVAL.md) and the prior
delivered copy at source commit `9e4507f3c691ee4dba44e2edd266246f3f971cc2`.
The 2-second lock timeout, 15-second individual statement timeout and SHARE lock
were retained. The connector returned success for the exact transaction ending
in COMMIT; subsequent independent read-only transactions observed its durable
privilege changes. No retry or recovery was attempted.

## Fresh preflight and resulting privileges

Target identity, ownership, role flags/memberships, PUBLIC and effective grants,
column ACLs, RLS/policy, function metadata, default privileges and corpus counts
matched the reviewed baseline before execution. Actual runtime was PostgreSQL
17.6 with vector 0.8.2. Safe evidence is in
[the refreshed preflight](A-preflight-2026-11-08.json) and
[comparison checks](A-preflight-comparison-2026-11-08.json).

| Principal | Effective table privileges after commit | Effective ID-sequence privileges |
| --- | --- | --- |
| `anon` | SELECT only; no INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER or MAINTAIN | None: USAGE, SELECT and UPDATE all denied |
| `authenticated` | SELECT only; no INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER or MAINTAIN | None: USAGE, SELECT and UPDATE all denied |
| `service_role` | Existing access preserved; reviewed SELECT/write/MAINTAIN categories match preflight | Existing access preserved |
| `postgres` | Existing ownership/access preserved by the exact statement set and transaction assertions | Existing ownership/access preserved |

Postflight used only the reviewed catalog query and two browser-role SELECT
transactions. It did not add a fresh exhaustive postgres ACL inventory: owner
preservation is supported by the unchanged grants and in-transaction assertions.
No browser write/destructive test or application RPC invocation ran live.

## Required reads preserved

All three functions remain owned by `postgres`, STABLE and SECURITY INVOKER.
Their existing unpinned search_path settings, full signatures, defaults, return
types, bodies and ACLs are unchanged. Existing EXECUTE for PUBLIC, postgres,
anon, authenticated and service_role remains present, without grant option.

| Read function | Unchanged body MD5 |
| --- | --- |
| `public.get_transcript_coverage(text,text)` | `22161cc4439ed49a91aae3b0146c2d7e` |
| `public.search_public_comment(vector,date,date,text,integer,real)` | `33e4ba028630765299b3359a19b9a396` |
| `public.search_transcripts(vector,text,date,date,text,integer,real)` | `67e13f5e574b0ef81e124b42256b775d` |

Catalog counts and separate read-only SELECTs as both `anon` and `authenticated`
each returned **5,003 chunks, 3,341 parent turns and 9 recordings**, unchanged.
This verifies SQL-role reads; HTTP credentials and deployed endpoints were not
tested. Full safe metadata and outcomes are in
[the execution receipt](A-execution-2026-11-08.json).

## Remaining gates and offline follow-up

- **Change B remains absent and unapproved.** Its existing installation-only
  [approval packet](B-APPROVAL.md) still requires separate exact-SQL/target
  approval and fresh preflight. A's observed post-state now supersedes its
  historical broad browser grants; do not compare future checks to the old
  baseline as if A were unapplied. B's SQL is unchanged.
- Creator default privileges are unchanged. They do not undo A automatically,
  but recreation can reintroduce excessive grants and needs exact-object review.
  Recovery is separately unapproved and would restore the broad prior grants.
- Caption probing remains stopped: listing-stage `unclassified_tool_error`,
  cookie access unknown, no caption payload tested. No absence/authentication
  conclusion, new probe, cookie access or ASR is inferred or authorized.
- Revised human practice labels and the frozen comparison remain unchanged.
  Target/identity/boundary holds remain; practice contributes zero items to the
  final independent >=100-turn held-out review against a verified release corpus.
- Original missing PRD requirements remain unresolved. Source/corpus expansion,
  relevance, independent attribution, HTTP credentials, limiter/spending controls
  and preview/release validation remain open.
- Remote publication remains blocked on unknown Vercel Git/build/branch settings
  and separate approval. The intended branch remains
  `release/weekend-2026-11-08`, with a proposed draft PR to `main`. No push, PR,
  workflow dispatch, environment change or deployment occurred.

Local follow-up only records this result and updates current release status.
Approved SQL, replacement contract, application code and frozen labels are
unchanged. The recorded 45/45 disposable tests on each of PostgreSQL 16.14 and
17.6 are retained; no database or full application suite was rerun for these
documentation changes. No replacement invocation, ingestion, paid call or
additional shared change occurred. **Release remains NO-GO.**
