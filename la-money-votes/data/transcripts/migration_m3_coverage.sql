-- M3.2 migration: per-official transcript coverage aggregate.
--
-- "Speaking turns" count parent utterances, not retrieval chunks. A long turn
-- can be split into multiple rows by the M1 chunker; sub_chunk_idx = 0 occurs
-- exactly once per parent turn and prevents those long statements from
-- inflating the coverage number.
--
-- Access remains SECURITY INVOKER and relies on transcript_chunks_read_anon.
-- The endpoint pins p_embedding_model so a future re-embed cannot silently
-- double-count rows from two model versions.

create or replace function get_transcript_coverage(
    p_official_id text,
    p_embedding_model text default 'pplx-embed-v1-0.6b'
)
returns table (
    speaking_turns bigint,
    meeting_count bigint,
    first_meeting_date date,
    last_meeting_date date
)
language sql
stable
security invoker
as $$
    select
        count(*) filter (where c.sub_chunk_idx = 0)::bigint as speaking_turns,
        count(distinct c.video_id)::bigint as meeting_count,
        min(c.meeting_date) as first_meeting_date,
        max(c.meeting_date) as last_meeting_date
    from transcript_chunks c
    where c.embedding_model = p_embedding_model
      and c.resolved_official_id = p_official_id;
$$;

comment on function get_transcript_coverage(text, text) is
    'Read-only per-official transcript coverage. Counts one row per parent speaking turn (sub_chunk_idx = 0) and distinct indexed videos for one embedding model.';

grant execute on function get_transcript_coverage(text, text)
    to anon, authenticated;
