# M3.1 caption blocker — diagnostic runbook

## What is blocked

The August 2026 historical inspection reported three videos declaring a manual
English CC1/CART track with an HTTP 200, zero-byte payload. A new run must
re-establish the outcome. The historical targets were:

| video | role |
|---|---|
| `2Wm-11hPNns` | the missing 10th regular session, 2026-08-18 |
| `1GWlqG-UJHE` | representative standing-committee meeting |
| `MBjio010l60` | **control** — previously ingested successfully |

The control is what makes this interesting. Its captions are already in the
corpus, so the asset is not simply absent. Three independent per-video gaps
would not explain a video that demonstrably downloaded before.

## Competing explanations

1. **yt-dlp regression** — the installed version no longer negotiates the
   manual track. Another version behaves differently.
2. **Player-client rotation** — YouTube serves caption tracks to some
   innertube clients and not others. Some `player_client` still returns bytes.
3. **Auth/cookie state** — the request is being downgraded because the
   signed-in session is not attached.
4. **Genuine upstream removal** — the asset really is empty everywhere.

Only (4) would reopen the ASR question, and that remains the user's decision,
not the script's.

## Running it

Run on the machine with the authenticated yt-dlp session — not in CI, and not
in the remote container, which has no yt-dlp, no cookie jar, and no cache.

```bash
cd la-money-votes
python3 scripts/transcripts/diagnose_captions.py \
    --out /tmp/captions_diagnosis.json \
    --cookies-from-browser chrome
```

It probes all three videos across six player clients, listing subtitles and
then attempting a real download, and classifies each attempt as `ok`,
`zero_byte`, `empty_with_error`, `fetch_failed`, or `not_offered`.

The `not_offered` / `zero_byte` split is the point: a declared-but-empty track
must never be recorded as "this meeting has no captions."

Inspect the bounded report before a follow-up. Installation changes and browser
cookie access require the owner's current approval. Use a pinned workspace
virtual environment, and do not run a global package upgrade. A different
version, additional client, or extra video requires its own approved scope.
The current diagnostic supports repeated `--only-video` arguments and one
`--client web` to replace the broad historical default matrix. See the current
[runbook](README.md#caption-feasibility) for the exact three-video examples.

## Reading the result

- **Any `ok` row** — captions are still retrievable. Pin that `player_client`
  in the ingest path and M3.1 unblocks with no ASR exception.
- **Control fails on every client** — suspect a yt-dlp or auth regression
  before blaming upstream; confirm the cookie jar is really signed in.
- **Everything zero-byte across versions and clients** — record each meeting
  as blocked with a source-specific reason and bring the ASR decision back to
  the user with this report attached.

## Safety

- No credentials are written to the report: the cookie-source presence is recorded as a
  boolean, raw stderr is excluded, and payload SHA-256 values are recorded.
  No signed caption URL is stored or represented as a known URL hash.
- Each probe uses an isolated temporary directory. Only validated payloads may
  be retained with explicit `--retain-usable-dir` in an approved ignored cache.
  Raw VTTs are never committed.
- The script only measures. It does not ingest, embed, write to Supabase, or
  select an ASR track.
