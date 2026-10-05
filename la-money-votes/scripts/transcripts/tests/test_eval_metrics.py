import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from transcripts.author_m3_3_eval import build
from transcripts.eval_metrics import cache_key, score_graded, validate_query_set
from transcripts.eval_transcript_rag import legacy_target, query_rpc, rpc_search


def judged(video_id, chunk_idx, sub_chunk_idx, grade):
    return {
        "key": {
            "video_id": video_id,
            "chunk_idx": chunk_idx,
            "sub_chunk_idx": sub_chunk_idx,
        },
        "grade": grade,
    }


class GradedMetricsTests(unittest.TestCase):
    def test_q06_partial_near_miss_gets_credit_without_becoming_direct(self):
        rows = [
            {"video_id": "oHYuOqkXv-0", "chunk_idx": 596, "sub_chunk_idx": 0},
            {"video_id": "oHYuOqkXv-0", "chunk_idx": 567, "sub_chunk_idx": 0},
        ]
        score = score_graded(rows, [
            judged("oHYuOqkXv-0", 596, 0, 2),
            judged("oHYuOqkXv-0", 567, 0, 3),
        ])
        self.assertEqual([2, 3], score["ranked_grades"])
        self.assertAlmostEqual(3 / 7, score["ndcg_at1"], places=6)
        self.assertGreater(score["ndcg_at3"], score["ndcg_at1"])

    def test_q19_top_results_are_only_adjacent(self):
        rows = [
            {"video_id": "oHYuOqkXv-0", "chunk_idx": 682, "sub_chunk_idx": 1},
            {"video_id": "oHYuOqkXv-0", "chunk_idx": 681, "sub_chunk_idx": 0},
            {"video_id": "oHYuOqkXv-0", "chunk_idx": 536, "sub_chunk_idx": 0},
        ]
        score = score_graded(rows, [
            judged("oHYuOqkXv-0", 682, 1, 1),
            judged("oHYuOqkXv-0", 681, 0, 1),
            judged("oHYuOqkXv-0", 536, 0, 3),
        ])
        self.assertEqual([1, 1, 3], score["ranked_grades"])
        self.assertAlmostEqual(1 / 7, score["ndcg_at1"], places=6)
        self.assertEqual(1.0, score["judged_coverage_at3"])

    def test_unjudged_rows_are_reported_not_silently_claimed_judged(self):
        rows = [
            {"video_id": "v", "chunk_idx": 1, "sub_chunk_idx": 0},
            {"video_id": "v", "chunk_idx": 2, "sub_chunk_idx": 0},
        ]
        score = score_graded(rows, [judged("v", 2, 0, 3)])
        self.assertEqual([None, 3], score["ranked_grades"])
        self.assertEqual(1, score["unjudged_count"])
        self.assertEqual(0.5, score["judged_coverage_at3"])

    def test_embedding_cache_key_changes_with_text_or_model(self):
        base = cache_key("q", "original", "model-a", 1)
        self.assertNotEqual(base, cache_key("q", "edited", "model-a", 1))
        self.assertNotEqual(base, cache_key("q", "original", "model-b", 1))
        self.assertNotEqual(base, cache_key("q", "original", "model-a", 2))


class QuerySetValidationTests(unittest.TestCase):
    def test_authored_fixture_validates_and_expands_legacy_set(self):
        qset = build()
        validate_query_set(qset)
        self.assertEqual(36, len(qset["queries"]))
        self.assertEqual(36, len({q["id"] for q in qset["queries"]}))
        classes = {label for q in qset["queries"] for label in q["classes"]}
        self.assertTrue(
            {"lexical", "paraphrase", "semantic", "date_bounded",
             "entity_confusion", "long_turn", "low_signal"}.issubset(classes)
        )

    def test_all_legacy_ids_and_targets_are_preserved(self):
        qset = build()
        by_id = {q["id"]: q for q in qset["queries"]}
        self.assertTrue({f"q{i:02d}" for i in range(1, 21)}.issubset(by_id))
        self.assertTrue({f"pc-{i:02d}" for i in range(1, 11)}.issubset(
            {query_id[:5] for query_id in by_id if query_id.startswith("pc-")}
        ))
        self.assertEqual(
            {"video_id": "oHYuOqkXv-0", "chunk_idx": 567, "sub_chunk_idx": None},
            by_id["q06"]["legacy_target"],
        )
        self.assertEqual(
            {"video_id": "oHYuOqkXv-0", "chunk_idx": 536, "sub_chunk_idx": None},
            by_id["q19"]["legacy_target"],
        )

    def test_invalid_date_range_is_rejected(self):
        qset = build()
        broken = copy.deepcopy(qset)
        broken["queries"][0]["search"]["date_from"] = "2026-08-20"
        broken["queries"][0]["search"]["date_to"] = "2026-08-19"
        with self.assertRaisesRegex(ValueError, "date_from"):
            validate_query_set(broken)

    def test_public_comment_official_filter_is_rejected(self):
        qset = build()
        broken = copy.deepcopy(qset)
        public = next(
            q for q in broken["queries"]
            if q["search"]["rpc"] == "search_public_comment"
        )
        public["search"]["official_id"] = "cd1-official"
        with self.assertRaisesRegex(ValueError, "cannot filter"):
            validate_query_set(broken)


class RunnerContractTests(unittest.TestCase):
    def test_mixed_fixture_uses_per_query_rpc(self):
        qset = {"rpc": "search_transcripts"}
        query = {"search": {"rpc": "search_public_comment"}}
        self.assertEqual("search_public_comment", query_rpc(query, qset, "auto"))
        self.assertEqual(
            "search_transcripts",
            query_rpc(query, qset, "search_transcripts"),
        )

    def test_legacy_target_supports_old_and_additive_schemas(self):
        self.assertEqual(
            ("v", 4, None),
            legacy_target({"expected_video_id": "v", "expected_chunk_idx": 4}),
        )
        self.assertEqual(
            ("v", 4, 2),
            legacy_target({
                "legacy_target": {
                    "video_id": "v",
                    "chunk_idx": 4,
                    "sub_chunk_idx": 2,
                }
            }),
        )

    @patch("transcripts.eval_transcript_rag.curl_json")
    def test_rpc_payload_carries_date_and_model_without_official_for_public(self, curl):
        curl.return_value = []
        rpc_search(
            "https://example.supabase.co",
            "anon",
            "search_public_comment",
            [0.0],
            None,
            0.25,
            date_from="2026-06-24",
            date_to="2026-06-24",
            embedding_model="pplx-embed-v1-0.6b",
        )
        body = curl.call_args.args[2]
        self.assertEqual("2026-06-24", body["p_date_from"])
        self.assertEqual("2026-06-24", body["p_date_to"])
        self.assertEqual("pplx-embed-v1-0.6b", body["p_embedding_model"])
        self.assertNotIn("p_official_id", body)

    def test_saved_m2_legacy_regression_contract(self):
        repo = Path(__file__).resolve().parents[3]
        saved = json.loads(
            (repo / "data" / "transcripts" / "eval_results_m2.json").read_text()
        )
        official = saved["runs"]["search_transcripts"]["aggregate_by_floor"]["0.25"]
        self.assertEqual(90.0, official["parent_at1_pct"])
        self.assertEqual(100.0, official["parent_at3_pct"])
        q06 = saved["per_query"]["search_transcripts"]["q06"]["at_floor"]["0.25"]["score"]
        q19 = saved["per_query"]["search_transcripts"]["q19"]["at_floor"]["0.25"]["score"]
        q13 = saved["per_query"]["search_transcripts"]["q13"]["at_floor"]["0.25"]["score"]
        self.assertEqual(1, q06["parent_rank"])
        self.assertEqual(2, q19["parent_rank"])
        self.assertEqual(0, q13["exact_rank"])


if __name__ == "__main__":
    unittest.main()
