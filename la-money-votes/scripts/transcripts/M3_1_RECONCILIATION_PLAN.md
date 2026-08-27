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
