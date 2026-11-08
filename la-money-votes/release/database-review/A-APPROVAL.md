# Change A — exact approval packet

**APPROVED AND COMMITTED November 8, 2026. Target Supabase
`pwbothxnfjnxkhrcxyvd`, la-politician, us-west-2, database/executor postgres.
All reviewed read-only postflight checks passed. Do not execute A again.**
See [the result](A-RESULT.md) and [execution receipt](A-execution-2026-11-08.json).
The reviewed contract and SQL below are retained unchanged; this approval covered A only.
Neither B nor recovery, ingestion, invocation or remote publication is included.

This is the unchanged prepared A from eb06c4e. The November 7 read-only refresh
exactly matches the prior inventory; 5,003 chunks / 3,341 parents / nine recordings.
[Prior state](prior-state.json), [fresh evidence](review-refresh-2026-11-07.json),
[scope and hash](A-approval.json).

| Object / principal | Effective before | Expected after A |
| --- | --- | --- |
| public.transcript_chunks / anon, authenticated | SELECT INSERT UPDATE DELETE TRUNCATE REFERENCES TRIGGER MAINTAIN | SELECT only |
| public.transcript_chunks_id_seq / anon, authenticated | SELECT USAGE UPDATE | None |
| Both objects / PUBLIC | None | None |
| Both objects / postgres, service_role | Full existing privileges, postgres owns both | Unchanged |

No parent role memberships for anon/authenticated/service_role and no column
ACLs add access. Browser roles lack superuser/BYPASSRLS. PUBLIC and membership
paths are checked, not just direct grants. Existing inherited administrative
capabilities are preserved: postgres inherits service_role; authenticator and
supabase_realtime_admin can SET ROLE service_role but do not inherit it. Those
platform roles are not browser roles, and no membership changes are proposed.

SELECT-only RLS and EXECUTE on search_transcripts, search_public_comment and
get_transcript_coverage remain unchanged. Their STABLE/INVOKER bodies match the
reviewed hashes. Read RPCs require table SELECT, not ID-sequence privileges.
Service ingestion privileges are retained; no ingestion is authorized.

Defaults for postgres/supabase_admin can grant broad browser access to newly
created public objects. They do not regrant an existing object automatically,
but recreation can reintroduce exposure. No default or schema-wide change is
proposed; future creation must harden the exact objects in its transaction.

A explicitly holds SHARE on the transcript table while checking invariance:
ordinary SELECT is compatible; writers and stronger maintenance/DDL locks can
wait. Lock timeout 2s, individual statement timeout 15s; these do not guarantee a
total operation duration. No table rewrite. Stop/rollback on owner, role,
policy/RLS, column-ACL, exact prior ACL, corpus-count or read-function drift.
The two target counts checks occur under the lock. See full dependencies and
lock test limits in [README.md](README.md).

After commit, run the unchanged [postflight.sql](postflight.sql) and the two
independent [read-role-postflight.sql](read-role-postflight.sql) transactions.
They are READ ONLY with 10s statement bounds, invoke no application functions,
verify both browser SELECTs and expected counts 5003/3341/9, and inspect effective
privileges/read-function metadata. Read-only refresh before execution is required.
No live TRUNCATE/write-denial probe, even under rollback.

Existing tests are reused: 45/45 PG 16.14 and 45/45 PG 17.6/vector0.8.2; all recorded
SQL/test input hashes still match. Relevant cases execute reads before/after A,
deny browser DML/TRUNCATE/sequence calls, reject PUBLIC/membership/count drift,
preserve unrelated objects/defaults, restore exact old ACL, and verify concurrent
reads/write blocking and read-only postflight. These ran only on disposable DBs.
No suite was rerun for this documentation/annotation change.

## Full forward SQL

SHA-256: `245a2122c42d14e315895ef9b0de6d079030f42beb6ece04017d42ee811cb415`

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
```

## Full recovery SQL — separate approval

**Warning: this restores unsafe broad browser grants, including TRUNCATE and sequence mutation. Recovery is not automatic and reopens the identified exposure.**

SHA-256: `a401c88891057102cad47aad6152a45c0d9562a47784abfa872ddd8e3e228227`

```sql
-- REVIEW ONLY. Target Supabase pwbothxnfjnxkhrcxyvd. Separate approval required.
-- Restores the reviewed prior broad browser ACL; increases privilege. Approval required.
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

GRANT ALL PRIVILEGES ON TABLE public.transcript_chunks TO anon, authenticated;
GRANT ALL PRIVILEGES ON SEQUENCE public.transcript_chunks_id_seq TO anon, authenticated;

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
