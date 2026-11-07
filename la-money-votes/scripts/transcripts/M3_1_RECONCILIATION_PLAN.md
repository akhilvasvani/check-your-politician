# M3.1 stale-chunk reconciliation boundary

`build_transcripts.py` currently upserts by
`(video_id, chunk_idx, embedding_model)`. That is idempotent for an unchanged
parse, but it does not remove higher indexes left behind after a parse produces
fewer chunks.

M3.1 does **not** add a client-side delete. A client upsert followed by a
separate delete is not atomic and could leave a recording partially replaced.

Before enabling stale-key removal, add and test a service-role-only
`replace_transcript_chunks` database RPC which, in one transaction:

1. takes one `video_id`, one embedding model, and the complete intended rows;
2. obtains a transaction-scoped lock for that video/model;
3. validates non-empty unique `chunk_idx` values and required row metadata;
4. upserts all intended rows;
5. verifies the exact intended key count; and only then
6. deletes rows for that video/model whose `chunk_idx` is not in the intended
   key set.

The RPC must be integration-tested in a disposable Supabase/Postgres project
for rollback behavior (invalid vector, duplicate index, interrupted request)
before it is applied anywhere. The local-only
`plan_stale_key_reconciliation` helper provides the exact intended/stale key
sets for those tests but performs no database operation.

## Status — implemented and tested (M3.1)

`replace_transcript_chunks` is implemented in
`data/transcripts/migration_m3_1_replace_chunks.sql` and satisfies all six
requirements above. `TransactionalReplacementIndexer` in `m3_1_ingest.py` is
the client seam: it groups rows into one `(video_id, embedding_model)` cohort
per RPC call, rejects duplicate indexes, missing embeddings, and
wrong-dimension vectors before any call, and treats the RPC's reported counts
as authoritative over the payload size. The client still issues no delete.

### Verification

`scripts/transcripts/run_pg_tests.sh` provisions a disposable Postgres 16 +
pgvector cluster on a free port, applies `schema.sql` and the migration, runs
17 integration tests, and tears the cluster down. It touches no Supabase
project. The tests cover the replacement happy path (shorter re-parse removes
exactly the stale keys, longer re-parse adds keys, repeat runs are idempotent),
cohort isolation (a replacement of one video/model leaves other videos and
other embedding models untouched), every staged-row rejection (empty payload,
duplicate `chunk_idx`, wrong embedding dimension, missing required metadata,
foreign `video_id`, foreign `embedding_model`, blank identifiers), both
post-upsert guards, and the grant posture (`anon`/`authenticated` cannot
execute the write RPC; `service_role` can; the read RPCs stay callable).

The two post-upsert guards are pinned separately, because they fail in
different ways. An `AFTER INSERT OR UPDATE` trigger that deletes an upserted
row leaves the statement row count correct and can only be caught by the
intended-key presence check; a `BEFORE INSERT` trigger that swallows a row is
caught by the row-count check. Both assert that the prior parse survives fully
intact, which is the property that makes a client-side delete unnecessary.

Each guard was mutation-tested: neutering the stale-delete model scoping, the
intended-key presence check, the row-count check, the duplicate-index check,
the empty-payload check, or the dimension check each turns the suite red.

### Still required before an online run

The migration has **not** been applied to any Supabase project. Applying it,
and the first live replacement, remain gated on the M3.1 caption blocker and
on explicit approval.
