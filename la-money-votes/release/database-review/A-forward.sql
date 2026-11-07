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

DO $acl$
DECLARE obj regclass; role_name text; expected text[]; actual text[];
BEGIN
  FOREACH obj IN ARRAY ARRAY['public.transcript_chunks'::regclass,'public.transcript_chunks_id_seq'::regclass] LOOP
    IF (SELECT relowner FROM pg_class WHERE oid=obj) <> 'postgres'::regrole THEN RAISE EXCEPTION 'Object owner drift'; END IF;
    IF EXISTS (SELECT 1 FROM pg_class c, LATERAL aclexplode(c.relacl) a WHERE c.oid=obj
       AND (a.grantee NOT IN ('postgres'::regrole,'anon'::regrole,'authenticated'::regrole,'service_role'::regrole)
            OR a.grantor <> 'postgres'::regrole OR a.is_grantable)) THEN
      RAISE EXCEPTION 'Unexpected PUBLIC/other ACL or grantor drift';
    END IF;
    FOREACH role_name IN ARRAY ARRAY['postgres','anon','authenticated','service_role'] LOOP
      IF obj='public.transcript_chunks'::regclass THEN
        expected := CASE WHEN current_setting('server_version_num')::int >= 170000
          THEN ARRAY['DELETE','INSERT','MAINTAIN','REFERENCES','SELECT','TRIGGER','TRUNCATE','UPDATE']
          ELSE ARRAY['DELETE','INSERT','REFERENCES','SELECT','TRIGGER','TRUNCATE','UPDATE'] END;
      ELSE expected := ARRAY['SELECT','UPDATE','USAGE']; END IF;
      SELECT array_agg(a.privilege_type ORDER BY a.privilege_type) INTO actual
        FROM pg_class c, LATERAL aclexplode(c.relacl) a WHERE c.oid=obj AND a.grantee=role_name::regrole;
      IF actual IS DISTINCT FROM expected THEN RAISE EXCEPTION 'Prior ACL drift for % on %',role_name,obj; END IF;
    END LOOP;
  END LOOP;
END $acl$;

REVOKE ALL PRIVILEGES ON TABLE public.transcript_chunks FROM PUBLIC, anon, authenticated;
GRANT SELECT ON TABLE public.transcript_chunks TO anon, authenticated;
REVOKE ALL PRIVILEGES ON SEQUENCE public.transcript_chunks_id_seq FROM PUBLIC, anon, authenticated;

DO $deny$
DECLARE role_name text; privilege text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
    IF NOT has_table_privilege(role_name,'public.transcript_chunks','SELECT') THEN RAISE EXCEPTION 'Required SELECT missing'; END IF;
    FOREACH privilege IN ARRAY ARRAY['INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'] LOOP
      IF has_table_privilege(role_name,'public.transcript_chunks',privilege) THEN RAISE EXCEPTION 'Unexpected browser % privilege',privilege; END IF;
    END LOOP;
    IF current_setting('server_version_num')::int >= 170000 THEN
      IF has_table_privilege(role_name,'public.transcript_chunks','MAINTAIN') THEN RAISE EXCEPTION 'Unexpected browser MAINTAIN privilege'; END IF;
    END IF;
    IF has_sequence_privilege(role_name,'public.transcript_chunks_id_seq','USAGE,SELECT,UPDATE') THEN RAISE EXCEPTION 'Browser sequence privilege remains'; END IF;
    IF NOT has_function_privilege(role_name,'public.get_transcript_coverage(text,text)','EXECUTE') THEN RAISE EXCEPTION 'Required read RPC access missing'; END IF;
  END LOOP;
END $deny$;

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
