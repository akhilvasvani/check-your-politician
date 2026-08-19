-- ---------------------------------------------------------------------------
-- Migration: M1.4 — align RPC default p_min_similarity with API constant.
--
-- The API (la-money-votes/api/search-transcripts.js MIN_SIMILARITY) always
-- passes p_min_similarity=0.25 explicitly, but the SQL default was still 0.35
-- (a leftover from the M0.2 initial estimate). The M1.4 empirical eval on
-- the full 5,003-chunk / 9-meeting corpus with 20 gold queries confirmed
-- 0.25 as the correct floor: parent@1 = 90%, parent@3 = 100%, min legitimate
-- top-1 similarity = 0.38, and floors 0.15-0.35 all produced identical hit
-- rates on this eval.
--
-- The full eval report is committed at:
--   la-money-votes/data/transcripts/eval_results_m1.4.json
--
-- Change: `create or replace function` with the same signature and body,
-- only p_min_similarity default flipped from 0.35 to 0.25. No RLS changes.
-- ---------------------------------------------------------------------------

create or replace function search_transcripts(
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

-- Execute grant is idempotent.
grant execute on function search_transcripts(
    vector(1024), text, date, date, text, int, real
) to anon, authenticated;
