# Change B — exact approval packet

**November 8 status: installation authorized, but NOT INSTALLED.** The first
confirmation was cancelled and the tool reported nothing ran. A separately
authorized fresh confirmation expired. Reviewed read-only reconciliation found
the replacement absent and A/read-function/count state unchanged. See receipts
[1](B-execution-2026-11-08.json) and [2](B-submission-2-2026-11-08.json).
Stop: no automatic retry; another submission needs a new explicit instruction.
The unchanged reviewed target is Supabase `pwbothxnfjnxkhrcxyvd`, la-politician,
us-west-2, database/executor postgres. Invocation, ingestion and replacement
remain excluded. The original SQL contract below is preserved.

This is the unchanged prepared B from eb06c4e. Recommend **A first, verify A,
then separately approve B**. There is no SQL dependency requiring B first; B can
install independently, but cannot repair A's broad grants by itself.
[Scope/hash](B-approval.json), [contract](contract.json), [fresh evidence](review-refresh-2026-11-07.json).

Full callable contract:
`public.replace_transcript_chunks(p_video_id text, p_embedding_model text, p_rows jsonb)`
returns `TABLE(intended_count bigint, upserted_count bigint, deleted_count bigint)`.
Language plpgsql; VOLATILE; owner postgres; SECURITY INVOKER;
configured search_path=`pg_catalog, pg_temp`. Main table/vector references are
public-qualified; staging is pg_temp-qualified. The tested transaction/cohort
validation, advisory lock, upsert/delete and exact-result contract is preserved.

One transaction creates (not overwrites) the function, sets owner, removes
PUBLIC/anon/authenticated EXECUTE and grants service_role EXECUTE before commit.
Exact ordinary ACL is postgres/service_role EXECUTE with no grant option.
Anonymous/authenticated effective invocation is false; no parent memberships
supply an alternate path. Owner/superuser powers remain. Existing authenticator
and supabase_realtime_admin may SET ROLE service_role under platform controls;
postgres inherits service_role. These are documented existing administrative
paths, not new browser execution grants or a claim that only two login sessions
can ever execute. The INVOKER service role's existing table, sequence, TEMP,
schema/type/function privileges and BYPASSRLS enable later authorized use.

The fresh all-schema proname query found **no replacement overloads**, and no
row triggers exist on transcript_chunks. Catalog/repository dependency review
is in README; dynamic external callers cannot be disproven by pg_depend alone.
The owner default gives PUBLIC function execution and public-schema defaults
can add browser grants; B explicitly removes those in the creation transaction.
No schema-wide default or other-function grant is changed.

**Existing platform DDL effects:** extensions.pgrst_ddl_watch is enabled and
requests `NOTIFY pgrst, 'reload schema'` for CREATE/ALTER FUNCTION. Its existing
sql_drop counterpart can notify when recovery drops this non-temporary function.
These are automatic cache notifications, not replacement execution or corpus
writes. ensure_rls is limited to CREATE TABLE/CREATE TABLE AS/SELECT INTO,
so it does not apply to installation of this function. Extension-access/drop
triggers are restricted to CREATE/DROP EXTENSION; neither is in B. No row or
DDL trigger is changed. Supabase's platform watchers/PostgREST runtime were not
reproduced by the vanilla disposable45-case suite; current trigger definitions
were inspected read-only. Cache reload completion/HTTP exposure remain runtime
postflight considerations, never permission to invoke replacement as a probe.

B and recovery hold SHARE to pin corpus counts, permit ordinary SELECT, and can
block writers/stronger DDL. Lock timeout 2s; individual statement timeout 15s.
CREATE/ALTER/DROP function also takes relevant catalog locks and can conflict
with concurrent object DDL. The signature must be absent on installation.
Recovery refuses changed input/output contract, body, language, owner, security,
search_path or execution ACL and drops the exact signature without CASCADE.
Existing dependencies can block removal; do not override them.

After an approved installation, run [postflight.sql](postflight.sql) and both
[read-role-postflight.sql](read-role-postflight.sql) READ ONLY transactions.
Expect counts 5003/3341/9, unchanged A/read-RPC state, full pinned B contract,
no PUBLIC/anon/authenticated EXECUTE and service execution privilege present.
Use catalog/has_function_privilege checks, never live replacement or destructive
probes, including rollback-wrapped calls. Stop on any drift or ambiguous result.

**Reuse 45/45 PG 16.14 and 45/45 PG 17.6/vector0.8.2.** All tested input hashes still
match. Each run consists of 18 existing contract cases, the same 18 run against B,
and 9 focused hardening/recovery cases. The existing cases cover atomic rollback,
invalid/duplicate/incorrect cohort payloads, dimensions, exact intended keys,
stale-row deletion, idempotence and service access. Focused cases verify browser
invocation denial, no install-time row or table-ACL changes, overwrite refusal,
recovery to absence, full-signature/search_path drift rejection, public staging
namesake preservation and required reads. No full app rerun or live invocation
is claimed. New catalog evidence documents platform side effects separately.

## Full forward SQL

SHA-256: `818c0d9c7135644e0a6796a6f7358aa55f9526a28293dc72553481b0802cf330`

```sql
-- REVIEW ONLY. Target Supabase pwbothxnfjnxkhrcxyvd. Separate approval required.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '15s';
LOCK TABLE public.transcript_chunks IN SHARE MODE;

DO $check$
DECLARE n bigint; parents bigint; videos bigint;
BEGIN
  IF current_user <> 'postgres' THEN RAISE EXCEPTION 'Expected reviewed executor postgres'; END IF;
  IF (SELECT relowner <> 'postgres'::regrole OR NOT relrowsecurity FROM pg_class WHERE oid='public.transcript_chunks'::regclass) THEN
    RAISE EXCEPTION 'Owner/RLS drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member IN ('anon'::regrole,'authenticated'::regrole,'service_role'::regrole)) THEN
    RAISE EXCEPTION 'Role membership drift; review inherited privileges';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated') AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Browser role bypass drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='public.transcript_chunks'::regclass AND attacl IS NOT NULL) THEN
    RAISE EXCEPTION 'Column ACL drift; review before changing table privileges';
  END IF;
  IF (SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks') <> 1
     OR NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks'
       AND policyname='transcript_chunks_read_anon' AND cmd='SELECT' AND qual='true'
       AND roles @> ARRAY['anon','authenticated']::name[] AND cardinality(roles)=2 AND permissive='PERMISSIVE') THEN
    RAISE EXCEPTION 'Read policy drift';
  END IF;
  SELECT count(*), count(*) FILTER(WHERE sub_chunk_idx=0), count(DISTINCT video_id)
    INTO n,parents,videos FROM public.transcript_chunks;
  IF (n,parents,videos) IS DISTINCT FROM (5003::bigint,3341::bigint,9::bigint) THEN
    RAISE EXCEPTION 'Corpus counts drift; refresh approval';
  END IF;
  IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace
      WHERE ns.nspname='public' AND NOT p.prosecdef AND p.provolatile='s' AND
       (p.proname,md5(p.prosrc)) IN (
        ('search_transcripts','67e13f5e574b0ef81e124b42256b775d'),
        ('search_public_comment','33e4ba028630765299b3359a19b9a396'),
        ('get_transcript_coverage','22161cc4439ed49a91aae3b0146c2d7e'))) <> 3 THEN
    RAISE EXCEPTION 'Read RPC drift';
  END IF;
END $check$;

DO $absent$ BEGIN
  IF to_regprocedure('public.replace_transcript_chunks(text,text,jsonb)') IS NOT NULL THEN RAISE EXCEPTION 'Replacement already exists; review instead of overwriting'; END IF;
END $absent$;
create function public.replace_transcript_chunks(
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
set search_path = pg_catalog, pg_temp
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
    -- fails here, before anything in public.transcript_chunks is touched.
    -- Dropped explicitly as well as ON COMMIT so that replacing several videos
    -- inside one transaction does not collide on the staging table.
    drop table if exists pg_temp._staged_chunks;
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
        (e->>'embedding')::public.vector                             as embedding,
        (e->>'embedding_model')::text                         as embedding_model,
        coalesce((e->>'embedding_version')::int, 1)           as embedding_version
    from jsonb_array_elements(p_rows) as e;

    select count(*), count(distinct chunk_idx) into v_intended, v_distinct
    from pg_temp._staged_chunks;

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
    from pg_temp._staged_chunks where video_id is distinct from p_video_id;
    if v_bad is not null then
        raise exception
            'replace_transcript_chunks: payload contains foreign video_id(s): %', v_bad;
    end if;
    select string_agg(distinct embedding_model, ',') into v_bad
    from pg_temp._staged_chunks where embedding_model is distinct from p_embedding_model;
    if v_bad is not null then
        raise exception
            'replace_transcript_chunks: payload contains foreign embedding_model(s): %', v_bad;
    end if;

    -- Required metadata must be present on every staged row.
    select string_agg(chunk_idx::text, ',' order by chunk_idx) into v_bad
    from pg_temp._staged_chunks
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
    from pg_temp._staged_chunks where public.vector_dims(embedding) <> 1024;
    if v_bad is not null then
        raise exception
            'replace_transcript_chunks: non-1024-dim embedding at chunk_idx: %', v_bad;
    end if;

    -- (4) Upsert every intended row.
    insert into public.transcript_chunks (
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
    from pg_temp._staged_chunks
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
    from public.transcript_chunks c
    join pg_temp._staged_chunks s
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
    delete from public.transcript_chunks c
    where c.video_id = p_video_id
      and c.embedding_model = p_embedding_model
      and not exists (
          select 1 from pg_temp._staged_chunks s where s.chunk_idx = c.chunk_idx
      );
    get diagnostics v_deleted = row_count;

    return query select v_intended, v_upserted, v_deleted;
end;
$$;


ALTER FUNCTION public.replace_transcript_chunks(text,text,jsonb) OWNER TO postgres;
REVOKE ALL PRIVILEGES ON FUNCTION public.replace_transcript_chunks(text,text,jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.replace_transcript_chunks(text,text,jsonb) TO service_role;

DO $rpc$
DECLARE f oid := to_regprocedure('public.replace_transcript_chunks(text,text,jsonb)');
BEGIN
  IF f IS NULL OR NOT EXISTS (SELECT 1 FROM pg_proc WHERE oid=f AND proowner='postgres'::regrole
      AND NOT prosecdef AND provolatile='v' AND md5(prosrc)='dc3d667d0a6a03a86c823da31eff205f'
      AND prokind='f' AND prolang=(SELECT oid FROM pg_language WHERE lanname='plpgsql')
      AND pg_get_function_arguments(oid)='p_video_id text, p_embedding_model text, p_rows jsonb'
      AND pg_get_function_result(oid)='TABLE(intended_count bigint, upserted_count bigint, deleted_count bigint)'
      AND proconfig=ARRAY['search_path=pg_catalog, pg_temp']) THEN RAISE EXCEPTION 'Replacement contract/config drift'; END IF;
  IF has_function_privilege('anon',f,'EXECUTE') OR has_function_privilege('authenticated',f,'EXECUTE')
     OR NOT has_function_privilege('service_role',f,'EXECUTE') THEN RAISE EXCEPTION 'Replacement effective grants incorrect'; END IF;
  IF EXISTS (SELECT 1 FROM pg_proc p, LATERAL aclexplode(p.proacl) a WHERE p.oid=f
       AND (a.grantee NOT IN ('postgres'::regrole,'service_role'::regrole) OR a.is_grantable)) THEN
    RAISE EXCEPTION 'Unexpected replacement ACL including PUBLIC';
  END IF;
END $rpc$;

DO $check$
DECLARE n bigint; parents bigint; videos bigint;
BEGIN
  IF current_user <> 'postgres' THEN RAISE EXCEPTION 'Expected reviewed executor postgres'; END IF;
  IF (SELECT relowner <> 'postgres'::regrole OR NOT relrowsecurity FROM pg_class WHERE oid='public.transcript_chunks'::regclass) THEN
    RAISE EXCEPTION 'Owner/RLS drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member IN ('anon'::regrole,'authenticated'::regrole,'service_role'::regrole)) THEN
    RAISE EXCEPTION 'Role membership drift; review inherited privileges';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated') AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Browser role bypass drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='public.transcript_chunks'::regclass AND attacl IS NOT NULL) THEN
    RAISE EXCEPTION 'Column ACL drift; review before changing table privileges';
  END IF;
  IF (SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks') <> 1
     OR NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks'
       AND policyname='transcript_chunks_read_anon' AND cmd='SELECT' AND qual='true'
       AND roles @> ARRAY['anon','authenticated']::name[] AND cardinality(roles)=2 AND permissive='PERMISSIVE') THEN
    RAISE EXCEPTION 'Read policy drift';
  END IF;
  SELECT count(*), count(*) FILTER(WHERE sub_chunk_idx=0), count(DISTINCT video_id)
    INTO n,parents,videos FROM public.transcript_chunks;
  IF (n,parents,videos) IS DISTINCT FROM (5003::bigint,3341::bigint,9::bigint) THEN
    RAISE EXCEPTION 'Corpus counts drift; refresh approval';
  END IF;
  IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace
      WHERE ns.nspname='public' AND NOT p.prosecdef AND p.provolatile='s' AND
       (p.proname,md5(p.prosrc)) IN (
        ('search_transcripts','67e13f5e574b0ef81e124b42256b775d'),
        ('search_public_comment','33e4ba028630765299b3359a19b9a396'),
        ('get_transcript_coverage','22161cc4439ed49a91aae3b0146c2d7e'))) <> 3 THEN
    RAISE EXCEPTION 'Read RPC drift';
  END IF;
END $check$;
COMMIT;
```

## Full recovery SQL — separate approval

This restores the prior function absence. No corpus rows are changed, but future ingestion callers would lose the RPC. No CASCADE or automatic retry is authorized.

SHA-256: `4ca0c947f4637fd5aa9a9310ceffaac8e25e9d57cc090bf3a74f18bfc206d263`

```sql
-- REVIEW ONLY. Target Supabase pwbothxnfjnxkhrcxyvd. Separate approval required.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '15s';
LOCK TABLE public.transcript_chunks IN SHARE MODE;

DO $check$
DECLARE n bigint; parents bigint; videos bigint;
BEGIN
  IF current_user <> 'postgres' THEN RAISE EXCEPTION 'Expected reviewed executor postgres'; END IF;
  IF (SELECT relowner <> 'postgres'::regrole OR NOT relrowsecurity FROM pg_class WHERE oid='public.transcript_chunks'::regclass) THEN
    RAISE EXCEPTION 'Owner/RLS drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member IN ('anon'::regrole,'authenticated'::regrole,'service_role'::regrole)) THEN
    RAISE EXCEPTION 'Role membership drift; review inherited privileges';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated') AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Browser role bypass drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='public.transcript_chunks'::regclass AND attacl IS NOT NULL) THEN
    RAISE EXCEPTION 'Column ACL drift; review before changing table privileges';
  END IF;
  IF (SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks') <> 1
     OR NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks'
       AND policyname='transcript_chunks_read_anon' AND cmd='SELECT' AND qual='true'
       AND roles @> ARRAY['anon','authenticated']::name[] AND cardinality(roles)=2 AND permissive='PERMISSIVE') THEN
    RAISE EXCEPTION 'Read policy drift';
  END IF;
  SELECT count(*), count(*) FILTER(WHERE sub_chunk_idx=0), count(DISTINCT video_id)
    INTO n,parents,videos FROM public.transcript_chunks;
  IF (n,parents,videos) IS DISTINCT FROM (5003::bigint,3341::bigint,9::bigint) THEN
    RAISE EXCEPTION 'Corpus counts drift; refresh approval';
  END IF;
  IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace
      WHERE ns.nspname='public' AND NOT p.prosecdef AND p.provolatile='s' AND
       (p.proname,md5(p.prosrc)) IN (
        ('search_transcripts','67e13f5e574b0ef81e124b42256b775d'),
        ('search_public_comment','33e4ba028630765299b3359a19b9a396'),
        ('get_transcript_coverage','22161cc4439ed49a91aae3b0146c2d7e'))) <> 3 THEN
    RAISE EXCEPTION 'Read RPC drift';
  END IF;
END $check$;

DO $rpc$
DECLARE f oid := to_regprocedure('public.replace_transcript_chunks(text,text,jsonb)');
BEGIN
  IF f IS NULL OR NOT EXISTS (SELECT 1 FROM pg_proc WHERE oid=f AND proowner='postgres'::regrole
      AND NOT prosecdef AND provolatile='v' AND md5(prosrc)='dc3d667d0a6a03a86c823da31eff205f'
      AND prokind='f' AND prolang=(SELECT oid FROM pg_language WHERE lanname='plpgsql')
      AND pg_get_function_arguments(oid)='p_video_id text, p_embedding_model text, p_rows jsonb'
      AND pg_get_function_result(oid)='TABLE(intended_count bigint, upserted_count bigint, deleted_count bigint)'
      AND proconfig=ARRAY['search_path=pg_catalog, pg_temp']) THEN RAISE EXCEPTION 'Replacement contract/config drift'; END IF;
  IF has_function_privilege('anon',f,'EXECUTE') OR has_function_privilege('authenticated',f,'EXECUTE')
     OR NOT has_function_privilege('service_role',f,'EXECUTE') THEN RAISE EXCEPTION 'Replacement effective grants incorrect'; END IF;
  IF EXISTS (SELECT 1 FROM pg_proc p, LATERAL aclexplode(p.proacl) a WHERE p.oid=f
       AND (a.grantee NOT IN ('postgres'::regrole,'service_role'::regrole) OR a.is_grantable)) THEN
    RAISE EXCEPTION 'Unexpected replacement ACL including PUBLIC';
  END IF;
END $rpc$;
DROP FUNCTION public.replace_transcript_chunks(text,text,jsonb);

DO $check$
DECLARE n bigint; parents bigint; videos bigint;
BEGIN
  IF current_user <> 'postgres' THEN RAISE EXCEPTION 'Expected reviewed executor postgres'; END IF;
  IF (SELECT relowner <> 'postgres'::regrole OR NOT relrowsecurity FROM pg_class WHERE oid='public.transcript_chunks'::regclass) THEN
    RAISE EXCEPTION 'Owner/RLS drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member IN ('anon'::regrole,'authenticated'::regrole,'service_role'::regrole)) THEN
    RAISE EXCEPTION 'Role membership drift; review inherited privileges';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated') AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Browser role bypass drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='public.transcript_chunks'::regclass AND attacl IS NOT NULL) THEN
    RAISE EXCEPTION 'Column ACL drift; review before changing table privileges';
  END IF;
  IF (SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks') <> 1
     OR NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks'
       AND policyname='transcript_chunks_read_anon' AND cmd='SELECT' AND qual='true'
       AND roles @> ARRAY['anon','authenticated']::name[] AND cardinality(roles)=2 AND permissive='PERMISSIVE') THEN
    RAISE EXCEPTION 'Read policy drift';
  END IF;
  SELECT count(*), count(*) FILTER(WHERE sub_chunk_idx=0), count(DISTINCT video_id)
    INTO n,parents,videos FROM public.transcript_chunks;
  IF (n,parents,videos) IS DISTINCT FROM (5003::bigint,3341::bigint,9::bigint) THEN
    RAISE EXCEPTION 'Corpus counts drift; refresh approval';
  END IF;
  IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace
      WHERE ns.nspname='public' AND NOT p.prosecdef AND p.provolatile='s' AND
       (p.proname,md5(p.prosrc)) IN (
        ('search_transcripts','67e13f5e574b0ef81e124b42256b775d'),
        ('search_public_comment','33e4ba028630765299b3359a19b9a396'),
        ('get_transcript_coverage','22161cc4439ed49a91aae3b0146c2d7e'))) <> 3 THEN
    RAISE EXCEPTION 'Read RPC drift';
  END IF;
END $check$;
COMMIT;
```
