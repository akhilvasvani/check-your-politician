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
