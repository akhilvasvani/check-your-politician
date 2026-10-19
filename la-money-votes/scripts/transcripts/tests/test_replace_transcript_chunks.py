"""Disposable-database integration tests for the M3.1 replacement RPC.

These tests require a throwaway Postgres cluster with pgvector. They are
skipped unless TRANSCRIPT_TEST_PG_DSN points at one, so the default offline
suite stays runnable with no database.

    scripts/transcripts/run_pg_tests.sh

brings up a disposable cluster, exports the DSN, and runs this module.

The RPC under test is data/transcripts/migration_m3_1_replace_chunks.sql.
Every failure case asserts the *whole* replacement rolled back, which is the
property that makes client-side upsert-then-delete unnecessary.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

DSN = os.environ.get("TRANSCRIPT_TEST_PG_DSN")

try:  # pragma: no cover - import guard
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:  # pragma: no cover
    psycopg2 = None

REPO = Path(__file__).resolve().parents[3]
SCHEMA_SQL = REPO / "data" / "transcripts" / "schema.sql"
REPLACE_SQL = REPO / "data" / "transcripts" / "migration_m3_1_replace_chunks.sql"

MODEL = "pplx-embed-v1-0.6b"
OTHER_MODEL = "some-other-embed-v2"


def _vec(seed: float, dims: int = 1024) -> list[float]:
    return [round(seed + (i % 7) * 0.001, 6) for i in range(dims)]


def _row(chunk_idx: int, *, video_id="vidAAA", model=MODEL, text=None, **over):
    row = {
        "video_id": video_id,
        "meeting_date": "2026-08-14",
        "chunk_idx": chunk_idx,
        "start_sec": 10.0 * chunk_idx,
        "end_sec": 10.0 * chunk_idx + 9.0,
        "source_label": "T. McOsker",
        "resolved_role": "councilmember",
        "resolved_official_id": "tim-mcosker",
        "resolved_name": "Tim McOsker",
        "resolution_method": "exact-councilmember",
        "text": text or f"turn number {chunk_idx}",
        "token_count": 5,
        "turn_speaker_raw": "T. McOsker",
        "sub_chunk_idx": 0,
        "sub_chunk_of": 1,
        "embedding": _vec(0.01 * chunk_idx),
        "embedding_model": model,
        "embedding_version": 1,
    }
    row.update(over)
    return row


@unittest.skipUnless(DSN and psycopg2, "set TRANSCRIPT_TEST_PG_DSN to run")
class ReplaceTranscriptChunksTest(unittest.TestCase):
    """Each test runs against a freshly truncated table on a disposable DB."""

    @classmethod
    def setUpClass(cls):
        cls.conn = psycopg2.connect(DSN)
        cls.conn.autocommit = True
        with cls.conn.cursor() as cur:
            # Supabase roles the checked-in SQL grants to.
            for role in ("anon", "authenticated", "service_role"):
                cur.execute(
                    "do $$ begin if not exists (select 1 from pg_roles "
                    "where rolname=%s) then execute format('create role %%I', %s); "
                    "end if; end $$;",
                    (role, role),
                )
            cur.execute(SCHEMA_SQL.read_text())
            cur.execute(REPLACE_SQL.read_text())

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        with self.conn.cursor() as cur:
            cur.execute("truncate transcript_chunks")

    # -- helpers ---------------------------------------------------------
    def seed(self, rows):
        return self.replace(rows[0]["video_id"], rows[0]["embedding_model"], rows)

    def replace(self, video_id, model, rows):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "select * from replace_transcript_chunks(%s,%s,%s::jsonb)",
                (video_id, model, json.dumps(rows)),
            )
            return cur.fetchone()

    def keys(self, video_id="vidAAA", model=MODEL):
        with self.conn.cursor() as cur:
            cur.execute(
                "select chunk_idx from transcript_chunks where video_id=%s "
                "and embedding_model=%s order by chunk_idx",
                (video_id, model),
            )
            return [r[0] for r in cur.fetchall()]

    def texts(self, video_id="vidAAA", model=MODEL):
        with self.conn.cursor() as cur:
            cur.execute(
                "select chunk_idx, text from transcript_chunks where video_id=%s "
                "and embedding_model=%s order by chunk_idx",
                (video_id, model),
            )
            return dict(cur.fetchall())

    def assertRollback(self, expected_keys, expected_texts=None):
        self.assertEqual(self.keys(), expected_keys)
        if expected_texts is not None:
            self.assertEqual(self.texts(), expected_texts)

    # -- happy path ------------------------------------------------------
    def test_inserts_complete_cohort(self):
        res = self.seed([_row(i) for i in range(5)])
        self.assertEqual(res["intended_count"], 5)
        self.assertEqual(res["upserted_count"], 5)
        self.assertEqual(res["deleted_count"], 0)
        self.assertEqual(self.keys(), [0, 1, 2, 3, 4])

    def test_shorter_reparse_removes_stale_keys_atomically(self):
        self.seed([_row(i) for i in range(5)])
        res = self.replace(
            "vidAAA", MODEL, [_row(i, text=f"reparsed {i}") for i in range(3)]
        )
        self.assertEqual(res["intended_count"], 3)
        self.assertEqual(res["deleted_count"], 2)
        # Exactly the new parse remains -- no mixing of two parses.
        self.assertEqual(self.keys(), [0, 1, 2])
        self.assertEqual(
            self.texts(), {0: "reparsed 0", 1: "reparsed 1", 2: "reparsed 2"}
        )

    def test_repeat_replacement_is_idempotent(self):
        rows = [_row(i) for i in range(4)]
        self.seed(rows)
        res = self.replace("vidAAA", MODEL, rows)
        self.assertEqual(res["deleted_count"], 0)
        self.assertEqual(res["upserted_count"], 4)
        self.assertEqual(self.keys(), [0, 1, 2, 3])

    def test_longer_reparse_adds_keys(self):
        self.seed([_row(i) for i in range(2)])
        res = self.replace("vidAAA", MODEL, [_row(i) for i in range(6)])
        self.assertEqual(res["deleted_count"], 0)
        self.assertEqual(self.keys(), [0, 1, 2, 3, 4, 5])

    # -- cohort isolation ------------------------------------------------
    def test_only_intended_video_and_model_change(self):
        self.seed([_row(i) for i in range(4)])
        self.seed([_row(i, video_id="vidBBB") for i in range(4)])
        self.seed([_row(i, model=OTHER_MODEL) for i in range(4)])

        self.replace("vidAAA", MODEL, [_row(0)])

        self.assertEqual(self.keys("vidAAA", MODEL), [0])
        self.assertEqual(self.keys("vidBBB", MODEL), [0, 1, 2, 3])
        self.assertEqual(self.keys("vidAAA", OTHER_MODEL), [0, 1, 2, 3])

    # -- staged-row validation (all must roll back) ----------------------
    def test_rejects_empty_row_set(self):
        self.seed([_row(i) for i in range(3)])
        with self.assertRaisesRegex(Exception, "empty row set"):
            self.replace("vidAAA", MODEL, [])
        self.assertRollback([0, 1, 2])

    def test_rejects_duplicate_chunk_idx(self):
        self.seed([_row(i) for i in range(3)])
        before = self.texts()
        with self.assertRaisesRegex(Exception, "not unique"):
            self.replace("vidAAA", MODEL, [_row(0, text="dup a"), _row(0, text="dup b")])
        self.assertRollback([0, 1, 2], before)

    def test_rejects_wrong_dimension_embedding(self):
        self.seed([_row(i) for i in range(3)])
        before = self.texts()
        bad = [_row(0), _row(1, embedding=_vec(0.5, dims=384))]
        with self.assertRaisesRegex(Exception, "non-1024-dim"):
            self.replace("vidAAA", MODEL, bad)
        self.assertRollback([0, 1, 2], before)

    def test_rejects_missing_required_metadata(self):
        self.seed([_row(i) for i in range(3)])
        before = self.texts()
        with self.assertRaisesRegex(Exception, "missing required metadata"):
            self.replace("vidAAA", MODEL, [_row(0), _row(1, text="   ")])
        self.assertRollback([0, 1, 2], before)

    def test_rejects_foreign_video_id_in_payload(self):
        self.seed([_row(i) for i in range(3)])
        before = self.texts()
        with self.assertRaisesRegex(Exception, "foreign video_id"):
            self.replace("vidAAA", MODEL, [_row(0), _row(1, video_id="vidZZZ")])
        self.assertRollback([0, 1, 2], before)

    def test_rejects_foreign_embedding_model_in_payload(self):
        self.seed([_row(i) for i in range(3)])
        before = self.texts()
        with self.assertRaisesRegex(Exception, "foreign embedding_model"):
            self.replace("vidAAA", MODEL, [_row(0), _row(1, model=OTHER_MODEL)])
        self.assertRollback([0, 1, 2], before)

    def test_rejects_blank_identifiers(self):
        with self.assertRaisesRegex(Exception, "p_video_id is required"):
            self.replace("  ", MODEL, [_row(0)])
        with self.assertRaisesRegex(Exception, "p_embedding_model is required"):
            self.replace("vidAAA", "", [_row(0)])

    # -- step (5): verification failure must roll back --------------------
    def _with_trigger(self, body_sql, trigger_sql):
        """Install a temporary trigger that corrupts the upsert, then clean up."""
        with self.conn.cursor() as cur:
            cur.execute(body_sql)
            cur.execute(trigger_sql)

    def _drop_trigger(self, name, func):
        with self.conn.cursor() as cur:
            cur.execute(f"drop trigger if exists {name} on transcript_chunks")
            cur.execute(f"drop function if exists {func}()")

    def test_missing_intended_key_fails_verification_and_rolls_back(self):
        """Pins guard (5): intended keys must be readable back after the upsert.

        An AFTER INSERT trigger removes one row *after* it is counted, so the
        statement row_count still looks correct and only the intended-key
        presence check can catch it. Without that check the RPC would proceed
        to delete stale rows against an incomplete cohort.
        """
        self.seed([_row(i) for i in range(5)])
        before = self.texts()
        self._with_trigger(
            """
            create or replace function _vanish_one() returns trigger
            language plpgsql as $f$
            begin
              delete from transcript_chunks where id = new.id;
              return null;
            end $f$;
            """,
            # ON CONFLICT DO UPDATE routes pre-existing keys to the UPDATE
            # path, so the trigger must cover both to reach the upserted row.
            "create trigger _vanish after insert or update on transcript_chunks "
            "for each row when (new.chunk_idx = 1) execute function _vanish_one();",
        )
        try:
            with self.assertRaisesRegex(Exception, "verification failed"):
                self.replace("vidAAA", MODEL, [_row(i, text=f"new {i}") for i in range(3)])
            self.assertRollback([0, 1, 2, 3, 4], before)
        finally:
            self._drop_trigger("_vanish", "_vanish_one")

    def test_upsert_rowcount_shortfall_rolls_back(self):
        """Pins the secondary guard: fewer rows written than intended."""
        self.seed([_row(i) for i in range(5)])
        before = self.texts()
        self._with_trigger(
            """
            create or replace function _swallow_one() returns trigger
            language plpgsql as $f$
            begin
              if new.chunk_idx = 1 then return null; end if;
              return new;
            end $f$;
            """,
            "create trigger _swallow before insert on transcript_chunks "
            "for each row execute function _swallow_one();",
        )
        try:
            with self.assertRaisesRegex(Exception, "verification failed|upsert touched"):
                self.replace("vidAAA", MODEL, [_row(i, text=f"new {i}") for i in range(3)])
            # Original five-chunk parse is fully intact: no partial replacement.
            self.assertRollback([0, 1, 2, 3, 4], before)
        finally:
            self._drop_trigger("_swallow", "_swallow_one")

    # -- grants ----------------------------------------------------------
    def test_write_rpc_is_not_executable_by_browser_roles(self):
        with self.conn.cursor() as cur:
            for role in ("anon", "authenticated"):
                cur.execute(
                    "select has_function_privilege(%s,"
                    " 'replace_transcript_chunks(text,text,jsonb)', 'EXECUTE')",
                    (role,),
                )
                self.assertFalse(cur.fetchone()[0], f"{role} must not execute the write RPC")
            cur.execute(
                "select has_function_privilege('service_role',"
                " 'replace_transcript_chunks(text,text,jsonb)', 'EXECUTE')"
            )
            self.assertTrue(cur.fetchone()[0], "service_role must execute the write RPC")

    def test_read_rpcs_remain_available_to_browser_roles(self):
        with self.conn.cursor() as cur:
            cur.execute(
                "select has_function_privilege('anon',"
                " 'get_transcript_coverage(text,text)', 'EXECUTE')"
            )
            self.assertTrue(cur.fetchone()[0])

    def test_replacement_is_visible_to_the_coverage_rpc(self):
        self.seed(
            [_row(i, sub_chunk_idx=0, sub_chunk_of=1) for i in range(3)]
            + [_row(3, sub_chunk_idx=1, sub_chunk_of=2)]
        )
        with self.conn.cursor() as cur:
            cur.execute(
                "select speaking_turns, meeting_count from "
                "get_transcript_coverage('tim-mcosker')"
            )
            turns, meetings = cur.fetchone()
        # Sub-chunk rows must not inflate the speaking-turn count.
        self.assertEqual((turns, meetings), (3, 1))


if __name__ == "__main__":
    unittest.main()
