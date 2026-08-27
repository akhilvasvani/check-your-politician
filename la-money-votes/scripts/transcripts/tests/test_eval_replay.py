"""Fixture-based tests for the M3.3 offline candidate-pool replay path.

Everything here runs against synthetic traces and query sets. No network,
embedding, caption, or database access is involved -- which is the point of
the module under test.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from transcripts.eval_replay import (
    build_worksheet,
    coverage_complete,
    extract_candidate_pool,
    load_trace,
    load_traces,
    merge_worksheet,
    pool_status,
    replay,
    stale_reasons,
)

MODEL = "pplx-embed-v1-0.6b"


def row(chunk_idx, sim, *, video="vidA", sub=0, name="Tim McOsker", head=None):
    return {
        "video_id": video,
        "chunk_idx": chunk_idx,
        "sub_chunk_idx": sub,
        "sub_chunk_of": 1,
        "similarity": sim,
        "resolved_name": name,
        "text_head": head or f"text for chunk {chunk_idx}",
    }


def query(qid="q01", *, text="what about the audit", judgments=None, **search_over):
    search = {
        "rpc": "search_transcripts",
        "official_id": "tim-mcosker",
        "match_count": 8,
        "embedding_model": MODEL,
        "embedding_version": 1,
        "date_from": None,
        "date_to": None,
    }
    search.update(search_over)
    return {
        "id": qid,
        "text": text,
        "classes": ["lexical"],
        "body": "city_council",
        "search": search,
        "legacy_target": {"video_id": "vidA", "chunk_idx": 1, "sub_chunk_idx": 0},
        "judgments": judgments if judgments is not None else [{
            "key": {"video_id": "vidA", "chunk_idx": 1, "sub_chunk_idx": 0},
            "grade": 3,
            "label": "direct",
            "rationale": "locked target",
            "reviewer": "test",
            "reviewed_at": "2026-08-20T00:00:00Z",
        }],
    }


def qset(queries):
    return {
        "schema_version": "m3.3-v1",
        "evaluation": {"note": "fixture"},
        "coverage": {
            "not_eligible": [{"official_id": "cd8-official", "reason": "attribution"}],
            "pending": [{"body": "committee", "reason": "not yet indexed"}],
        },
        "queries": queries,
    }


def trace(qid="q01", *, floors=None, q=None, rpc="search_transcripts"):
    """Build a saved trace. `rpc=None` mirrors the M2 report, whose inner
    traces carry only `query` and `at_floor` and rely on the RPC they are
    filed under."""
    floors = floors or {
        "0.15": [row(1, 0.50), row(2, 0.40), row(3, 0.20)],
        "0.25": [row(1, 0.50), row(2, 0.40)],
        "0.35": [row(1, 0.50)],
    }
    entry = {
        "query": q or query(qid),
        "at_floor": {k: {"score": {}, "returned": v} for k, v in floors.items()},
    }
    if rpc is not None:
        entry["rpc"] = rpc
    return {qid: entry}


class LoadTraceTest(unittest.TestCase):
    def _write(self, tmp, payload, name="t.json"):
        path = Path(tmp) / name
        path.write_text(json.dumps(payload))
        return path

    def test_reads_flat_layout(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, {"per_query": trace()})
            self.assertEqual(list(load_trace(path)), ["q01"])

    def test_reads_layout_nested_by_rpc(self):
        with TemporaryDirectory() as tmp:
            payload = {"per_query": {
                "search_transcripts": trace("q01", rpc=None),
                "search_public_comment": trace("pc-01", rpc=None),
            }}
            loaded = load_trace(self._write(tmp, payload))
            self.assertEqual(sorted(loaded), ["pc-01", "q01"])
            # The RPC the trace was filed under is retained.
            self.assertEqual(loaded["pc-01"]["rpc"], "search_public_comment")

    def test_rejects_report_without_traces(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "no per_query"):
                load_trace(self._write(tmp, {"per_query": {}}))

    def test_rejects_duplicate_query_across_files(self):
        with TemporaryDirectory() as tmp:
            a = self._write(tmp, {"per_query": trace("q01")}, "a.json")
            b = self._write(tmp, {"per_query": trace("q01")}, "b.json")
            with self.assertRaisesRegex(ValueError, "more than one file"):
                load_traces([a, b])


class CandidatePoolTest(unittest.TestCase):
    def test_unions_candidates_across_floors(self):
        pool = extract_candidate_pool(trace()["q01"])
        self.assertEqual([c["key"]["chunk_idx"] for c in pool], [1, 2, 3])

    def test_records_best_rank_and_max_similarity(self):
        pool = extract_candidate_pool(trace()["q01"])
        by_idx = {c["key"]["chunk_idx"]: c for c in pool}
        self.assertEqual(by_idx[1]["best_rank"], 0)
        self.assertEqual(by_idx[3]["best_rank"], 2)
        self.assertEqual(by_idx[1]["max_similarity"], 0.50)
        # A row that survives only the lowest floor is still in the pool.
        self.assertEqual(by_idx[3]["seen_at_floors"], ["0.15"])
        self.assertEqual(by_idx[1]["seen_at_floors"], ["0.15", "0.25", "0.35"])

    def test_status_splits_judged_from_ungraded(self):
        status = pool_status(query(), trace()["q01"])
        self.assertEqual(status["pool_size"], 3)
        self.assertEqual(status["judged"], 1)
        self.assertEqual(status["ungraded"], 2)
        self.assertAlmostEqual(status["coverage"], 1 / 3, places=5)


class StalenessTest(unittest.TestCase):
    def test_matching_query_is_not_stale(self):
        self.assertEqual(stale_reasons(query(), trace()["q01"]), [])

    def test_edited_text_invalidates_the_trace(self):
        reasons = stale_reasons(query(text="different wording"), trace()["q01"])
        self.assertTrue(any("query text changed" in r for r in reasons))

    def test_changed_search_parameters_invalidate_the_trace(self):
        for field, value in (
            ("date_from", "2026-07-01"),
            ("official_id", "someone-else"),
            ("embedding_model", "other-model"),
            ("match_count", 5),
        ):
            with self.subTest(field=field):
                reasons = stale_reasons(query(**{field: value}), trace()["q01"])
                self.assertTrue(
                    any(field in r for r in reasons), f"{field} change not detected"
                )


class WorksheetTest(unittest.TestCase):
    def test_lists_only_ungraded_candidates(self):
        sheet = build_worksheet(qset([query()]), trace(), queries_file="q.json",
                                trace_files=["t.json"])
        entry = sheet["queries"][0]
        self.assertEqual(entry["already_judged"], 1)
        self.assertEqual([c["key"]["chunk_idx"] for c in entry["candidates"]], [2, 3])
        # Grades start empty; an unreviewed candidate is never pre-filled as 0.
        self.assertTrue(all(c["grade"] is None for c in entry["candidates"]))

    def test_reports_queries_with_no_trace(self):
        sheet = build_worksheet(qset([query(), query("q02")]), trace(),
                                queries_file="q.json", trace_files=["t.json"])
        self.assertEqual(sheet["queries_without_trace"], ["q02"])


class MergeTest(unittest.TestCase):
    def _sheet(self, qs, **over):
        sheet = build_worksheet(qs, trace(), queries_file="q.json", trace_files=["t.json"])
        for candidate in sheet["queries"][0]["candidates"]:
            candidate.update(over)
        return sheet

    def test_explicit_grade_zero_is_recorded_as_a_judgment(self):
        qs = qset([query()])
        sheet = self._sheet(qs, grade=0, rationale="reviewed; off topic")
        merged, stats = merge_worksheet(qs, sheet, reviewer="reviewer-a")
        self.assertEqual(stats["judgments_added"], 2)
        grades = {j["key"]["chunk_idx"]: j["grade"] for j in merged["queries"][0]["judgments"]}
        self.assertEqual(grades, {1: 3, 2: 0, 3: 0})
        zero = next(j for j in merged["queries"][0]["judgments"] if j["grade"] == 0)
        self.assertEqual(zero["label"], "irrelevant")
        self.assertEqual(zero["reviewer"], "reviewer-a")

    def test_unreviewed_candidates_are_skipped_not_zeroed(self):
        qs = qset([query()])
        sheet = self._sheet(qs)  # grade stays None
        merged, stats = merge_worksheet(qs, sheet, reviewer="reviewer-a")
        self.assertEqual(stats["judgments_added"], 0)
        self.assertEqual(stats["candidates_left_unreviewed"], 2)
        self.assertEqual(len(merged["queries"][0]["judgments"]), 1)

    def test_graded_candidate_requires_a_rationale(self):
        qs = qset([query()])
        sheet = self._sheet(qs, grade=0)
        with self.assertRaisesRegex(ValueError, "needs a rationale"):
            merge_worksheet(qs, sheet, reviewer="reviewer-a")

    def test_rejects_out_of_range_grade(self):
        qs = qset([query()])
        sheet = self._sheet(qs, grade=7, rationale="x")
        with self.assertRaisesRegex(ValueError, "grade must be an integer 0-3"):
            merge_worksheet(qs, sheet, reviewer="reviewer-a")

    def test_rejects_regrading_an_existing_judgment(self):
        qs = qset([query()])
        sheet = build_worksheet(qs, trace(), queries_file="q.json", trace_files=["t.json"])
        sheet["queries"][0]["candidates"].append({
            "key": {"video_id": "vidA", "chunk_idx": 1, "sub_chunk_idx": 0},
            "grade": 1, "rationale": "conflicting regrade",
        })
        with self.assertRaisesRegex(ValueError, "already judged"):
            merge_worksheet(qs, sheet, reviewer="reviewer-a")


class ReplayTest(unittest.TestCase):
    def test_replays_saved_rows_and_preserves_legacy_metrics(self):
        report = replay(qset([query()]), trace())
        self.assertEqual(report["n_queries_replayed"], 1)
        agg = report["aggregate_by_floor"]["0.25"]
        # Target vidA/chunk 1 is rank 0 in the saved rows at every floor.
        self.assertEqual(agg["parent_at1_pct"], 100.0)
        self.assertEqual(agg["exact_at1_pct"], 100.0)
        self.assertEqual(agg["null_pct"], 0.0)
        for field in ("parent_at1_pct", "parent_at3_pct", "parent_at8_pct",
                      "exact_at1_pct", "exact_at3_pct", "exact_at8_pct",
                      "null_pct", "top1_sim_median"):
            self.assertIn(field, agg["legacy_metrics"], f"{field} missing from legacy block")

    def test_excludes_stale_traces_instead_of_scoring_them(self):
        report = replay(qset([query(text="rewritten"), query("q02")]),
                        {**trace(), **trace("q02")})
        self.assertIn("q01", report["excluded_queries"])
        self.assertEqual(report["n_queries_replayed"], 1)

    def test_query_without_a_trace_is_excluded_and_named(self):
        report = replay(qset([query(), query("q02")]), trace())
        self.assertEqual(report["excluded_queries"]["q02"], ["no saved trace"])

    def test_unjudged_rows_are_not_scored_as_zero(self):
        report = replay(qset([query()]), trace())
        graded = report["aggregate_by_floor"]["0.15"]["graded_metrics"]
        # 3 rows returned, 1 judged.
        self.assertEqual(graded["unjudged_rows"], 2)
        self.assertLess(graded["judged_coverage_at8"], 1.0)

    def test_reports_pool_judgment_coverage(self):
        report = replay(qset([query()]), trace())
        cov = report["judgment_coverage"]
        self.assertEqual(cov["pool_candidates_total"], 3)
        self.assertEqual(cov["pool_judged_total"], 1)
        self.assertEqual(cov["queries_with_incomplete_pool_judgments"], ["q01"])

    def test_coverage_gate_fails_while_pool_is_incomplete(self):
        complete, problems = coverage_complete(replay(qset([query()]), trace()))
        self.assertFalse(complete)
        self.assertTrue(problems)

    def test_coverage_gate_passes_once_every_candidate_is_judged(self):
        judgments = [{
            "key": {"video_id": "vidA", "chunk_idx": idx, "sub_chunk_idx": 0},
            "grade": grade, "label": "reviewed", "rationale": "reviewed",
            "reviewer": "test", "reviewed_at": "2026-08-20T00:00:00Z",
        } for idx, grade in ((1, 3), (2, 1), (3, 0))]
        report = replay(qset([query(judgments=judgments)]), trace())
        complete, problems = coverage_complete(report)
        self.assertTrue(complete, problems)
        self.assertEqual(report["judgment_coverage"]["pool_judged_total"], 3)
        graded = report["aggregate_by_floor"]["0.15"]["graded_metrics"]
        self.assertEqual(graded["unjudged_rows"], 0)
        self.assertEqual(graded["judged_coverage_at8"], 1.0)

    def test_raises_when_nothing_is_replayable(self):
        with self.assertRaisesRegex(ValueError, "no query has a replayable trace"):
            replay(qset([query("q02")]), trace())


if __name__ == "__main__":
    unittest.main()
