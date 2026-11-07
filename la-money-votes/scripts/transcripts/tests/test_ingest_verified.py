"""Offline checks for the one-recording approval and replacement boundary."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from transcripts import ingest_verified as ingest

VIDEO = "abcdefghijk"
VTT = """WEBVTT

00:00:01.000 --> 00:00:05.000
&gt;&gt; Y. Jurado: Housing policy needs public review.

00:00:06.000 --> 00:00:09.000
&gt;&gt; Speaker: I support more housing.
"""


class VerifiedIngestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.vtt = self.root / "captions.vtt"
        self.vtt.write_text(VTT)
        self.manifest = self.root / "manifest.json"
        self.sources = [
            {"primegov_id": meeting_id, "video_id": VIDEO,
             "meeting_date": "2026-08-14", "date_time": "2026-08-14T10:00:00",
             "title": title, "normalized_body": "City Council", "body_type": "city_council",
             "meeting_type": "regular_council", "committee_id": 1}
            for meeting_id, title in [(17801, "City Council Meeting"), (18451, "Special Council Meeting")]
        ]
        self.write(self.manifest, {"meetings": self.sources})
        self.caption = self.root / "caption-review.json"
        self.write(self.caption, {
            "video_id": VIDEO, "caption_language": ingest.build.CART_LANG_CODE,
            "track_kind": "manual", "payload_status": "ok",
            "payload_sha256": ingest.file_digest(self.vtt),
            "approved_by": "Fixture reviewer", "approved_at": "2026-11-06T12:00:00Z",
        })
        evidence = self.root / "target-review-evidence.json"
        self.write(evidence, {"fixture_only": True})
        self.target = self.root / "target-review.json"
        self.receipt = {
            "video_id": VIDEO, "supabase_url": "https://abcdefghijklmnopqrst.supabase.co",
            "embedding_model": ingest.build.EMBED_MODEL,
            "embedding_version": ingest.build.EMBED_VERSION, "dimensions": ingest.build.EMBED_DIM,
            "replacement_rpc": "replace_transcript_chunks",
            "schema_sha256": ingest.file_digest(ingest.build.DATA_DIR / "schema.sql"),
            "migration_sha256": ingest.file_digest(ingest.build.DATA_DIR / "migration_m3_1_replace_chunks.sql"),
            "reviewed_by": "Fixture reviewer", "reviewed_at": "2026-11-06T12:00:00Z",
            "existing_count": 0, "existing_rows_sha256": ingest.digest([]),
            "checks": {"rpc_signature": True, "rls_and_grants": True,
                       "model_dimensions_version": True, "exclusive_cohort_writer": True},
            "exclusive_writer_until": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            "evidence_files": [{"path": evidence.name, "sha256": ingest.file_digest(evidence)}],
        }
        self.write(self.target, self.receipt)
        self.database = []
        self.embedder = Mock(side_effect=lambda texts: [[1.0] * ingest.build.EMBED_DIM for _ in texts])
        self.replacement = Mock(side_effect=self.replace)
        self.reader = Mock(side_effect=lambda: copy.deepcopy(self.database))
        self.work = self.root / "execution"

    @staticmethod
    def write(path, content):
        path.write_text(json.dumps(content))

    def plan(self):
        return ingest.make_plan(self.manifest, VIDEO, self.vtt, self.caption, self.target, self.work)

    def replace(self, *, video_id, embedding_model, rows):
        self.assertEqual(video_id, VIDEO)
        self.assertEqual(embedding_model, ingest.build.EMBED_MODEL)
        self.database = copy.deepcopy(rows)
        return {"intended_count": len(rows), "upserted_count": len(rows), "deleted_count": 0}

    def execute(self, plan, transcript, rows, approved=None):
        return ingest.execute(plan, transcript, rows, approved or ingest.digest(plan), self.work,
                              embedder=self.embedder, replacement_rpc=self.replacement, read_rows=self.reader)

    def test_plan_is_offline_deterministic_and_preserves_shared_identities(self):
        with patch.object(ingest.build, "embed_batch", side_effect=AssertionError("network")):
            first = self.plan()
            second = self.plan()
        self.assertEqual(first, second)
        plan, transcript, rows = first
        self.assertEqual([source["primegov_id"] for source in transcript["source_meetings"]], [17801, 18451])
        self.assertEqual(plan["row_count"], 2)
        self.assertEqual(plan["parent_turn_count"], 2)
        self.assertEqual(plan["maximum_embedding_attempts"], 5)
        self.assertEqual(plan["maximum_replacement_attempts"], 1)
        self.assertNotIn("embedding", rows[0])
        self.assertEqual(rows[0]["resolved_official_id"], "cd14-official")
        self.assertIsNone(rows[1]["resolved_official_id"])

    def test_changed_vtt_or_unapproved_track_fails_offline(self):
        self.vtt.write_text(VTT + "\nchanged")
        with self.assertRaisesRegex(ValueError, "CART"):
            self.plan()
        self.vtt.write_text(VTT)
        caption = ingest.load_json(self.caption)
        caption["track_kind"] = "asr"
        self.write(self.caption, caption)
        with self.assertRaisesRegex(ValueError, "CART"):
            self.plan()

    def test_empty_or_invalid_timing_is_rejected_even_with_matching_hash(self):
        for payload in ["WEBVTT\n", VTT.replace("00:00:05.000", "00:00:00.000")]:
            self.vtt.write_text(payload)
            caption = ingest.load_json(self.caption)
            caption["payload_sha256"] = ingest.file_digest(self.vtt)
            self.write(self.caption, caption)
            with self.assertRaisesRegex(ValueError, "CART"):
                self.plan()

    def test_missing_grant_or_changed_target_evidence_is_rejected(self):
        self.receipt["checks"]["rls_and_grants"] = False
        self.write(self.target, self.receipt)
        with self.assertRaisesRegex(ValueError, "checks"):
            self.plan()
        self.receipt["checks"]["rls_and_grants"] = True
        self.write(self.target, self.receipt)
        (self.root / "target-review-evidence.json").write_text("changed")
        with self.assertRaisesRegex(ValueError, "evidence changed"):
            self.plan()

    def test_ambiguous_dates_block_without_silent_identity_fallback(self):
        self.sources[1]["meeting_date"] = "2026-08-15"
        self.write(self.manifest, {"meetings": self.sources})
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            self.plan()

    def test_unknown_labels_need_explicit_review(self):
        self.vtt.write_text(VTT.replace("Y. Jurado", "Unlisted Committee Chair"))
        caption = ingest.load_json(self.caption)
        caption["payload_sha256"] = ingest.file_digest(self.vtt)
        self.write(self.caption, caption)
        with self.assertRaisesRegex(ValueError, "unreviewed speaker labels"):
            self.plan()
        caption["reviewed_unknown_labels"] = ["Unlisted Committee Chair"]
        self.write(self.caption, caption)
        self.assertEqual(self.plan()[2][0]["resolved_role"], "unknown")

    def test_wrong_approval_or_modified_rows_cannot_make_external_calls(self):
        plan, transcript, rows = self.plan()
        with self.assertRaisesRegex(ValueError, "Approval"):
            self.execute(plan, transcript, rows, "wrong-hash")
        rows[0]["text"] = "Unapproved text"
        with self.assertRaisesRegex(ValueError, "Approval"):
            self.execute(plan, transcript, rows)
        self.reader.assert_not_called()
        self.embedder.assert_not_called()
        self.replacement.assert_not_called()

    def test_replacement_verified_and_rerun_is_no_paid_no_write(self):
        args = self.plan()
        result = self.execute(*args)
        self.assertEqual(result["row_count"], 2)
        second = self.execute(*args)
        self.assertEqual(second["replacement_calls"], 0)
        self.assertEqual(second["embedding_calls"], 0)
        self.embedder.assert_called_once()
        self.replacement.assert_called_once()
        artifact = ingest.load_json(self.work / f"{VIDEO}.json")
        self.assertEqual(len(artifact["source_meetings"]), 2)
        self.assertEqual(len(list(self.work.glob("*.before.json"))), 1)

    def test_live_cohort_drift_stops_before_paid_work(self):
        args = self.plan()
        self.database = [{**row, "embedding": [1.0] * ingest.build.EMBED_DIM} for row in args[2]]
        with self.assertRaisesRegex(ValueError, "changed"):
            self.execute(*args)
        self.embedder.assert_not_called()
        self.replacement.assert_not_called()

    def test_embedding_failure_prevents_write_and_repeated_spending(self):
        args = self.plan()
        self.embedder.side_effect = RuntimeError("fixture provider failed")
        with self.assertRaises(RuntimeError):
            self.execute(*args)
        with self.assertRaisesRegex(ValueError, "spending reconciliation"):
            self.execute(*args)
        self.embedder.assert_called_once()
        self.replacement.assert_not_called()

    def test_partial_or_invalid_embeddings_never_reach_replacement(self):
        for vectors in [[], [[0.0] * ingest.build.EMBED_DIM] * 2,
                        [[float("nan")] * ingest.build.EMBED_DIM] * 2]:
            with self.subTest(vectors=len(vectors)):
                self.work = self.root / f"invalid-{len(list(self.root.iterdir()))}"
                self.embedder.side_effect = None
                self.embedder.return_value = vectors
                with self.assertRaises(ValueError):
                    self.execute(*self.plan())
                self.replacement.assert_not_called()

    def test_unknown_replacement_outcome_recovers_only_by_matching_read(self):
        args = self.plan()
        def lost_response(**kwargs):
            self.replace(**kwargs)
            raise TimeoutError("response lost")
        self.replacement.side_effect = lost_response
        with self.assertRaises(TimeoutError):
            self.execute(*args)
        result = self.execute(*args)
        self.assertEqual(result["replacement_calls"], 0)
        self.replacement.assert_called_once()
        self.embedder.assert_called_once()

    def test_replacement_failure_does_not_rewrite_or_retry_automatically(self):
        args = self.plan()
        self.replacement.side_effect = RuntimeError("fixture database rejected")
        with self.assertRaises(RuntimeError):
            self.execute(*args)
        with self.assertRaisesRegex(ValueError, "replacement attempt"):
            self.execute(*args)
        self.assertEqual(self.database, [])
        self.replacement.assert_called_once()

    def test_post_replace_missing_key_is_not_verified(self):
        args = self.plan()
        def faulty(**kwargs):
            result = self.replace(**kwargs)
            self.database.pop()
            return result
        self.replacement.side_effect = faulty
        with self.assertRaisesRegex(ValueError, "verification failed"):
            self.execute(*args)
        checkpoint = ingest.load_json(next(self.work.glob("*.checkpoint.json")))
        self.assertEqual(checkpoint["state"], "replacement_pending")

    def test_modified_checkpoint_cannot_change_approved_content(self):
        args = self.plan()
        self.execute(*args)
        path = next(self.work.glob("*.checkpoint.json"))
        checkpoint = ingest.load_json(path)
        checkpoint["rows"][0]["text"] = "tampered"
        self.write(path, checkpoint)
        with self.assertRaisesRegex(ValueError, "Checkpoint content"):
            self.execute(*args)
        self.replacement.assert_called_once()

    def test_online_target_mismatch_fails_before_client_creation(self):
        plan, _, _ = self.plan()
        with patch.dict(ingest.os.environ, {"SUPABASE_URL": "https://wrong.supabase.co"}):
            with self.assertRaisesRegex(ValueError, "reviewed target"):
                ingest.online_adapters(plan)

    def test_same_plan_concurrent_entry_cannot_repeat_paid_work(self):
        args = self.plan()
        self.work.mkdir()
        lock_path = self.work / f"{ingest.digest(args[0])}.lock"
        with ingest.cohort_lock(lock_path):
            with self.assertRaises(BlockingIOError):
                self.execute(*args)
        self.reader.assert_not_called()
        self.embedder.assert_not_called()
        self.replacement.assert_not_called()

    def test_verified_checkpoint_never_replaces_after_target_reverted(self):
        args = self.plan()
        self.execute(*args)
        self.database = []
        with self.assertRaisesRegex(ValueError, "replacement attempt"):
            self.execute(*args)
        self.embedder.assert_called_once()
        self.replacement.assert_called_once()

    def test_different_work_directory_cannot_bypass_checkpoint(self):
        args = self.plan()
        self.work = self.root / "other-execution"
        with self.assertRaisesRegex(ValueError, "Execution directory"):
            self.execute(*args)
        self.reader.assert_not_called()
        self.embedder.assert_not_called()
        self.replacement.assert_not_called()

    def test_external_change_during_embedding_is_not_overwritten(self):
        args = self.plan()
        def concurrent_change(texts):
            self.database = [{**row, "text": "Concurrent update", "embedding": [1.0] * ingest.build.EMBED_DIM}
                             for row in args[2]]
            return [[1.0] * ingest.build.EMBED_DIM for _ in texts]
        self.embedder.side_effect = concurrent_change
        with self.assertRaisesRegex(ValueError, "changed during embedding"):
            self.execute(*args)
        self.replacement.assert_not_called()
        checkpoint = ingest.load_json(next(self.work.glob("*.checkpoint.json")))
        self.assertEqual(checkpoint["state"], "embedded")
        self.assertEqual(self.database[0]["text"], "Concurrent update")

    def test_expired_exclusive_writer_window_blocks_all_external_calls(self):
        self.receipt["exclusive_writer_until"] = "2020-01-01T00:00:00Z"
        self.write(self.target, self.receipt)
        with self.assertRaisesRegex(ValueError, "exclusive writer window"):
            self.execute(*self.plan())
        self.reader.assert_not_called()
        self.embedder.assert_not_called()
        self.replacement.assert_not_called()


if __name__ == "__main__":
    unittest.main()
