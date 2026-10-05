-- M2.2 migration: extend search_transcripts to return sub-chunk metadata.
--
-- Adds two columns to the RPC's RETURNS TABLE:
--   sub_chunk_idx int
--   sub_chunk_of  int
--
-- These already exist on transcript_chunks (see migration_m1_speaker_turns.sql
-- and schema.sql). This migration only surfaces them through the search RPC
-- so the API layer + frontend can render a "part N of M" badge when a long
-- turn was split by the M1 chunker.
--
-- Postgres does NOT allow CREATE OR REPLACE FUNCTION to change the RETURNS
-- TABLE shape, so we DROP + CREATE. DROP is safe here: no view or trigger
-- depends on this RPC, and the frontend/API cache is stateless (each
-- request re-issues the RPC by name).
--
-- Additive to existing callers: they select fields by name from the returned
-- rowset, so adding columns doesn't break them.

drop function if exists search_transcripts(
    vector(1024), text, date, date, text, int, real
);

create function search_transcripts(
    p_query_embedding vector(1024),
    p_official_id text,
    p_date_from date default null,
    p_date_to date default null,
    p_embedding_model text default 'pplx-embed-v1-0.6b',
    p_match_count int default 8,
    p_min_similarity real default 0.25
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
    similarity real,
    sub_chunk_idx int,
    sub_chunk_of int
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
        (1 - (c.embedding <=> p_query_embedding))::real as similarity,
        c.sub_chunk_idx,
        c.sub_chunk_of
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
