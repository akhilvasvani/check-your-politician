# Database changes awaiting separate approval

**REVIEW ONLY — neither A nor B has been applied to the shared project. Release
remains NO-GO.** Approve each exact forward SQL file and target separately.
Approval of preparation, local testing or project restoration is not execution
approval. Recovery files also require approval before use.

Target: Supabase `pwbothxnfjnxkhrcxyvd`, organization `la-politician`
(`lkcaqfydvsheedqghupd`), `us-west-2`, database `postgres`, executor `postgres`.
This is the project confirmed by the narrowly approved Vercel Preview URL read.
It remains active. Do not restore again or re-pause it. SQL guards cannot prove
the connected Supabase project identity; the executor must bind the tool's
`project_id` to this target and recheck it before execution.

## Reviewable artifacts and sequence

| Change | Exact forward SQL | Exact recovery SQL | Requested effect |
| --- | --- | --- | --- |
| A | [A-forward.sql](A-forward.sql) | [A-recovery.sql](A-recovery.sql) | Limit browser access on the one transcript table to SELECT; remove all browser privileges on its ID sequence. |
| B | [B-forward.sql](B-forward.sql) | [B-recovery.sql](B-recovery.sql) | Install the missing transactional replacement function; permit only the owner and service role to execute it. Do not invoke it. |

[SHA256SUMS](SHA256SUMS) binds all SQL, contract and prior-state evidence files.
The proposed order is A, read-only postflight, then B, read-only postflight, with
separate approval for each. Each is independently tested from the observed
baseline; B does not silently apply A. A alone leaves the replacement absent.
B alone leaves the existing broad table/sequence browser grants unresolved.

Before any approved execution, run [preflight.sql](preflight.sql),
[prerequisites.sql](prerequisites.sql) and [postflight.sql](postflight.sql) as
bounded reads and compare to the attached evidence. Inspect drift before doing
anything; do not broaden privileges or rewrite the proposal automatically.
The scripts abort for count, owner, RLS/policy, role-membership, column-ACL or
read-function-body drift. A additionally pins the complete observed object ACL.
B refuses to overwrite an existing signature. Run the complete approved file in
one transaction; do not split it into autocommitted statements. Stop after any
error and explicitly roll back an open transaction. Never retry an ambiguous
result without a read-only state check.

These are review scripts, not applied migration records. No migration-history
row, schema-cache notification or function invocation is included. Installation
method and any later history/cache operation must be reviewed within the exact
execution request; the files do not authorize extra SQL.

## Prior state and effective privileges

[prior-state.json](prior-state.json) records the November 7 04:03:33 UTC bounded
live snapshot. [prerequisites.json](prerequisites.json) supplements it with
service-role metadata and unchanged aggregate counts. Both were collected using
read-only transactions, 10-second statement limits and safe catalog/aggregate
results. No write-denial or destructive statement was attempted live.

Exact objects: `public.transcript_chunks` and
`public.transcript_chunks_id_seq`, both owned by `postgres`. The sequence is
owned by `transcript_chunks.id` and supplies its default. No column ACL or row
trigger was found. The expected corpus is **5,003 chunks / 3,341 parent turns /
9 recordings**. Existing read RPC bodies match the checked-in versions.

| Principal | Effective transcript table privileges before A | Sequence privileges before A | After A |
| --- | --- | --- | --- |
| `anon`, `authenticated` | SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER, MAINTAIN | SELECT, USAGE, UPDATE | SELECT on table; none on sequence |
| `service_role` | Same full table privileges | SELECT, USAGE, UPDATE | Unchanged; authorized ingestion dependency |
| `postgres` | Owner and full table privileges | Owner and full sequence privileges | Unchanged |
| `PUBLIC` | No grants on these two objects | None | None |

All captured object grants are direct from `postgres`, without grant option.
Recursive role-membership inspection and `pg_has_role` found no parent roles for
anon, authenticated or service_role; there is no inherited grant path to add to
these effective object privileges. A rejects new memberships rather than assuming
that direct revocation is sufficient. The owner/superuser capability is separate
from ACL entries and remains intact. Neither browser role is a superuser or
BYPASSRLS role. Neither browser role nor service_role can CREATE in public.

RLS is enabled with the one permissive SELECT policy
`transcript_chunks_read_anon` for anon/authenticated, `USING (true)`. This policy
and all read RPC ACLs/bodies remain unchanged. Table grants are excessive even
with SELECT-only RLS: TRUNCATE is outside row security. No live TRUNCATE test,
including a rollback-wrapped test, is permitted by this plan.
[PostgreSQL RLS](https://www.postgresql.org/docs/17/ddl-rowsecurity.html)

## Dependencies and read preservation

| Dependency | Required access and treatment |
| --- | --- |
| `search_transcripts(vector,text,date,date,text,integer,real)` | STABLE, SECURITY INVOKER, owner postgres; table SELECT and existing EXECUTE grants retained. Body MD5 `67e13f5e574b0ef81e124b42256b775d`. |
| `search_public_comment(vector,date,date,text,integer,real)` | Same read boundary. Body MD5 `33e4ba028630765299b3359a19b9a396`. |
| `get_transcript_coverage(text,text)` | Same read boundary. Body MD5 `22161cc4439ed49a91aae3b0146c2d7e`. |
| API `api/_lib/transcript-search-lib.js` | Calls those three RPCs using browser-level read credentials. Requires no table write, sequence privilege or replacement EXECUTE. |
| `scripts/transcripts/ingest_verified.py` | Reads a cohort with service credentials, then uses named replacement parameters only after a separately approved source/cost/write plan. No ingestion is authorized here. |
| Historical builder/backfill/ingestion tools | Administrative/service operations; no reviewed requirement for anon/authenticated writes. Service table/sequence privileges are retained. |
| Indexes, constraints, ID default, table type/TOAST and RLS policy | Catalog dependencies remain unchanged. No external view or foreign-key dependency was found in the bounded relation-dependency query. |

The catalog source scan found only the three named public read functions
referencing this table. Catalog dependencies cannot prove the absence of dynamic
SQL or external clients; repository call-site review supplies the application
cross-check. There is no schema-wide revocation or change to unrelated tables,
functions, policies, types, extensions, event triggers or roles.

## Creator defaults and recurrence

Captured public-schema defaults for creators `postgres` and `supabase_admin`
grant broad table/sequence privileges and function EXECUTE to anon,
authenticated and service_role. There were no separate global overrides in the
captured default-ACL rows. PostgreSQL's built-in function default also grants
EXECUTE to PUBLIC. These are object-creation defaults, not additional grants on
existing objects. They do not undo A by themselves, but recreating this table or
sequence under those creators could reintroduce broad access. New functions can
start with unwanted execution access.
[Default privileges](https://www.postgresql.org/docs/17/sql-alterdefaultprivileges.html),
[function/PUBLIC privileges](https://www.postgresql.org/docs/17/ddl-priv.html)

No schema-wide default change is proposed without reviewing other application
dependencies. A hardens only the existing named objects. Future transcript
creation/recreation must establish the same per-object ACL in its creation
transaction. The current bootstrap's additive SELECT grants alone do not remove
legacy default write grants. B handles its own function ACL before transaction
commit, including the PUBLIC default. Deployment/restore procedures must retain
these object-specific checks; project-wide default hardening is separate work.

## B: exact replacement contract

```sql
public.replace_transcript_chunks(
  p_video_id text,
  p_embedding_model text,
  p_rows jsonb
) RETURNS TABLE (
  intended_count bigint,
  upserted_count bigint,
  deleted_count bigint
)
LANGUAGE plpgsql VOLATILE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
```

Owner: `postgres`. Exact ordinary execution ACL after installation:
`postgres=EXECUTE`, `service_role=EXECUTE`, no grant option; PUBLIC, anon and
authenticated have no EXECUTE. Existing privileged owner/superuser capabilities
are not revoked. No role membership is added.

The source is checked-in `data/transcripts/migration_m3_1_replace_chunks.sql`
(SHA-256 `4236f13f9624d188b2857d859fac90a0fc263404354517d9dea621434b5bc84b`).
The transactional staging, validation, cohort advisory lock, upsert, stale-key
delete and intended-result contract are preserved. The review wrapper uses
CREATE (not CREATE OR REPLACE), pins owner/search_path/ACL, qualifies table and
vector extension references, and qualifies the temporary staging table. The
last change prevents a same-named public table from being dropped through an
untrusted search path. Installed body MD5 is
`dc3d667d0a6a03a86c823da31eff205f`; [contract.json](contract.json) pins input names,
return columns/types, language, mode and execution roles.

The INVOKER service role already has table and sequence privileges, BYPASSRLS,
public schema USAGE, vector type USAGE, vector_dims EXECUTE and database
CONNECT/TEMP. Those prerequisites were checked as metadata, without invoking the
replacement. Installation creates only the function/catalog grants. No staging,
embedding, replacement, delete or corpus write runs during installation. Future
service use must separately satisfy the existing exclusive-cohort-writer rule
and source, budget and approval gates. The ingestion target receipt must bind
the reviewed installed function metadata/hash as well as the checked-in source
contract; the source-file hash alone is not live-installation proof.

## Recovery, locks and availability

A recovery restores the exact captured broad browser grants on these two
objects, including TRUNCATE and sequence mutation privileges. This intentionally
reopens the identified exposure and is not an automatic response to a timeout.
It checks current read-only browser access and verifies the restored full ACL;
any drift rolls the transaction back. Owners, service grants, corpus and default
ACLs remain unchanged. Use only with explicit approval of that recovery risk.

B recovery drops only `public.replace_transcript_chunks(text,text,jsonb)`, with
no CASCADE and no row writes, restoring its prior absence. It pins body hash,
input names/types, output names/types, language, owner, security mode,
search_path and ACL before dropping. It refuses a changed contract, modified
function or new dependency; do not force recovery through such drift. Removing
the RPC would interrupt future ingestion calls but leaves existing reads.

Each forward/recovery transaction explicitly takes SHARE on the transcript
table so the before/after count checks cannot race with row writes. This permits
ordinary SELECT and blocks concurrent INSERT/UPDATE/DELETE and stronger
maintenance/DDL locks until commit/rollback. Catalog grants/function DDL also
serialize relevant catalog changes. A lock wait over 2 seconds fails; individual
statements have a 15-second limit. That is not a guaranteed total deployment
latency. Run without an intentional pause inside the transaction and coordinate
with any writers. Existing transactions or queued stronger locks can still
affect latency. No index rebuild or table rewrite is included.
[PostgreSQL lock conflicts](https://www.postgresql.org/docs/17/explicit-locking.html)

Disposable PostgreSQL 17 measurement observed AccessShareLock plus ShareLock on
the transcript table. Separate anon/authenticated count reads completed during
both open forward transactions. Final tests on both PostgreSQL versions repeat
that read test and confirm a competing no-row UPDATE reaches its lock timeout.
This demonstrates local lock compatibility, not production latency or complete
endpoint availability. Required read RPCs also execute successfully as both
browser roles in disposable tests before/after A and after B.

## Read-only postflight and stop rules

After each separately approved action, run [postflight.sql](postflight.sql) and
both independent transactions in [read-role-postflight.sql](read-role-postflight.sql).
All use READ ONLY and 10-second statement bounds; none calls an application RPC.
Expected counts are always 5,003 / 3,341 / 9, including under both browser roles.
After A: both browser roles have SELECT true, write/MAINTAIN/sequence false;
service access and the three read RPC bodies/ACLs are unchanged. After B: the
exact contract/owner/path/ACL above exists; the three read RPCs are unchanged.

Retain safe metadata/results and compare them to the prior evidence. If target,
counts, privileges, function metadata or required reads differ, stop and review.
Do not test live write denial, TRUNCATE, nextval/setval, replacement or recovery
as a diagnostic, even in a rollback. No automatic repair is authorized.

## Executed local evidence

| Configuration | Existing suite | Full review run | Failures / skips |
| --- | ---: | ---: | --- |
| PostgreSQL 16.14 / vector 0.8.2 | 18 existing cases included | **45 passed**, 18.140s | 0 / 0 |
| PostgreSQL 17.6 / vector 0.8.2 | Initial separate 18/18; included again below | **45 passed**, 14.273s | 0 / 0 |

Each 45-case run comprises 18 original contract tests, the same 18 applied to B,
and nine focused hardening/recovery/availability cases. Repetitions are not new
unique application tests. The earlier 492-test release baseline remains a
separate record; the entire app suite was not rerun in this preparation.
[validation.json](validation.json) binds the final SQL/test hashes and outcomes.

The first PG16 review run had one test-fixture failure: a test-only trigger used
an unqualified table under B's pinned path. Qualifying that fixture's table fixed
the test; the production function contract was not relaxed. Later 43-case runs
passed on both versions. Review then identified a missing full-signature guard;
it is now pinned and a same-body/changed-return-schema recovery regression passes.
Initial attempts to start the final runs inside the restrictive sandbox failed
before server start at loopback socket allocation. Authorized local execution
then passed; those setup logs remain separate from test results.

PostgreSQL 17.6's official archive SHA-256 matched the published checksum before
extraction: `e0630a3600aea27511715563259ec2111cd5f4353a4b040e0be827f94cd7a8b0`.
The existing approved pgvector 0.8.2 archive was built separately using PG17's
explicit pg_config, without extra packages. Runtime queries confirmed 17.6 and
vector 0.8.2. Prefix: `work/release/tooling/pg17/install`; PG16 is preserved.
Existing Python/psycopg2 were reused. Isolated clusters bound only loopback with
Unix sockets disabled, and the runner stopped/removed them on exit. The PG17
scratch directory is empty; two pre-existing caption scratch directories under
the PG16 scratch parent were preserved. Sources/binaries/logs/temp files remain
under ignored work/, outside tracked Git/deployment source. No persistent
service, sudo, global PATH/profile change or shared write occurred.
