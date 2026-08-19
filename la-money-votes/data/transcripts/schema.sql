-- Meeting-transcript RAG schema (Supabase / Postgres + pgvector).
-- Purpose: store one row per speaker turn (or sub-chunk of a long turn), with
--   speaker attribution, timestamp, video ID, and an embedding for retrieval.
--   See migration_m1_speaker_turns.sql for the M1 upgrade from 400-token
--   windows to per-turn chunks.
-- Design notes:
--   - transcript_chunks is additive to the existing schema. Nothing here touches
--     data/officials.json, funding.json, or record.json.
--   - embedding_model column lets us re-embed with a different model incrementally,
--     without a destructive migration. This session locked in
--     pplx-embed-v1-0.6b (1024-dim) for both ingestion and search, replacing
--     an earlier E5-small-v2 (384-dim) plan -- see build plan v5 addendum.
--   - source_label is the raw CART label ('T. McOsker', 'Council President', etc.),
--     preserved for audit. resolved_role and resolved_official_id are the joined-in
--     canonical forms, produced by scripts/transcripts/speaker_resolver.py.

create extension if not exists vector;

create table if not exists transcript_chunks (
    id                    bigserial primary key,
    video_id              text         not null,
    meeting_date          date         not null,
    chunk_idx             int          not null,
    start_sec             real         not null,
    end_sec               real         not null,

    -- speaker attribution (all denormalized for query-side simplicity)
    source_label          text,                      -- raw CART label, e.g. 'A. Nazarian' or 'Council President'
    resolved_role         text         not null,     -- 'councilmember' | 'presiding' | 'counsel' | 'clerk' | 'interpreter' | 'reporter' | 'public-speaker' | 'unknown'
    resolved_official_id  text,                      -- FK-like reference to data/officials.json ids (nullable — see roster.json)
    resolved_name         text,                      -- 'Adrin Nazarian' | 'Council President' etc. (denormalized display form)
    resolution_method     text         not null,     -- 'exact-role' | 'exact-councilmember' | 'fuzzy-from:<raw>' | 'unresolved'

    -- content
    text                  text         not null,
    token_count           int          not null,

    -- Speaker-turn provenance (M1). Chunks are scoped to a single utterance;
    -- long turns (>120w) are split into sentence-bounded sub-chunks that share
    -- the same turn_speaker_raw but differ in sub_chunk_idx / sub_chunk_of.
    -- See scripts/transcripts/chunker.py for the splitter and
    -- migration_m1_speaker_turns.sql for column semantics.
    turn_speaker_raw      text,
    sub_chunk_idx         int          not null default 0,
    sub_chunk_of          int          not null default 1,

    -- embedding (1024-dim, pplx-embed-v1-0.6b, cosine similarity).
    -- Perplexity embeddings are unnormalized -- use cosine distance
    -- (`<=>`), NOT inner product or L2. See:
    -- https://docs.perplexity.ai/docs/embeddings/best-practices
    embedding             vector(1024) not null,
    embedding_model       text         not null default 'pplx-embed-v1-0.6b',
    embedding_version     int          not null default 1,

    -- provenance
    ingested_at           timestamptz  not null default now(),

    unique (video_id, chunk_idx, embedding_model)
);

-- Retrieval index: HNSW on cosine distance.
create index if not exists transcript_chunks_embedding_idx
    on transcript_chunks
    using hnsw (embedding vector_cosine_ops);

-- Filter/browse indices
create index if not exists transcript_chunks_video_idx    on transcript_chunks (video_id, chunk_idx);
create index if not exists transcript_chunks_date_idx     on transcript_chunks (meeting_date desc);
create index if not exists transcript_chunks_official_idx on transcript_chunks (resolved_official_id) where resolved_official_id is not null;
create index if not exists transcript_chunks_subchunk_idx
    on transcript_chunks (video_id, resolved_official_id, sub_chunk_of, sub_chunk_idx)
    where sub_chunk_of > 1;

-- RLS: public read (D1 decision, 2026-08-19). transcript_chunks is a mirror of
-- publicly-broadcast LA City Council CART captions; writes are restricted to
-- service_role via the default "no policy" write behavior.
alter table transcript_chunks enable row level security;
drop policy if exists transcript_chunks_read_anon on transcript_chunks;
create policy transcript_chunks_read_anon
    on transcript_chunks
    for select
    to anon, authenticated
    using (true);

-- RPC used by api/search-transcripts.js.
-- Filters:
--   - p_embedding_model pins the vectors compared (defense against silent drift).
--   - p_official_id filters to a single councilmember (matches the "mounted panel
--     on official.html" MVP scope).
--   - p_date_from / p_date_to are optional ISO dates.
--   - p_min_similarity floors the cosine similarity of returned chunks.
--     Defaults to 0.35. Rationale: in the M0.2 v2 re-eval
--     (spike-m0/embed_bakeoff_v2_pplx.json, 2026-08-19), pplx-embed-v1-0.6b
--     scores off-topic chunks in the ~0.25-0.32 range and on-topic chunks
--     at ~0.37+. A 0.35 floor drops the false-positive class ("no chunk in
--     this corpus is about the query, but here are 5 procedural ones")
--     without dropping any documented true positive from that eval.
--     Set to 0 at call time to disable and see raw ranking.
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
      -- pgvector's `<=>` returns cosine *distance* (0 identical, 2 opposite),
      -- so `1 - distance` is similarity. Filtering on the raw distance keeps
      -- the ORDER BY able to use the HNSW `vector_cosine_ops` index.
      and (p_min_similarity <= 0
           or c.embedding <=> p_query_embedding <= (1 - p_min_similarity))
    order by c.embedding <=> p_query_embedding
    limit p_match_count;
$$;

comment on table transcript_chunks is
    'Per-chunk transcript store for LA City Council meetings. Additive to data/officials.json — no FK enforced because roster.json is the authoritative speaker table.';
