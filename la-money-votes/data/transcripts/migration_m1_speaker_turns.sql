-- M1 migration (2026-08-19): speaker-turn chunking + RLS.
--
-- Two things happen here, both idempotent:
--
-- 1. Schema additions for the new speaker-turn chunker (scripts/transcripts/chunker.py):
--      - turn_speaker_raw:  the original CART label of the utterance the chunk came
--                           from. Duplicates source_label today (they're equal by
--                           construction after M1), but kept separate so a future
--                           reprocessing pass can rewrite source_label without
--                           losing raw provenance.
--      - sub_chunk_idx:     0-based position within a sub-chunked long turn.
--      - sub_chunk_of:      total sub-chunks emitted from the parent utterance
--                           (1 for whole-turn chunks). Together these let the UI
--                           join adjacent sub-chunks when a search hit spans a
--                           long monologue.
--
-- 2. RPC security posture: SECURITY INVOKER + a read-only RLS policy for anon.
--    Previously the RPC was created with the SQL default (INVOKER) but a hotpatch
--    on preview flipped it to DEFINER with a bare EXECUTE grant to anon so the
--    frontend could call it without bypassing RLS. That's a wider trust surface
--    than the data warrants: transcript_chunks is a public dataset (LA City
--    Council CART captions). This migration reverts to INVOKER and grants anon
--    a narrow SELECT policy on the underlying table so RLS approves the RPC's
--    read without a definer bypass.
--
-- Non-goals: no changes to officials.json / funding.json / record.json / build
-- scripts / refresh-data workflow. Additive to the existing schema.sql.

-- ---------------------------------------------------------------------------
-- 1. Schema additions (idempotent).
-- ---------------------------------------------------------------------------
alter table transcript_chunks
    add column if not exists turn_speaker_raw text;

alter table transcript_chunks
    add column if not exists sub_chunk_idx int not null default 0;

alter table transcript_chunks
    add column if not exists sub_chunk_of int not null default 1;

comment on column transcript_chunks.turn_speaker_raw is
    'Raw CART speaker label of the utterance this chunk came from. Preserved separately from source_label so a future rewrite can normalize source_label without losing provenance.';

comment on column transcript_chunks.sub_chunk_idx is
    '0-based position of this chunk within a sub-chunked long turn. 0 for whole-turn chunks.';

comment on column transcript_chunks.sub_chunk_of is
    'Total sub-chunks produced from the parent utterance. 1 for whole-turn chunks; N for the N sub-chunks of a long monologue split on sentence boundaries.';

-- Index to help the UI stitch adjacent sub-chunks back into a monologue.
create index if not exists transcript_chunks_subchunk_idx
    on transcript_chunks (video_id, resolved_official_id, sub_chunk_of, sub_chunk_idx)
    where sub_chunk_of > 1;

-- ---------------------------------------------------------------------------
-- 2. RLS + read-only policy for anon (D1 decision: 2026-08-19).
-- ---------------------------------------------------------------------------
alter table transcript_chunks enable row level security;

-- Public read on transcript_chunks. This table is a mirror of publicly-broadcast
-- LA City Council CART captions; there is no PII beyond speaker labels which are
-- already public record. Writes are restricted to service_role (default RLS
-- behavior when no write policy is defined).
drop policy if exists transcript_chunks_read_anon on transcript_chunks;
create policy transcript_chunks_read_anon
    on transcript_chunks
    for select
    to anon, authenticated
    using (true);

-- ---------------------------------------------------------------------------
-- 3. RPC: SECURITY INVOKER (D1). Body is unchanged from schema.sql; only the
--    security clause moves. `create or replace` is idempotent.
-- ---------------------------------------------------------------------------
create or replace function search_transcripts(
    p_query_embedding vector(1024),
    p_official_id text,
    p_date_from date default null,
    p_date_to date default null,
    p_embedding_model text default 'pplx-embed-v1-0.6b',
    p_match_count int default 8,
    p_min_similarity real default 0.35
)
returns table (
    id bigint,
    video_id text,
    meeting_date date,
    chunk_idx int,
    start_sec real,
    end_sec real,
    resolved_role text,
    resolved_official_id text,
    resolved_name text,
    text text,
    token_count int,
    similarity real
)
language sql
stable
security invoker
as $$
    select
        c.id,
        c.video_id,
        c.meeting_date,
        c.chunk_idx,
        c.start_sec,
        c.end_sec,
        c.resolved_role,
        c.resolved_official_id,
        c.resolved_name,
        c.text,
        c.token_count,
        (1 - (c.embedding <=> p_query_embedding))::real as similarity
    from transcript_chunks c
    where c.embedding_model = p_embedding_model
      and c.resolved_official_id = p_official_id
      and (p_date_from is null or c.meeting_date >= p_date_from)
      and (p_date_to   is null or c.meeting_date <= p_date_to)
      and (p_min_similarity <= 0
           or c.embedding <=> p_query_embedding <= (1 - p_min_similarity))
    order by c.embedding <=> p_query_embedding
    limit p_match_count;
$$;

-- INVOKER means the caller's role is what RLS checks; the anon SELECT policy
-- above is what lets the RPC read the table. The DEFINER-era anon EXECUTE grant
-- stays in place (harmless under INVOKER), but the trust surface is now RLS, not
-- a definer bypass.
grant execute on function search_transcripts(
    vector(1024), text, date, date, text, int, real
) to anon, authenticated;
