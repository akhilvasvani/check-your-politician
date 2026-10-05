import json
import tempfile
import unittest
from pathlib import Path

from transcripts.m3_1_ingest import (
    CART_LANGUAGE_CODE,
    apply_caption_preflight,
    attach_source_meetings,
    build_video_work_items,
    canonical_meeting_for_work_item,
    plan_stale_key_reconciliation,
    TransactionalReplacementIndexer,
    require_reviewed_coverage,
    speaker_coverage_report,
    embed_and_index,
)
from transcripts.speaker_resolver import SpeakerResolver


def meeting(
    primegov_id: int,
    video_id: str | None,
    *,
    state: str = "discovered",
    retryable: bool = True,
    title: str = "City Council Meeting",
) -> dict:
    return {
        "primegov_id": primegov_id,
        "video_id": video_id,
        "title": title,
        "meeting_date": "2026-06-30",
        "date_time": f"2026-06-30T{primegov_id % 24:02d}:00:00",
        "committee_id": 1,
        "normalized_body": "Los Angeles City Council",
        "body_type": "city_council",
        "meeting_type": "regular_council",
        "pipeline_state": state,
        "retryable": retryable,
        "last_error": None,
        "caption_status": "not_checked_m3_0",
    }


def manifest(rows: list[dict]) -> dict:
    return {
        "pipeline_states": [
            "discovered",
            "caption_preflighted",
            "caption_fetched",
            "parsed",
            "embedded",
            "indexed",
            "published",
            "blocked",
        ],
        "meetings": rows,
    }


class M31WorkItemTests(unittest.TestCase):
    def test_shared_video_is_one_work_item_with_all_source_meetings(self):
        doc = manifest([
            meeting(17801, "welTRe5_RH4"),
            meeting(18451, "welTRe5_RH4", title="Special City Council Meeting #2"),
            meeting(19000, "abcdefghijk"),
        ])
        items = build_video_work_items(doc)
        self.assertEqual([item.video_id for item in items], ["abcdefghijk", "welTRe5_RH4"])
        shared = next(item for item in items if item.video_id == "welTRe5_RH4")
        self.assertEqual(shared.primegov_ids, (17801, 18451))
        canonical = canonical_meeting_for_work_item(shared)
        self.assertEqual(canonical.primegov_id, 17801)
        self.assertEqual(canonical.title, "City Council Meeting")

        enriched = attach_source_meetings({"video_id": "welTRe5_RH4"}, shared)
        self.assertEqual(
            [item["primegov_id"] for item in enriched["source_meetings"]],
            [17801, 18451],
        )

    def test_preflight_requires_every_pending_video_and_checkpoints_atomically(self):
        doc = manifest([meeting(1, "aaaaaaaaaaa"), meeting(2, "bbbbbbbbbbb")])
        with self.assertRaisesRegex(ValueError, "missing preflight"):
            apply_caption_preflight(
                doc,
                {"videos": {"aaaaaaaaaaa": {"status": "approved", "caption_language": CART_LANGUAGE_CODE}}},
            )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            apply_caption_preflight(
                doc,
                {
                    "videos": {
                        "aaaaaaaaaaa": {
                            "status": "approved",
                            "caption_language": CART_LANGUAGE_CODE,
                            "checked_at": "2026-08-19T21:00:00+00:00",
                        },
                        "bbbbbbbbbbb": {
                            "status": "blocked",
                            "caption_status": "unavailable_no_cart",
                            "missing_reason": "no_known_cart_track",
                        },
                    }
                },
                manifest_path=path,
            )
            persisted = json.loads(path.read_text())
            self.assertFalse((Path(str(path) + ".tmp")).exists())

        approved, blocked = persisted["meetings"]
        self.assertEqual(approved["pipeline_state"], "caption_preflighted")
        self.assertEqual(approved["caption_status"], "approved_cart_track")
        self.assertIsNone(approved["last_error"])
        self.assertEqual(blocked["pipeline_state"], "blocked")
        self.assertFalse(blocked["retryable"])
        self.assertEqual(blocked["missing_reason"], "no_known_cart_track")

    def test_retryable_error_preserves_error_and_remains_pending(self):
        doc = manifest([meeting(1, "aaaaaaaaaaa")])
        apply_caption_preflight(
            doc,
            {
                "videos": {
                    "aaaaaaaaaaa": {
                        "status": "retryable_error",
                        "last_error": "browser cookie database locked",
                    }
                }
            },
        )
        row = doc["meetings"][0]
        self.assertEqual(row["pipeline_state"], "discovered")
        self.assertTrue(row["retryable"])
        self.assertEqual(row["last_error"], "browser cookie database locked")

    def test_partial_batch_applies_only_supplied_eligible_video(self):
        doc = manifest([meeting(1, "aaaaaaaaaaa"), meeting(2, "bbbbbbbbbbb")])
        applied = apply_caption_preflight(
            doc,
            {
                "videos": {
                    "aaaaaaaaaaa": {
                        "status": "approved",
                        "caption_language": CART_LANGUAGE_CODE,
                    }
                }
            },
            require_complete=False,
        )
        self.assertEqual(applied, ["aaaaaaaaaaa"])
        self.assertEqual(doc["meetings"][0]["pipeline_state"], "caption_preflighted")
        self.assertEqual(doc["meetings"][1]["pipeline_state"], "discovered")
        self.assertEqual(doc["meetings"][1]["caption_status"], "not_checked_m3_0")

    def test_partial_batch_checkpoints_every_source_row_for_shared_video(self):
        doc = manifest([
            meeting(17801, "welTRe5_RH4"),
            meeting(18451, "welTRe5_RH4", title="Special City Council Meeting #2"),
            meeting(2, "bbbbbbbbbbb"),
        ])
        apply_caption_preflight(
            doc,
            {
                "videos": {
                    "welTRe5_RH4": {
                        "status": "approved",
                        "caption_language": CART_LANGUAGE_CODE,
                    }
                }
            },
            require_complete=False,
        )
        shared_rows = [row for row in doc["meetings"] if row["video_id"] == "welTRe5_RH4"]
        self.assertEqual(
            [row["pipeline_state"] for row in shared_rows],
            ["caption_preflighted", "caption_preflighted"],
        )
        self.assertEqual(
            [row["caption_status"] for row in shared_rows],
            ["approved_cart_track", "approved_cart_track"],
        )

    def test_unknown_or_non_pending_result_is_rejected_even_for_partial_batch(self):
        doc = manifest([meeting(1, "aaaaaaaaaaa")])
        with self.assertRaisesRegex(ValueError, "unknown or non-pending"):
            apply_caption_preflight(
                doc,
                {
                    "videos": {
                        "zzzzzzzzzzz": {
                            "status": "approved",
                            "caption_language": CART_LANGUAGE_CODE,
                        }
                    }
                },
                require_complete=False,
            )

    def test_non_pending_result_is_rejected_even_for_partial_batch(self):
        doc = manifest([meeting(1, "aaaaaaaaaaa", state="caption_fetched")])
        with self.assertRaisesRegex(ValueError, "unknown or non-pending"):
            apply_caption_preflight(
                doc,
                {
                    "videos": {
                        "aaaaaaaaaaa": {
                            "status": "approved",
                            "caption_language": CART_LANGUAGE_CODE,
                        }
                    }
                },
                require_complete=False,
            )

    def test_preflight_preserves_supplied_evidence_fields(self):
        doc = manifest([meeting(1, "aaaaaaaaaaa")])
        apply_caption_preflight(
            doc,
            {
                "videos": {
                    "aaaaaaaaaaa": {
                        "status": "approved",
                        "caption_language": CART_LANGUAGE_CODE,
                        "track_name": "English CART",
                        "track_kind": "manual",
                        "track_vss_id": ".en-uYU-mmqFLq8",
                        "payload_status": "nonempty",
                        "payload_bytes": 1234,
                        "inspection_method": "authenticated_list_subs",
                    }
                }
            },
        )
        row = doc["meetings"][0]
        self.assertEqual(row["track_name"], "English CART")
        self.assertEqual(row["track_kind"], "manual")
        self.assertEqual(row["track_vss_id"], ".en-uYU-mmqFLq8")
        self.assertEqual(row["payload_status"], "nonempty")
        self.assertEqual(row["payload_bytes"], 1234)
        self.assertEqual(row["inspection_method"], "authenticated_list_subs")

    def test_empty_cart_payload_decision_fixture_blocks_without_asr(self):
        fixture = (
            Path(__file__).resolve().parent
            / "fixtures"
            / "preflight_2Wm-11hPNns.json"
        )
        doc = manifest([meeting(18197, "2Wm-11hPNns")])
        apply_caption_preflight(doc, json.loads(fixture.read_text()))
        row = doc["meetings"][0]
        self.assertEqual(row["pipeline_state"], "blocked")
        self.assertEqual(row["missing_reason"], "manual_cart_payload_empty")
        self.assertEqual(
            row["caption_status"], "cart_metadata_present_payload_empty"
        )
        self.assertFalse(row["retryable"])
        self.assertFalse(row["asr_approved"])
        self.assertEqual(row["payload_status"], "empty")
        self.assertEqual(row["payload_bytes"], 0)

    def test_blocked_result_cannot_approve_asr(self):
        doc = manifest([meeting(18197, "2Wm-11hPNns")])
        with self.assertRaisesRegex(ValueError, "cannot approve ASR"):
            apply_caption_preflight(
                doc,
                {
                    "videos": {
                        "2Wm-11hPNns": {
                            "status": "blocked",
                            "caption_status": "cart_metadata_present_payload_empty",
                            "missing_reason": "manual_cart_payload_empty",
                            "asr_approved": True,
                        }
                    }
                },
            )


class M31CoverageAndEmbeddingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[3]
        cls.resolver = SpeakerResolver(root / "data" / "transcripts" / "roster.json")

    def test_committee_label_coverage_requires_review(self):
        report = speaker_coverage_report(
            [
                {"source_label": "A. Nazarian"},
                {"source_label": "Committee Analyst"},
                {"source_label": "Committee Analyst"},
            ],
            self.resolver,
        )
        self.assertEqual(report["label_frequency"]["Committee Analyst"], 2)
        self.assertEqual(report["unresolved_labels"], {"Committee Analyst": 2})
        with self.assertRaisesRegex(ValueError, "Committee Analyst"):
            require_reviewed_coverage(report)
        require_reviewed_coverage(report, reviewed_unknown_labels={"Committee Analyst"})

    def test_partial_embeddings_never_reach_indexer(self):
        report = speaker_coverage_report([{"source_label": "Speaker"}], self.resolver)
        index_calls = []

        def partial_embedder(_texts):
            return [[0.0] * 1024]

        def indexer(rows):
            index_calls.append(rows)
            return len(rows)

        with self.assertRaisesRegex(ValueError, "partial embeddings"):
            embed_and_index(
                [{"text": "one"}, {"text": "two"}],
                embedder=partial_embedder,
                indexer=indexer,
                coverage_report=report,
            )
        self.assertEqual(index_calls, [])

    def test_indexer_acknowledgement_must_match_rows(self):
        report = speaker_coverage_report([{"source_label": "Speaker"}], self.resolver)
        with self.assertRaisesRegex(ValueError, "acknowledged 0 rows"):
            embed_and_index(
                [{"text": "one"}],
                embedder=lambda _texts: [[0.0] * 1024],
                indexer=lambda _rows: 0,
                coverage_report=report,
            )

    def test_stale_plan_never_authorizes_client_delete(self):
        plan = plan_stale_key_reconciliation(
            video_id="abcdefghijk",
            embedding_model="pplx-embed-v1-0.6b",
            existing_chunk_indexes=[0, 1, 2],
            intended_chunk_indexes=[0, 1],
        )
        self.assertEqual(plan["stale_chunk_indexes"], [2])
        self.assertFalse(plan["client_delete_permitted"])
        with self.assertRaisesRegex(ValueError, "not unique"):
            plan_stale_key_reconciliation(
                video_id="abcdefghijk",
                embedding_model="pplx-embed-v1-0.6b",
                existing_chunk_indexes=[],
                intended_chunk_indexes=[0, 0],
            )



class TransactionalReplacementIndexerTest(unittest.TestCase):
    """Offline coverage for the cohort grouping in front of the replacement RPC.

    The RPC's own transactional behavior is covered against a real database in
    tests/test_replace_transcript_chunks.py; these cases pin the client-side
    contract with no network.
    """

    def _row(self, idx, video_id="vidAAA", model="pplx-embed-v1-0.6b", dims=1024):
        return {
            "video_id": video_id,
            "chunk_idx": idx,
            "embedding": [0.0] * dims,
            "embedding_model": model,
            "text": f"turn {idx}",
        }

    def _rpc(self, calls, *, intended=None, upserted=None):
        def rpc(*, video_id, embedding_model, rows):
            calls.append((video_id, embedding_model, [r["chunk_idx"] for r in rows]))
            return {
                "intended_count": len(rows) if intended is None else intended,
                "upserted_count": len(rows) if upserted is None else upserted,
                "deleted_count": 0,
            }
        return rpc

    def test_groups_one_rpc_call_per_video_and_model(self):
        calls = []
        indexer = TransactionalReplacementIndexer(self._rpc(calls))
        total = indexer(
            [self._row(0), self._row(1)]
            + [self._row(0, video_id="vidBBB")]
            + [self._row(0, model="other-model")]
        )
        self.assertEqual(total, 4)
        self.assertEqual(len(calls), 3)
        self.assertIn(("vidAAA", "pplx-embed-v1-0.6b", [0, 1]), calls)
        self.assertIn(("vidBBB", "pplx-embed-v1-0.6b", [0]), calls)
        self.assertIn(("vidAAA", "other-model", [0]), calls)

    def test_rejects_duplicate_chunk_idx_before_calling_rpc(self):
        calls = []
        indexer = TransactionalReplacementIndexer(self._rpc(calls))
        with self.assertRaisesRegex(ValueError, "duplicate chunk_idx"):
            indexer([self._row(0), self._row(0)])
        self.assertEqual(calls, [])

    def test_rejects_missing_embedding_before_calling_rpc(self):
        calls = []
        indexer = TransactionalReplacementIndexer(self._rpc(calls))
        row = self._row(0)
        row["embedding"] = None
        with self.assertRaisesRegex(ValueError, "no embedding"):
            indexer([row])
        self.assertEqual(calls, [])

    def test_rejects_wrong_dimension_before_calling_rpc(self):
        calls = []
        indexer = TransactionalReplacementIndexer(self._rpc(calls))
        with self.assertRaisesRegex(ValueError, "dimension 384"):
            indexer([self._row(0, dims=384)])
        self.assertEqual(calls, [])

    def test_rejects_row_missing_cohort_keys(self):
        calls = []
        indexer = TransactionalReplacementIndexer(self._rpc(calls))
        row = self._row(0)
        del row["video_id"]
        with self.assertRaisesRegex(ValueError, "missing video_id"):
            indexer([row])
        self.assertEqual(calls, [])

    def test_trusts_the_rpc_over_the_payload_size(self):
        calls = []
        indexer = TransactionalReplacementIndexer(
            self._rpc(calls, upserted=1)
        )
        with self.assertRaisesRegex(ValueError, "expected 2"):
            indexer([self._row(0), self._row(1)])

    def test_reconciliation_plan_records_the_rpc_migration(self):
        plan = plan_stale_key_reconciliation(
            video_id="vidAAA",
            embedding_model="pplx-embed-v1-0.6b",
            existing_chunk_indexes=[0, 1, 2],
            intended_chunk_indexes=[0, 1],
        )
        self.assertFalse(plan["client_delete_permitted"])
        self.assertTrue(plan["rpc_implemented"])
        self.assertEqual(plan["stale_chunk_indexes"], [2])

if __name__ == "__main__":
    unittest.main()
