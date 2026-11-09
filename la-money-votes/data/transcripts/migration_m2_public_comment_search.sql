-- M2.1 migration: search_public_comment RPC.
--
-- Symmetric to search_transcripts, but instead of filtering to a single
-- councilmember it filters to public speakers only (resolved_role =
-- 'public-speaker'). Rationale in scripts/transcripts/M2_PLAN.md:
--   - Public comment is a distinct, high-signal surface (~1,231 chunks out
--     of 5,003 in the current corpus), and mixing it into per-official
--     results dilutes both stories.
--   - There is no chunk_type column in the schema; resolved_role is the
--     canonical way we tag speakers in ingestion (see
--     scripts/transcripts/speaker_resolver.py).
--   - Sub-chunk metadata is included from day one so the UI can show
--     "part N of M" without a second migration.
--
-- Access: SECURITY INVOKER + relies on the existing
-- transcript_chunks_read_anon RLS policy (public select on the base table).
-- No new grants required — anon/authenticated already have EXECUTE on
-- functions in public by default. If that ever changes, add:
--   grant execute on function search_public_comment(...) to anon, authenticated;

create or replace function search_public_comment(
    p_query_embedding vector(1024),
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
    source_label text,
    turn_speaker_raw text,
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
        c.source_label,
        c.turn_speaker_raw,
        c.text,
        c.token_count,
        (1 - (c.embedding <=> p_query_embedding))::real as similarity,
        c.sub_chunk_idx,
        c.sub_chunk_of
    from transcript_chunks c
    where c.embedding_model = p_embedding_model
      and c.resolved_role = 'public-speaker'
      and (p_date_from is null or c.meeting_date >= p_date_from)
      and (p_date_to   is null or c.meeting_date <= p_date_to)
      and (p_min_similarity <= 0
           or c.embedding <=> p_query_embedding <= (1 - p_min_similarity))
    order by c.embedding <=> p_query_embedding
    limit p_match_count;
$$;

comment on function search_public_comment(vector, date, date, text, int, real) is
    'Semantic search over public-comment transcript chunks (resolved_role = public-speaker). Same signature/shape as search_transcripts minus p_official_id.';
