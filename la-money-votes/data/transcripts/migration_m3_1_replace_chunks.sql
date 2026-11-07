-- M3.1 — transactional transcript replacement RPC.
--
-- Rationale (see scripts/transcripts/M3_1_RECONCILIATION_PLAN.md):
--   build_transcripts.py upserts by (video_id, chunk_idx, embedding_model).
--   That is idempotent for an unchanged parse, but leaves orphaned high
--   chunk_idx rows behind when a re-parse produces fewer chunks. A client-side
--   "upsert then delete" is NOT atomic: an interrupted run can leave a meeting
--   half-replaced and silently mixing two parses in one retrieval cohort.
--
--   This RPC performs staging validation, upsert, count verification, and
--   stale-key deletion inside a single transaction. Any RAISE rolls the whole
--   replacement back, so a video is either fully at the new parse or fully at
--   the old one -- never in between.
--
-- Security: writes are service-role only. The function is SECURITY INVOKER so
--   RLS still applies to the caller; anon/authenticated have no INSERT/UPDATE/
--   DELETE policy on transcript_chunks, and EXECUTE is revoked from them below.
--   This deliberately does NOT mirror the SECURITY DEFINER pattern -- a definer
--   write RPC reachable by anon would be an RLS bypass.

create or replace function replace_transcript_chunks(
    p_video_id text,
    p_embedding_model text,
    p_rows jsonb
)
returns table (
    intended_count bigint,
    upserted_count bigint,
    deleted_count bigint
)
language plpgsql
volatile
security invoker
as $$
declare
    v_intended   bigint;
    v_distinct   bigint;
    v_present    bigint;
    v_upserted   bigint;
    v_deleted    bigint;
    v_bad        text;
begin
    if p_video_id is null or length(trim(p_video_id)) = 0 then
        raise exception 'replace_transcript_chunks: p_video_id is required';
    end if;
    if p_embedding_model is null or length(trim(p_embedding_model)) = 0 then
        raise exception 'replace_transcript_chunks: p_embedding_model is required';
    end if;
    if p_rows is null or jsonb_typeof(p_rows) <> 'array' then
        raise exception 'replace_transcript_chunks: p_rows must be a jsonb array';
    end if;

    -- (2) Transaction-scoped lock for this (video, model) cohort. Two concurrent
    -- replacements of the same recording serialize here instead of interleaving
    -- their upsert and delete phases.
    perform pg_advisory_xact_lock(
        hashtextextended(p_video_id || '|' || p_embedding_model, 0)
    );

    -- (1) Stage the intended rows with explicit casts. A malformed payload
    -- fails here, before anything in transcript_chunks is touched.
    -- Dropped explicitly as well as ON COMMIT so that replacing several videos
    -- inside one transaction does not collide on the staging table.
    drop table if exists _staged_chunks;
    create temporary table _staged_chunks on commit drop as
    select
        (e->>'video_id')::text                                as video_id,
        (e->>'meeting_date')::date                            as meeting_date,
        (e->>'chunk_idx')::int                                as chunk_idx,
        (e->>'start_sec')::real                               as start_sec,
        (e->>'end_sec')::real                                 as end_sec,
        (e->>'source_label')::text                            as source_label,
        (e->>'resolved_role')::text                           as resolved_role,
        (e->>'resolved_official_id')::text                    as resolved_official_id,
        (e->>'resolved_name')::text                           as resolved_name,
        (e->>'resolution_method')::text                       as resolution_method,
        (e->>'text')::text                                    as text,
        (e->>'token_count')::int                              as token_count,
        (e->>'turn_speaker_raw')::text                        as turn_speaker_raw,
        coalesce((e->>'sub_chunk_idx')::int, 0)               as sub_chunk_idx,
        coalesce((e->>'sub_chunk_of')::int, 1)                as sub_chunk_of,
        (e->>'embedding')::vector                             as embedding,
        (e->>'embedding_model')::text                         as embedding_model,
        coalesce((e->>'embedding_version')::int, 1)           as embedding_version
    from jsonb_array_elements(p_rows) as e;

    select count(*), count(distinct chunk_idx) into v_intended, v_distinct
    from _staged_chunks;

    -- (3) Completeness and consistency checks on the staged set.
    if v_intended = 0 then
        raise exception
            'replace_transcript_chunks: refusing to replace % with an empty row set',
            p_video_id;
    end if;
    if v_distinct <> v_intended then
        raise exception
            'replace_transcript_chunks: chunk_idx values are not unique (% rows, % distinct)',
            v_intended, v_distinct;
    end if;

    -- Guard against a mixed payload silently rewriting a different cohort.
    select string_agg(distinct video_id, ',') into v_bad
    from _staged_chunks where video_id is distinct from p_video_id;
    if v_bad is not null then
        raise exception
            'replace_transcript_chunks: payload contains foreign video_id(s): %', v_bad;
    end if;
    select string_agg(distinct embedding_model, ',') into v_bad
    from _staged_chunks where embedding_model is distinct from p_embedding_model;
    if v_bad is not null then
        raise exception
            'replace_transcript_chunks: payload contains foreign embedding_model(s): %', v_bad;
    end if;

    -- Required metadata must be present on every staged row.
    select string_agg(chunk_idx::text, ',' order by chunk_idx) into v_bad
    from _staged_chunks
    where meeting_date is null or chunk_idx is null or start_sec is null
       or end_sec is null or resolved_role is null or resolution_method is null
       or text is null or length(trim(text)) = 0 or token_count is null
       or embedding is null or sub_chunk_idx is null or sub_chunk_of is null;
    if v_bad is not null then
        raise exception
            'replace_transcript_chunks: rows missing required metadata at chunk_idx: %', v_bad;
    end if;

    -- Wrong-dimension vectors must never reach the retrieval cohort.
    select string_agg(chunk_idx::text, ',' order by chunk_idx) into v_bad
    from _staged_chunks where vector_dims(embedding) <> 1024;
    if v_bad is not null then
        raise exception
            'replace_transcript_chunks: non-1024-dim embedding at chunk_idx: %', v_bad;
    end if;

    -- (4) Upsert every intended row.
    insert into transcript_chunks (
        video_id, meeting_date, chunk_idx, start_sec, end_sec,
        source_label, resolved_role, resolved_official_id, resolved_name,
        resolution_method, text, token_count, turn_speaker_raw,
        sub_chunk_idx, sub_chunk_of, embedding, embedding_model, embedding_version
    )
    select
        video_id, meeting_date, chunk_idx, start_sec, end_sec,
        source_label, resolved_role, resolved_official_id, resolved_name,
        resolution_method, text, token_count, turn_speaker_raw,
        sub_chunk_idx, sub_chunk_of, embedding, embedding_model, embedding_version
    from _staged_chunks
    on conflict (video_id, chunk_idx, embedding_model) do update set
        meeting_date         = excluded.meeting_date,
        start_sec            = excluded.start_sec,
        end_sec              = excluded.end_sec,
        source_label         = excluded.source_label,
        resolved_role        = excluded.resolved_role,
        resolved_official_id = excluded.resolved_official_id,
        resolved_name        = excluded.resolved_name,
        resolution_method    = excluded.resolution_method,
        text                 = excluded.text,
        token_count          = excluded.token_count,
        turn_speaker_raw     = excluded.turn_speaker_raw,
        sub_chunk_idx        = excluded.sub_chunk_idx,
        sub_chunk_of         = excluded.sub_chunk_of,
        embedding            = excluded.embedding,
        embedding_model      = excluded.embedding_model,
        embedding_version    = excluded.embedding_version,
        ingested_at          = now();
    get diagnostics v_upserted = row_count;

    -- (5) Verify the intended keys are all actually present BEFORE deleting.
    select count(*) into v_present
    from transcript_chunks c
    join _staged_chunks s
      on s.video_id = c.video_id
     and s.chunk_idx = c.chunk_idx
     and s.embedding_model = c.embedding_model;

    if v_present <> v_intended then
        raise exception
            'replace_transcript_chunks: post-upsert verification failed for % (% of % intended keys present); rolling back',
            p_video_id, v_present, v_intended;
    end if;
    if v_upserted <> v_intended then
        raise exception
            'replace_transcript_chunks: upsert touched % rows; expected %; rolling back',
            v_upserted, v_intended;
    end if;

    -- (6) Only now remove stale keys, scoped strictly to this cohort.
    delete from transcript_chunks c
    where c.video_id = p_video_id
      and c.embedding_model = p_embedding_model
      and not exists (
          select 1 from _staged_chunks s where s.chunk_idx = c.chunk_idx
      );
    get diagnostics v_deleted = row_count;

    return query select v_intended, v_upserted, v_deleted;
end;
$$;

comment on function replace_transcript_chunks(text, text, jsonb) is
    'Service-role-only transactional replacement of one (video_id, embedding_model) transcript cohort: validate staged rows, upsert, verify intended key count, then delete stale chunk_idx rows. Any failure rolls the whole replacement back.';

-- Ingestion writes only. Never reachable by browser clients.
revoke all on function replace_transcript_chunks(text, text, jsonb) from public;
revoke all on function replace_transcript_chunks(text, text, jsonb) from anon, authenticated;
grant execute on function replace_transcript_chunks(text, text, jsonb) to service_role;
