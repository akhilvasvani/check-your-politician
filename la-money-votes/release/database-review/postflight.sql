-- REVIEW ONLY. Target Supabase pwbothxnfjnxkhrcxyvd. Separate approval required.
BEGIN READ ONLY;
SET LOCAL statement_timeout='10s';

SELECT jsonb_build_object(
 'read_only',current_setting('transaction_read_only'),
 'counts',(SELECT jsonb_build_object('chunks',count(*),'parent_turns',count(*) FILTER(WHERE sub_chunk_idx=0),'recordings',count(DISTINCT video_id)) FROM public.transcript_chunks),
 'roles',(SELECT jsonb_agg(jsonb_build_object('role',r.rolname,'select',has_table_privilege(r.oid,'public.transcript_chunks','SELECT'),
   'any_write',has_table_privilege(r.oid,'public.transcript_chunks','INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'),
   'maintain',CASE WHEN current_setting('server_version_num')::int>=170000 THEN has_table_privilege(r.oid,'public.transcript_chunks','MAINTAIN') ELSE false END,
   'any_sequence',has_sequence_privilege(r.oid,'public.transcript_chunks_id_seq','USAGE,SELECT,UPDATE')) ORDER BY r.rolname)
   FROM pg_roles r WHERE r.rolname IN ('anon','authenticated','service_role')),
 'rpcs',(SELECT jsonb_agg(jsonb_build_object('name',p.proname,'signature',pg_get_function_identity_arguments(p.oid),
   'arguments',pg_get_function_arguments(p.oid),'result',pg_get_function_result(p.oid),
   'owner',pg_get_userbyid(p.proowner),'security_definer',p.prosecdef,'volatility',p.provolatile,'settings',p.proconfig,'body_md5',md5(p.prosrc),
   'acl',(SELECT jsonb_agg(jsonb_build_object('grantee',CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,'privilege',a.privilege_type,'grantable',a.is_grantable)) FROM aclexplode(p.proacl) a)) ORDER BY p.proname)
   FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname IN ('replace_transcript_chunks','search_transcripts','search_public_comment','get_transcript_coverage'))
) AS postflight;
ROLLBACK;
