BEGIN READ ONLY; SET LOCAL statement_timeout='10s';
SELECT jsonb_build_object('read_only',current_setting('transaction_read_only'),'service_role',
 (SELECT jsonb_build_object('bypass_rls',rolbypassrls,
 'database_connect',has_database_privilege(oid,current_database(),'CONNECT'),
 'database_temp',has_database_privilege(oid,current_database(),'TEMP'),
 'public_usage',has_schema_privilege(oid,'public','USAGE'),
 'vector_usage',has_type_privilege(oid,'public.vector','USAGE'),
 'vector_dims_execute',has_function_privilege(oid,'public.vector_dims(public.vector)','EXECUTE'))
 FROM pg_roles WHERE rolname='service_role'),
 'counts',(SELECT jsonb_build_object('chunks',count(*),'parent_turns',count(*) FILTER(WHERE sub_chunk_idx=0),'recordings',count(DISTINCT video_id)) FROM public.transcript_chunks)) AS dependency_prerequisites;
ROLLBACK;
