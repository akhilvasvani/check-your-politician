"""A/B review-script tests. Writes/destructive probes run ONLY in a disposable DB.

Run with run_pg_tests.sh scripts.transcripts.tests.test_database_review -v.
No shared database or provider calls are made by this module.
"""
import json
import unittest
from pathlib import Path

from . import test_replace_transcript_chunks as baseline

REVIEW = baseline.REPO / "release/database-review"
DATA = baseline.REPO / "data/transcripts"
VECTOR = "[" + ",".join(["0.1"] * 1024) + "]"


def script(conn, name):
    with conn.cursor() as cur:
        try:
            cur.execute((REVIEW / name).read_text())
        except Exception:
            cur.execute("ROLLBACK")
            raise


def scalar(conn, sql, args=()):
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchone()[0]


def counts(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT count(*),count(*) FILTER(WHERE sub_chunk_idx=0),count(DISTINCT video_id) FROM public.transcript_chunks")
        return cur.fetchone()


def acl(conn):
    with conn.cursor() as cur:
        cur.execute("""SELECT c.relname,pg_get_userbyid(a.grantor),a.grantee,a.privilege_type,a.is_grantable
        FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a
        WHERE c.oid IN ('public.transcript_chunks'::regclass,'public.transcript_chunks_id_seq'::regclass)
        ORDER BY c.relname,a.grantee,a.privilege_type""")
        return cur.fetchall()


def fixture(conn):
    """Reproduce observed legacy defaults/grants and counts, with synthetic text."""
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        for role in ("anon", "authenticated", "service_role"):
            cur.execute("DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname=%s) THEN EXECUTE format('CREATE ROLE %%I',%s); END IF; END $$", (role,role))
        cur.execute("ALTER ROLE service_role BYPASSRLS")
        cur.execute("""ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon,authenticated,service_role;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon,authenticated,service_role;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO anon,authenticated,service_role;""")
        cur.execute("SELECT oid::regprocedure::text FROM pg_proc WHERE pronamespace='public'::regnamespace AND proname IN ('replace_transcript_chunks','search_transcripts','search_public_comment','get_transcript_coverage')")
        for (signature,) in cur.fetchall():
            cur.execute("DROP FUNCTION " + signature)
        cur.execute("DROP TABLE IF EXISTS public.transcript_chunks CASCADE; DROP TABLE IF EXISTS public.review_unrelated; DROP TABLE IF EXISTS public._staged_chunks")
        cur.execute(baseline.SCHEMA_SQL.read_text())
        cur.execute((DATA / 'migration_m2_subchunk_in_rpc.sql').read_text())
        cur.execute((DATA / 'migration_m2_public_comment_search.sql').read_text())
        cur.execute("CREATE TABLE public.review_unrelated (marker text)")
        cur.execute("""INSERT INTO public.transcript_chunks
        (video_id,meeting_date,chunk_idx,start_sec,end_sec,resolved_role,resolved_official_id,resolution_method,text,token_count,embedding,sub_chunk_idx,sub_chunk_of)
        SELECT 'fixture-'||(g%%9),'2026-08-14'::date,g,g,g+1,
        CASE WHEN g%%10=0 THEN 'public-speaker' ELSE 'councilmember' END,
        CASE WHEN g%%10=0 THEN NULL ELSE 'cd1-official' END,'fixture','synthetic local fixture',3,%s::public.vector,
        CASE WHEN g<=3341 THEN 0 ELSE 1 END,CASE WHEN g<=3341 THEN 1 ELSE 2 END
        FROM generate_series(1,5003) g""", (VECTOR,))


def browser_reads(conn):
    results = []
    with conn.cursor() as cur:
        for role in ('anon','authenticated'):
            cur.execute('SET ROLE ' + role)
            try:
                cur.execute("SELECT count(*) FROM public.transcript_chunks")
                results.append(cur.fetchone()[0])
                cur.execute("SELECT speaking_turns FROM public.get_transcript_coverage('cd1-official')")
                results.append(cur.fetchone()[0])
                cur.execute("SELECT count(*) FROM public.search_transcripts(%s::public.vector,'cd1-official',NULL,NULL,'pplx-embed-v1-0.6b',8,0)",(VECTOR,))
                results.append(cur.fetchone()[0])
                cur.execute("SELECT count(*) FROM public.search_public_comment(%s::public.vector,NULL,NULL,'pplx-embed-v1-0.6b',8,0)",(VECTOR,))
                results.append(cur.fetchone()[0])
            finally:
                cur.execute('RESET ROLE')
    assert all(x > 0 for x in results), results
    return results


@unittest.skipUnless(baseline.DSN and baseline.psycopg2, 'disposable DSN required')
class ReviewChanges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = baseline.psycopg2.connect(baseline.DSN)
        cls.conn.autocommit = True

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        fixture(self.conn)

    def test_a_preserves_reads_counts_defaults_and_unrelated_objects_recovers_exact_acl(self):
        before, reads = acl(self.conn), browser_reads(self.conn)
        defaults = scalar(self.conn,"SELECT md5(string_agg(defaclacl::text,'|' ORDER BY oid)) FROM pg_default_acl")
        script(self.conn,'A-forward.sql')
        self.assertEqual(counts(self.conn),(5003,3341,9))
        self.assertEqual(browser_reads(self.conn),reads)
        self.assertTrue(scalar(self.conn,"SELECT has_table_privilege('anon','public.review_unrelated','INSERT')"))
        self.assertEqual(defaults,scalar(self.conn,"SELECT md5(string_agg(defaclacl::text,'|' ORDER BY oid)) FROM pg_default_acl"))
        script(self.conn,'A-recovery.sql')
        self.assertEqual(acl(self.conn),before)
        self.assertEqual(counts(self.conn),(5003,3341,9))

    def test_a_denies_browser_writes_truncate_and_sequence_calls(self):
        script(self.conn,'A-forward.sql')
        with self.conn.cursor() as cur:
            for role in ('anon','authenticated'):
                cur.execute('SET ROLE '+role)
                try:
                    for sql in ("TRUNCATE public.transcript_chunks", "DELETE FROM public.transcript_chunks", "UPDATE public.transcript_chunks SET text='forbidden'", "INSERT INTO public.transcript_chunks SELECT * FROM public.transcript_chunks LIMIT 1", "SELECT nextval('public.transcript_chunks_id_seq')", "SELECT setval('public.transcript_chunks_id_seq',1)"):
                        with self.subTest(role=role,statement=sql), self.assertRaises(baseline.psycopg2.errors.InsufficientPrivilege):
                            cur.execute(sql)
                finally:
                    cur.execute('RESET ROLE')
        self.assertEqual(counts(self.conn),(5003,3341,9))

    def test_a_refuses_public_and_inherited_privilege_drift(self):
        with self.conn.cursor() as cur:
            cur.execute('GRANT UPDATE ON public.transcript_chunks TO PUBLIC')
        with self.assertRaisesRegex(Exception,'Unexpected PUBLIC'):
            script(self.conn,'A-forward.sql')
        with self.conn.cursor() as cur:
            cur.execute('REVOKE UPDATE ON public.transcript_chunks FROM PUBLIC')
            cur.execute('GRANT service_role TO anon')
        try:
            with self.assertRaisesRegex(Exception,'Role membership drift'):
                script(self.conn,'A-forward.sql')
        finally:
            with self.conn.cursor() as cur: cur.execute('REVOKE service_role FROM anon')
        self.assertEqual(counts(self.conn),(5003,3341,9))

    def test_precondition_count_drift_rolls_back_without_acl_changes(self):
        with self.conn.cursor() as cur: cur.execute('DELETE FROM public.transcript_chunks WHERE chunk_idx=5003')
        before=acl(self.conn)
        with self.assertRaisesRegex(Exception,'Corpus counts drift'):
            script(self.conn,'A-forward.sql')
        self.assertEqual(acl(self.conn),before)

    def test_b_installs_without_rows_changes_denies_browser_execution_and_recovers_absence(self):
        before=acl(self.conn)
        script(self.conn,'B-forward.sql')
        self.assertEqual(counts(self.conn),(5003,3341,9))
        self.assertEqual(acl(self.conn),before)
        browser_reads(self.conn)
        with self.conn.cursor() as cur:
            for role in ('anon','authenticated'):
                cur.execute('SET ROLE '+role)
                try:
                    with self.assertRaises(baseline.psycopg2.errors.InsufficientPrivilege):
                        cur.execute("SELECT * FROM public.replace_transcript_chunks('fixture-1','pplx-embed-v1-0.6b','[]'::jsonb)")
                finally: cur.execute('RESET ROLE')
        with self.assertRaisesRegex(Exception,'already exists'):
            script(self.conn,'B-forward.sql')
        script(self.conn,'B-recovery.sql')
        self.assertIsNone(scalar(self.conn,"SELECT to_regprocedure('public.replace_transcript_chunks(text,text,jsonb)')"))
        self.assertEqual(counts(self.conn),(5003,3341,9))

    def test_b_qualified_staging_preserves_public_namesake(self):
        script(self.conn,'A-forward.sql'); script(self.conn,'B-forward.sql')
        with self.conn.cursor() as cur:
            cur.execute("CREATE TABLE public._staged_chunks(marker text); INSERT INTO public._staged_chunks VALUES('keep')")
            cur.execute('SET ROLE service_role')
            try:
                cur.execute("SELECT * FROM public.replace_transcript_chunks(%s,%s,%s::jsonb)",('new-local',baseline.MODEL,json.dumps([baseline._row(0,video_id='new-local')])))
                self.assertEqual(cur.fetchone(),(1,1,0))
            finally: cur.execute('RESET ROLE')
        self.assertEqual(scalar(self.conn,'SELECT marker FROM public._staged_chunks'),'keep')

    def test_b_recovery_refuses_modified_function(self):
        script(self.conn,'B-forward.sql')
        with self.conn.cursor() as cur: cur.execute('ALTER FUNCTION public.replace_transcript_chunks(text,text,jsonb) SET search_path=public')
        with self.assertRaisesRegex(Exception,'contract/config drift'):
            script(self.conn,'B-recovery.sql')
        self.assertIsNotNone(scalar(self.conn,"SELECT to_regprocedure('public.replace_transcript_chunks(text,text,jsonb)')"))

    def test_b_recovery_refuses_changed_return_contract_with_same_body(self):
        script(self.conn,'B-forward.sql')
        before = scalar(self.conn,"SELECT md5(prosrc) FROM pg_proc WHERE oid='public.replace_transcript_chunks(text,text,jsonb)'::regprocedure")
        definition = scalar(self.conn,"SELECT pg_get_functiondef('public.replace_transcript_chunks(text,text,jsonb)'::regprocedure)")
        self.assertIn('TABLE(intended_count bigint,',definition)
        with self.conn.cursor() as cur:
            cur.execute('DROP FUNCTION public.replace_transcript_chunks(text,text,jsonb)')
            cur.execute(definition.replace('TABLE(intended_count bigint,','TABLE(changed_count bigint,'))
            cur.execute('REVOKE ALL ON FUNCTION public.replace_transcript_chunks(text,text,jsonb) FROM PUBLIC,anon,authenticated')
            cur.execute('GRANT EXECUTE ON FUNCTION public.replace_transcript_chunks(text,text,jsonb) TO service_role')
        self.assertEqual(before,scalar(self.conn,"SELECT md5(prosrc) FROM pg_proc WHERE oid='public.replace_transcript_chunks(text,text,jsonb)'::regprocedure"))
        with self.assertRaisesRegex(Exception,'contract/config drift'):
            script(self.conn,'B-recovery.sql')
        self.assertIn('changed_count',scalar(self.conn,"SELECT pg_get_function_result('public.replace_transcript_chunks(text,text,jsonb)'::regprocedure)"))

    def test_review_transactions_preserve_concurrent_reads_and_postflight_is_read_only(self):
        peer = baseline.psycopg2.connect(baseline.DSN)
        peer.autocommit = True
        try:
            for name in ('A-forward.sql','B-forward.sql'):
                sql = (REVIEW / name).read_text().rstrip()
                self.assertTrue(sql.endswith('COMMIT;'))
                with self.conn.cursor() as holder, peer.cursor() as reader:
                    try:
                        holder.execute(sql[:-len('COMMIT;')])
                        reader.execute("SET statement_timeout='500ms'; SET lock_timeout='200ms'")
                        for role in ('anon','authenticated'):
                            reader.execute('SET ROLE '+role)
                            reader.execute('SELECT count(*) FROM public.transcript_chunks')
                            self.assertEqual(reader.fetchone()[0],5003)
                            reader.execute('RESET ROLE')
                        with self.assertRaises(baseline.psycopg2.errors.LockNotAvailable):
                            reader.execute('UPDATE public.transcript_chunks SET text=text WHERE false')
                    finally:
                        holder.execute('ROLLBACK')
            script(self.conn,'A-forward.sql')
            script(self.conn,'B-forward.sql')
            sql = (REVIEW / 'postflight.sql').read_text().rstrip()
            self.assertTrue(sql.endswith('ROLLBACK;'))
            with self.conn.cursor() as cur:
                try:
                    cur.execute(sql[:-len('ROLLBACK;')])
                    report = cur.fetchone()[0]
                    self.assertEqual(report['read_only'],'on')
                    self.assertEqual(report['counts'],{'chunks':5003,'parent_turns':3341,'recordings':9})
                    for role in report['roles']:
                        if role['role'] in ('anon','authenticated'):
                            self.assertTrue(role['select'])
                            self.assertFalse(role['any_write'] or role['maintain'] or role['any_sequence'])
                    replacement = next(f for f in report['rpcs'] if f['name']=='replace_transcript_chunks')
                    self.assertEqual(replacement['result'],'TABLE(intended_count bigint, upserted_count bigint, deleted_count bigint)')
                finally:
                    cur.execute('ROLLBACK')
        finally:
            peer.close()


@unittest.skipUnless(baseline.DSN and baseline.psycopg2, 'disposable DSN required')
class ProposedReplacementContract(baseline.ReplaceTranscriptChunksTest):
    """Run the existing 18 replacement behaviors against the proposed B body."""
    @classmethod
    def setUpClass(cls):
        cls.conn = baseline.psycopg2.connect(baseline.DSN)
        cls.conn.autocommit=True
        fixture(cls.conn)
        script(cls.conn,'A-forward.sql')
        script(cls.conn,'B-forward.sql')
        assert counts(cls.conn)==(5003,3341,9)


if __name__=='__main__': unittest.main()
