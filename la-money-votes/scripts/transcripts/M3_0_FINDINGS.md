# Transcript RAG — M3.0 Discovery Findings

**Discovery time:** 2026-08-19
**PrimeGov window:** Previous 90 days, 2026-05-21 through 2026-08-18
**Mutation boundary:** Metadata reads and local artifact generation only. No
captions were downloaded, no embeddings were requested, no Supabase writes
were made, and no commit, merge, or deployment occurred.

## Corpus cardinality

PrimeGov returned 211 rows in the 90-day window. Applying the locked M3 policy
produced:

- 122 in-scope PrimeGov meeting rows.
- 69 unique YouTube video IDs.
- 9 unique videos already published in the M1/M2 corpus.
- 60 new unique video candidates for M3.1 caption preflight.
- 52 in-scope rows with no YouTube video URL.
- 89 excluded rows:
  - 70 SAP duplicates.
  - 6 ad hoc body rows.
  - 5 advisory body rows.
  - 5 cancelled rows.
  - 3 commission rows.

The in-scope rows break down as:

| Meeting type | Rows | With YouTube video | New video candidates |
|---|---:|---:|---:|
| Regular City Council | 38 | 23 | 14 |
| Recessed City Council | 1 | 1 | 1 |
| Special City Council | 1 | 1 | 0 |
| Standing committee | 77 | 40 | 40 |
| Special standing committee | 5 | 5 | 5 |

Counts are meeting-row counts except where explicitly labeled unique videos.
One video is shared by two PrimeGov meeting rows.

## Missing member of the newest 10 regular sessions

The newest regular session not present in the canonical corpus is:

| Field | Value |
|---|---|
| Meeting date | 2026-08-18 |
| PrimeGov ID | 18197 |
| YouTube video ID | `2Wm-11hPNns` |
| PrimeGov title | `City Council Meeting` |
| Video title observed on YouTube | `Regular City Council - 8/18/26` |

This is not an identity-resolution failure: PrimeGov supplies an exact YouTube
video ID. M3.1 authenticated inspection found both an ASR track and a manual
English CC1 track in player metadata, but the manual track returned HTTP 200
with a zero-byte body. The user chose to skip this meeting for now rather than
admit an ASR-only exception into the official-attribution corpus. The manifest
records `caption_status = cart_metadata_present_payload_empty`,
`missing_reason = manual_cart_payload_empty`, and `asr_approved = false`.

## PrimeGov video collision

PrimeGov IDs `17801` (`City Council Meeting`) and `18451`
(`Special City Council Meeting #2`) both point to YouTube video
`welTRe5_RH4` on 2026-06-30.

The M2 backfill's video-ID index kept the later row, so the canonical artifact
currently carries PrimeGov ID `18451` and the special-meeting title. The M3
manifest preserves both meeting rows and reports the collision rather than
collapsing it silently.

M3.1 must:

1. Ingest the shared video at most once.
2. Preserve both PrimeGov meeting identities in provenance metadata.
3. Avoid changing the unique chunk key solely to accommodate duplicate
   meeting rows.
4. Decide which meeting label the UI displays when a video covers both records.

## Standing-committee taxonomy

Sixteen PrimeGov body IDs are in scope: City Council plus 15 standing
committees observed in the window. Special meetings of those bodies are
included. SAP rows, cancelled meetings, ad hoc committees, the Budget and
Finance Advisory Committee, and the Los Angeles City Health Commission are
excluded.

The allowlist is versioned in `committee_taxonomy.json`. It is intentionally
explicit rather than based only on title suffixes, because PrimeGov titles
contain whitespace differences, shortened names, and special-meeting prefixes.

## Historical decision reconciliation

### Speaker resolution

The checked-in M1/M2 pipeline is deterministic:

- `vtt_flatten.py` extracts CART speaker labels.
- `speaker_resolver.py` maps labels to roles and councilmembers.
- Existing canonical artifacts use `exact-role`, `exact-councilmember`, and
  three documented fuzzy corrections.
- No Haiku call exists in the active transcript build path.

M3 therefore keeps deterministic CART resolution as canonical. The M3.4
hand-labeled precision gate evaluates this resolver; it does not introduce an
LLM fallback.

### Embedding model

The ingest script, search API, schema, and evaluation runner consistently pin
`pplx-embed-v1-0.6b`, dimension 1024, embedding version 1. M3 keeps that model
and uses batch requests plus query-embedding cache reuse.

## M3.1 risks and gates

- Caption availability initially required authenticated preflight for all 60
  new unique video candidates. Two were inspected: `2Wm-11hPNns` is blocked by
  user decision and `1GWlqG-UJHE` remains retryable after its manual CC1 payload
  also returned zero bytes. The other 58 remain uninspected.
- Committee speaker labels may not match the Council-only roster assumptions.
- Fifty-two in-scope meeting rows currently have no PrimeGov YouTube URL.
- The shared-video collision needs a provenance representation before ingest.
- The 60-video expansion is materially larger than M1/M2 and must checkpoint
  the manifest at every pipeline boundary.

The Mac caption cache contains only the nine M1/M2 CART VTT files. A known-good
indexed control (`MBjio010l60`) now also returns a zero-byte manual CC1 payload,
which indicates a systemic current-source problem rather than proof that an
individual meeting never had captions.

M3.1 should not begin until the user approves caption metadata inspection,
caption download for approved tracks, canonical JSON generation, batched
embedding calls, and Supabase upserts.
