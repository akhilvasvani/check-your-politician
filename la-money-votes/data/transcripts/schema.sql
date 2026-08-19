-- Meeting-transcript RAG schema (Supabase / Postgres + pgvector).
-- Purpose: store one row per 400-token chunk, with speaker attribution, timestamp,
--   video ID, and a 384-dimensional embedding for retrieval.
-- Design notes:
--   - transcript_chunks is additive to the existing schema. Nothing here touches
--     data/officials.json, funding.json, or record.json.
--   - embedding_model column lets us re-embed with a different model incrementally,
--     without a destructive migration. Cf. build plan v5 §"M0.2 findings".
--   - source_label is the raw CART label ('T. McOsker', 'Council President', etc.),
--     preserved for audit. resolved_role and resolved_official_id are the joined-in
--     canonical forms, produced by scripts/transcripts/speaker_resolver.py.

create extension if not exists vector;

create table if not exists transcript_chunks (
    id                    bigserial primary key,
    video_id              text        not null,
    meeting_date          date        not null,
    chunk_idx             int         not null,
    start_sec             real        not null,
    end_sec               real        not null,

    -- speaker attribution (all denormalized for query-side simplicity)
    source_label          text,                     -- raw CART label, e.g. 'A. Nazarian' or 'Council President'
    resolved_role         text        not null,     -- 'councilmember' | 'presiding' | 'counsel' | 'clerk' | 'interpreter' | 'reporter' | 'public-speaker' | 'unknown'
    resolved_official_id  text,                     -- FK-like reference to data/officials.json ids (nullable — see roster.json)
    resolved_name         text,                     -- 'Adrin Nazarian' | 'Council President' etc. (denormalized display form)
    resolution_method     text        not null,     -- 'exact-role' | 'exact-councilmember' | 'fuzzy-from:<raw>' | 'unresolved'

    -- content
    text                  text        not null,
    token_count           int         not null,

    -- embedding (384-dim, E5-small-v2 with 'passage: ' prefix, L2-normalized)
    embedding             vector(384) not null,
    embedding_model       text        not null default 'intfloat/e5-small-v2',
    embedding_version     int         not null default 1,

    -- provenance
    ingested_at           timestamptz not null default now(),

    unique (video_id, chunk_idx, embedding_model)
);

-- Retrieval index: HNSW on cosine distance (matches E5's normalized dot-product usage).
create index if not exists transcript_chunks_embedding_idx
    on transcript_chunks
    using hnsw (embedding vector_cosine_ops);

-- Filter/browse indices
create index if not exists transcript_chunks_video_idx    on transcript_chunks (video_id, chunk_idx);
create index if not exists transcript_chunks_date_idx     on transcript_chunks (meeting_date desc);
create index if not exists transcript_chunks_official_idx on transcript_chunks (resolved_official_id) where resolved_official_id is not null;

-- RPC used by api/search-transcripts.js.
-- Applies default filter: current embedding model, optional date window and role filter.
create or replace function search_transcripts(
    query_embedding vector(384),
    match_count int default 10,
    from_date date default null,
    to_date date default null,
    role_filter text default null
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
    similarity real
)
language sql stable
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
        (1 - (c.embedding <=> query_embedding))::real as similarity
    from transcript_chunks c
    where c.embedding_model = 'intfloat/e5-small-v2'
      and (from_date is null or c.meeting_date >= from_date)
      and (to_date is null or c.meeting_date <= to_date)
      and (role_filter is null or c.resolved_role = role_filter)
    order by c.embedding <=> query_embedding
    limit match_count;
$$;

comment on table transcript_chunks is
    'Per-chunk transcript store for LA City Council meetings. Additive to data/officials.json — no FK enforced because roster.json is the authoritative speaker table.';
