#!/usr/bin/env python3
"""Plan one reviewed CART recording, then explicitly execute its approved hash.

The default invocation is offline. Required caption evidence is an operator-
reviewed JSON object with video_id, caption_language, track_kind='manual',
payload_status='ok', payload_sha256, approved_by, approved_at, and optional
reviewed_unknown_labels. This runner never downloads or approves captions.

Target verification is a separate reviewed JSON receipt containing supabase_url,
video_id, embedding_model, embedding_version, dimensions, replacement_rpc,
schema_sha256, migration_sha256, reviewed_by, reviewed_at, existing_count,
existing_rows_sha256, checks={rpc_signature:true, rls_and_grants:true,
model_dimensions_version:true, exclusive_cohort_writer:true}, an aware ISO
exclusive_writer_until timestamp, and evidence_files=[{path,sha256}]. Evidence
paths are relative to that receipt. A receipt records an independent review,
not proof that this offline planner inspected or migrated a live database.

--execute additionally requires --approved-plan-sha256. Host/owner approval for
paid calls and shared writes is still required. The local checkpoint supports
one cohort and retains a before-image plus materialized replacement rows. A
rerun verifies the database before resuming. Source provenance stays in the
staged canonical artifact because the existing RPC has no source_meetings
column. The existing RPC has no compare-and-swap precondition. Live execution
requires an independently reviewed exclusive writer window for this cohort,
covering the full deadline. A second read before replacement detects intervening
changes but cannot eliminate the read/write race without that ownership gate. Publishing that artifact and the manifest is a separate reviewed step.
"""
from __future__ import annotations

import argparse
import hashlib
import fcntl
import json
import math
import os
from pathlib import Path
import re
import signal
import struct
import sys
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from transcripts import build_transcripts as build
from transcripts.diagnose_captions import inspect_payload
from transcripts.m3_1_ingest import (
    VideoWorkItem, TransactionalReplacementIndexer, atomic_write_json,
    canonical_meeting_for_work_item, embed_and_index, load_json,
    require_reviewed_coverage, speaker_coverage_report, utc_now,
)

FIELDS = (
    "video_id", "meeting_date", "chunk_idx", "start_sec", "end_sec",
    "source_label", "resolved_role", "resolved_official_id", "resolved_name",
    "resolution_method", "text", "token_count", "turn_speaker_raw",
    "sub_chunk_idx", "sub_chunk_of", "embedding_model", "embedding_version",
    "embedding",
)
SOURCE_FILES = (
    "ingest_verified.py", "build_transcripts.py", "m3_1_ingest.py",
    "vtt_flatten.py", "speaker_resolver.py", "chunker.py", "diagnose_captions.py",
)


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalise_rows(rows: list[dict]) -> list[dict]:
    """Ignore database-generated IDs; reproduce PostgreSQL real/vector types."""
    result = []
    for row in rows:
        item = {field: row[field] for field in FIELDS}
        for field in ("start_sec", "end_sec"):
            item[field] = struct.unpack("f", struct.pack("f", float(item[field])))[0]
        embedding = item["embedding"]
        if isinstance(embedding, str):
            embedding = json.loads(embedding)
        if len(embedding) != build.EMBED_DIM or any(
            isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
            for value in embedding
        ) or not any(embedding):
            raise ValueError("Invalid finite nonzero embedding")
        item["embedding"] = [float(value) for value in embedding]
        result.append(item)
    return sorted(result, key=lambda row: row["chunk_idx"])


def verify_receipt(path: Path, video_id: str) -> dict:
    receipt = load_json(path)
    expected = {
        "video_id": video_id, "embedding_model": build.EMBED_MODEL,
        "embedding_version": build.EMBED_VERSION, "dimensions": build.EMBED_DIM,
        "replacement_rpc": "replace_transcript_chunks",
        "schema_sha256": file_digest(build.DATA_DIR / "schema.sql"),
        "migration_sha256": file_digest(build.DATA_DIR / "migration_m3_1_replace_chunks.sql"),
    }
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError("Target review does not match this cohort/schema/model/RPC")
    if not re.fullmatch(r"https://[a-z0-9]{20}\.supabase\.co", receipt.get("supabase_url", "")):
        raise ValueError("An exact Supabase project URL is required")
    if not receipt.get("reviewed_by") or not receipt.get("reviewed_at"):
        raise ValueError("Independent target review attribution is required")
    for check in ("rpc_signature", "rls_and_grants", "model_dimensions_version", "exclusive_cohort_writer"):
        if receipt.get("checks", {}).get(check) is not True:
            raise ValueError("Target review checks are incomplete")
    window_end = datetime.fromisoformat(receipt.get("exclusive_writer_until", "").replace("Z", "+00:00"))
    if window_end.tzinfo is None:
        raise ValueError("Exclusive writer window must specify a timezone")
    if type(receipt.get("existing_count")) is not int or receipt["existing_count"] < 0:
        raise ValueError("Target review must include an exact prior cohort count")
    if not re.fullmatch(r"[0-9a-f]{64}", receipt.get("existing_rows_sha256", "")):
        raise ValueError("Target review must include the normalised prior cohort hash")
    evidence = receipt.get("evidence_files")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("Target review evidence is required")
    for entry in evidence:
        if file_digest(path.parent / entry["path"]) != entry["sha256"]:
            raise ValueError("Target review evidence changed")
    allowed = set(expected) | {
        "supabase_url", "reviewed_by", "reviewed_at", "existing_count",
        "existing_rows_sha256", "checks", "evidence_files", "exclusive_writer_until",
    }
    return {key: receipt[key] for key in allowed}


def make_plan(manifest_path: Path, video_id: str, vtt: Path, caption_path: Path,
              target_path: Path, work_dir: Path, roster_path: Path = build.ROSTER_PATH) -> tuple[dict, dict, list[dict]]:
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise ValueError("Invalid video ID")
    manifest = load_json(manifest_path)
    sources = [row for row in manifest.get("meetings", []) if row.get("video_id") == video_id]
    if not sources or len({row["primegov_id"] for row in sources}) != len(sources):
        raise ValueError("Missing or duplicate exact PrimeGov identities")
    sources.sort(key=lambda row: (row.get("date_time") or "", int(row["primegov_id"])))
    existing_artifact = build.DATA_DIR / f"{video_id}.json"
    if existing_artifact.exists():
        previous = load_json(existing_artifact)
        known_ids = {row["primegov_id"] for row in previous.get("source_meetings", [])}
        known_ids.add(previous["primegov_id"])
        if not known_ids.issubset({row["primegov_id"] for row in sources}):
            raise ValueError("Manifest would drop a previously known PrimeGov identity")
    item = VideoWorkItem(video_id, tuple(sources), "caption_preflighted")
    meeting = canonical_meeting_for_work_item(item)
    caption = load_json(caption_path)
    payload = inspect_payload(vtt)
    if (caption.get("video_id") != video_id or caption.get("caption_language") != build.CART_LANG_CODE
            or caption.get("track_kind") != "manual" or caption.get("payload_status") != "ok"
            or caption.get("payload_sha256") != payload["sha256"] or not payload["usable"]
            or not caption.get("approved_by") or not caption.get("approved_at")):
        raise ValueError("Usable, hash-bound, reviewed manual CART evidence is required")
    receipt = verify_receipt(target_path, video_id)
    utterances = build.stitch_utterances(build.dedupe_rolling(build.parse_vtt(vtt)))
    first = next(index for index, utterance in enumerate(utterances) if utterance.speaker is not None)
    utterances = utterances[first:]
    resolver = build.SpeakerResolver(roster_path)
    transcript = build.build_transcript_json(meeting, utterances, resolver)
    transcript.pop("ingested_at")  # Keep the approval hash stable between runs.
    coverage = speaker_coverage_report(transcript["utterances"], resolver)
    reviewed_labels = caption.get("reviewed_unknown_labels", [])
    require_reviewed_coverage(coverage, reviewed_unknown_labels=reviewed_labels)
    rows = []
    for chunk in build.chunk_turns(utterances):
        row = asdict(chunk)
        row.update(asdict(resolver.resolve(chunk.source_label)))
        row.update(video_id=video_id, meeting_date=transcript["meeting_date"],
                   turn_speaker_raw=chunk.source_label, embedding_model=build.EMBED_MODEL,
                   embedding_version=build.EMBED_VERSION)
        rows.append(row)
    if not rows:
        raise ValueError("Empty cohorts cannot replace an indexed recording")
    batches = math.ceil(len(rows) / build.EMBED_BATCH_SIZE)
    plan = {
        "schema_version": "verified-transcript-plan-v1", "video_id": video_id,
        "work_dir": str(work_dir.resolve()),
        "target": receipt, "source_meetings": transcript["source_meetings"],
        "inputs": {"manifest": file_digest(manifest_path), "captions": payload["sha256"],
                   "caption_review": file_digest(caption_path), "target_review": file_digest(target_path),
                   "roster": file_digest(roster_path)},
        "code": {name: file_digest(Path(__file__).parent / name) for name in SOURCE_FILES},
        "rows_sha256": digest(rows), "artifact_sha256": digest(transcript),
        "coverage": coverage, "reviewed_unknown_labels": reviewed_labels,
        "row_count": len(rows), "parent_turn_count": sum(row["sub_chunk_idx"] == 0 for row in rows),
        "maximum_embedding_attempts": batches * 5, "maximum_replacement_attempts": 1,
        "maximum_input_bytes_across_embedding_attempts": sum(len(row["text"].encode()) for row in rows) * 5,
        "embedding_policy": "Existing embed_batch: 100 texts/batch, 60s socket timeout, up to 5 attempts; backoff 1+2+4+8s maximum.",
        "overall_deadline_seconds": batches * 315 + 120,
        "canonical_publication": "staged only; source_meetings is not a database column",
    }
    return plan, transcript, rows


@contextmanager
def deadline(seconds: int):
    """Hard wall-clock bound on the supported local Unix main-thread runner."""
    previous = signal.getsignal(signal.SIGALRM)
    def expired(_signal, _frame):
        raise TimeoutError("Approved cohort deadline exceeded")
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


@contextmanager
def cohort_lock(path: Path):
    with path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def execute(plan: dict, transcript: dict, rows: list[dict], approved_hash: str,
            work_dir: Path, *, embedder, replacement_rpc, read_rows) -> dict:
    plan_hash = digest(plan)
    if str(work_dir.resolve()) != plan.get("work_dir"):
        raise ValueError("Execution directory differs from the approved plan")
    if approved_hash != plan_hash or digest(rows) != plan["rows_sha256"] or digest(transcript) != plan["artifact_sha256"]:
        raise ValueError("Approval hash or staged inputs do not match")
    exclusive_until = datetime.fromisoformat(plan["target"]["exclusive_writer_until"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) + timedelta(seconds=plan["overall_deadline_seconds"]) > exclusive_until:
        raise ValueError("Reviewed exclusive writer window does not cover the execution deadline")
    work_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    checkpoint_path = work_dir / f"{plan_hash}.checkpoint.json"
    with cohort_lock(work_dir / f"{plan_hash}.lock"), deadline(plan["overall_deadline_seconds"]):
        current = normalise_rows(read_rows())
        if checkpoint_path.exists():
            checkpoint = load_json(checkpoint_path)
            if checkpoint.get("plan_sha256") != plan_hash:
                raise ValueError("Checkpoint belongs to another plan")
            if "rows" not in checkpoint:
                raise ValueError("Earlier embedding attempt needs spending reconciliation and a newly approved plan")
            materialized = checkpoint["rows"]
            metadata = [{key: value for key, value in row.items() if key != "embedding"} for row in materialized]
            if digest(metadata) != plan["rows_sha256"] or digest(materialized) != checkpoint.get("materialized_sha256"):
                raise ValueError("Checkpoint content does not match the approved plan")
            if digest(current) == digest(normalise_rows(materialized)):
                atomic_write_json(work_dir / f"{plan['video_id']}.json", {**transcript, "ingested_at": utc_now()})
                checkpoint["state"] = "verified"
                atomic_write_json(checkpoint_path, checkpoint)
                return {"state": "verified", "row_count": len(current), "embedding_calls": 0, "replacement_calls": 0}
            if checkpoint.get("state") != "embedded":
                raise ValueError("Earlier replacement attempt needs reconciliation and a newly approved plan")
        else:
            materialized = None
        if len(current) != plan["target"]["existing_count"] or digest(current) != plan["target"]["existing_rows_sha256"]:
            raise ValueError("Live cohort changed since independent target review")
        atomic_write_json(work_dir / f"{plan_hash}.before.json", {"rows": current})
        captured = []
        def save_embedded(prepared):
            normalise_rows(prepared)
            captured.extend(prepared)
            return len(prepared)
        if materialized is None:
            atomic_write_json(checkpoint_path, {"plan_sha256": plan_hash, "state": "embedding_pending"})
            embed_and_index(rows, embedder=embedder, indexer=save_embedded,
                            coverage_report=plan["coverage"], reviewed_unknown_labels=plan["reviewed_unknown_labels"])
            materialized = captured
        checkpoint = {"plan_sha256": plan_hash, "state": "embedded", "rows": materialized,
                      "materialized_sha256": digest(materialized)}
        atomic_write_json(checkpoint_path, checkpoint)
        artifact = {**transcript, "ingested_at": utc_now()}
        atomic_write_json(work_dir / f"{plan['video_id']}.json", artifact)
        if digest(normalise_rows(read_rows())) != digest(current):
            raise ValueError("Live cohort changed during embedding; replacement was not attempted")
        checkpoint["state"] = "replacement_pending"
        atomic_write_json(checkpoint_path, checkpoint)
        count = TransactionalReplacementIndexer(replacement_rpc)(materialized)
        actual = normalise_rows(read_rows())
        if digest(actual) != digest(normalise_rows(materialized)):
            raise ValueError("Post-replacement keys/count/content verification failed")
        checkpoint["state"] = "verified"
        atomic_write_json(checkpoint_path, checkpoint)
        return {"state": "verified", "row_count": count, "replacement_calls": 1}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise ValueError("Redirects are forbidden for credentialed database requests")


def online_adapters(plan: dict):
    target = plan["target"]["supabase_url"]
    if os.environ.get("SUPABASE_URL") != target:
        raise ValueError("SUPABASE_URL differs from the reviewed target")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    api_key = os.environ["PERPLEXITY_API_KEY"]
    opener = build_opener(NoRedirect())
    def request(path, body=None):
        data = None if body is None else json.dumps(body, allow_nan=False).encode()
        headers = {"apikey": service_key, "Content-Type": "application/json"}
        if not service_key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {service_key}"
        req = Request(target + "/rest/v1/" + path, data=data, headers=headers)
        with opener.open(req, timeout=30) as response:
            return json.load(response)
    def read_rows():
        maximum = max(plan["target"]["existing_count"], plan["row_count"]) + 1
        rows = []
        while len(rows) < maximum:
            query = urlencode({"select": ",".join(FIELDS), "video_id": "eq." + plan["video_id"],
                               "embedding_model": "eq." + build.EMBED_MODEL, "order": "chunk_idx",
                               "limit": min(1000, maximum - len(rows)), "offset": len(rows)})
            batch = request("transcript_chunks?" + query)
            if not isinstance(batch, list):
                raise ValueError("Invalid cohort read response")
            rows.extend(batch)
            if not batch:
                return rows
        raise ValueError("Cohort exceeds the reviewed row bound")
    def replacement_rpc(*, video_id, embedding_model, rows):
        response = request("rpc/replace_transcript_chunks", {
            "p_video_id": video_id, "p_embedding_model": embedding_model, "p_rows": rows,
        })
        if not isinstance(response, list) or len(response) != 1:
            raise ValueError("Invalid replacement response")
        return response[0]
    def embedder(texts):
        vectors = []
        for offset in range(0, len(texts), build.EMBED_BATCH_SIZE):
            vectors.extend(build.embed_batch(texts[offset:offset + build.EMBED_BATCH_SIZE], api_key))
        return vectors
    return embedder, replacement_rpc, read_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ("manifest", "vtt", "caption-evidence", "target-verification", "work-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approved-plan-sha256")
    args = parser.parse_args()
    try:
        plan, transcript, rows = make_plan(args.manifest, args.video_id, args.vtt, args.caption_evidence, args.target_verification, args.work_dir)
        args.work_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic_write_json(args.work_dir / "plan.json", plan)
        print(json.dumps({"plan_sha256": digest(plan), "rows": plan["row_count"],
                          "maximum_embedding_attempts": plan["maximum_embedding_attempts"]}))
        if args.execute:
            if args.approved_plan_sha256 != digest(plan):
                raise ValueError("An exact approved plan hash is required before online setup")
            embedder, replacement, reader = online_adapters(plan)
            result = execute(plan, transcript, rows, args.approved_plan_sha256, args.work_dir,
                             embedder=embedder, replacement_rpc=replacement, read_rows=reader)
            print(json.dumps(result))
        return 0
    except (ValueError, KeyError, OSError, RuntimeError) as error:
        # Never print provider exception bodies, URLs or credentials.
        print(f"Verified ingest stopped ({type(error).__name__}); inspect the local plan/checkpoint before retrying.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
