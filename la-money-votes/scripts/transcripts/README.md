# `scripts/transcripts/` — transcript ingestion

Ingests LA City Council meeting transcripts from the City Clerk's public
YouTube channel (CART captions, one file per meeting), resolves speakers
via `data/transcripts/roster.json`, chunks each transcript, embeds the
chunks with Perplexity's `pplx-embed-v1-0.6b` model, and upserts them
into a Supabase Postgres table (`transcript_chunks`) that the
`/api/search-transcripts` Vercel function queries at request time.

This runs **locally on the Mac mini**, not in GitHub Actions. See the
"Why not CI?" note at the bottom.

Frontend and API integration:

- `data/transcripts/roster.json` — human-curated speaker table.
- `data/transcripts/{video_id}.json` — per-meeting output, canonical.
- `data/transcripts/schema.sql` — Supabase table + RPC (apply once).
- `api/search-transcripts.js` — Vercel function that reads Supabase.
- `js/transcript-search.js` — per-official panel on `official.html`.

Full schema reference: [`../../CONTRACT.md`](../../CONTRACT.md#new-datatranscripts-transcript-search-feature-additive).

## One-time setup

### 1. Python virtualenv

`scripts/transcripts/` intentionally does **not** share Python
dependencies with `scripts/pipeline/`, which is stdlib-only. It has its
own `requirements-transcripts.txt`.

From the repo root:

```bash
cd la-money-votes
python3 -m venv .venv-transcripts
source .venv-transcripts/bin/activate
pip install --upgrade pip
pip install -r scripts/transcripts/requirements-transcripts.txt
```

Only third-party dep is `supabase>=2.5.0,<3.0.0`. Everything else
(PrimeGov fetch, VTT parsing, chunking, HTTP calls to Perplexity's
embedding API) is stdlib.

### 2. `yt-dlp` on `$PATH`

The script shells out to `yt-dlp` to download CART VTT captions.
Homebrew works:

```bash
brew install yt-dlp
which yt-dlp    # should print /usr/local/bin/yt-dlp on Intel Mac mini
```

If `yt-dlp` lives somewhere non-standard, set `YT_DLP_PATH` to the
absolute path.

### 3. Chrome cookies

`yt-dlp` invokes `--cookies-from-browser chrome` to establish the
"logged-in human watching YouTube" signal that keeps CART captions
downloadable without a rate-limit challenge. Just make sure Chrome is
installed and has been used to visit `youtube.com` at least once on
this user account; you don't need to log in.

If you use a different browser, override the default:

```bash
export YT_DLP_COOKIES_BROWSER=firefox   # or safari, edge, etc.
```

### 4. Environment variables

Required for a real (embedding) run:

| Variable                     | Where it comes from                                                                        |
| ---------------------------- | ------------------------------------------------------------------------------------------ |
| `PERPLEXITY_API_KEY`         | Perplexity account. Same key `api/ask-official.js` uses in Vercel.                          |
| `SUPABASE_URL`               | Supabase project settings → API → Project URL. `https://<project-ref>.supabase.co`.       |
| `SUPABASE_SERVICE_ROLE_KEY`  | Supabase project settings → API → `service_role` key. **Never** commit or share.          |

Optional:

| Variable                     | Default              | Purpose                                                    |
| ---------------------------- | -------------------- | ---------------------------------------------------------- |
| `YT_DLP_PATH`                | `yt-dlp` on `$PATH`  | Absolute path to yt-dlp if not on the shell's `$PATH`.     |
| `YT_DLP_COOKIES_BROWSER`     | `chrome`             | Which browser's cookie jar to read.                        |
| `VTT_CACHE_DIR`              | `.cache/youtube/`    | Where raw downloaded VTTs live (never committed).          |

Recommended: keep these in a `.envrc` (direnv) or a per-shell `~/.zshenv`
snippet, never in the repo. The repo's root `.gitignore` already excludes
`.env*` files, but the safest posture is not to write them into the tree
at all.

### 5. Supabase schema

One-time only, when the Supabase project is first created OR when
`data/transcripts/schema.sql` changes shape (a schema change is a
CONTRACT event — do not sneak one in).

Preferred: paste `data/transcripts/schema.sql` into the Supabase SQL
editor and run it. It is idempotent (`create ... if not exists`,
`create or replace function ...`).

Alternative, if using the Supabase MCP connector from Perplexity
Computer: apply the file via the MCP's `execute_sql` tool. The service
role key is not needed for this — the MCP handles auth on its own.

## Running the pipeline

### Dry run (no Supabase, no embedding, no cost)

Fast smoke test — fetches the 10 most recent City Council meetings,
downloads each VTT, resolves speakers, chunks, and writes
`data/transcripts/{video_id}.json`, but skips embedding and Supabase
upsert entirely. Useful for verifying speaker coverage on a fresh
meeting before spending API credits.

```bash
python3 scripts/transcripts/build_transcripts.py --no-embed
```

Or one specific video (bypasses PrimeGov entirely — handy when the API
is slow):

```bash
python3 scripts/transcripts/build_transcripts.py --video-id UkdZRHDB9qs --no-embed
```

After a dry run, check the coverage summary logged for each meeting.
Anything with a nonzero `unresolved` count means the CART operator used
a `cart_label` that `roster.json` doesn't have yet — fix the roster
before doing a real run, or those utterances end up as `Unknown` in the
committed JSON.

### Real run (embeds + upserts to Supabase)

```bash
python3 scripts/transcripts/build_transcripts.py
```

Cost: `pplx-embed-v1-0.6b` at ~$0.004/1M tokens; a 10-meeting corpus
re-embedded from scratch runs about $0.001. Idempotent — re-running
against unchanged transcripts is a no-op (the `(video_id, chunk_idx,
embedding_model)` unique constraint deduplicates on the Supabase side).

## CLI flags

| Flag           | Default          | Purpose                                                              |
| -------------- | ---------------- | -------------------------------------------------------------------- |
| `--top N`      | `10`             | How many recent City Council meetings to consider from PrimeGov.     |
| `--video-id X` | (none)           | Skip PrimeGov entirely; process one specific YouTube video ID.       |
| `--no-embed`   | (off)            | Skip embedding + Supabase upsert. Writes JSON only.                  |
| `--cache-dir P`| `.cache/youtube` | Where to put downloaded raw VTTs (never committed).                  |
| `--log-level L`| `INFO`           | Standard Python logging level.                                       |

## Common failure modes

### "No English CART captions on this video"

Fresh livestreams don't have CART captions transcoded for anywhere from
a few minutes to a few hours after the meeting ends. The script logs
this and moves on — the meeting will be picked up on the next
scheduled run (which is: the next time you run this manually). The
committed JSON is the retry marker: as long as there's no
`data/transcripts/{video_id}.json` for a given video, the pipeline will
retry it.

### "yt-dlp needs Chrome cookies"

If the download fails with a "sign in to confirm" error, quit Chrome
completely and rerun. `yt-dlp --cookies-from-browser chrome` needs to
copy the cookie file, and Chrome holds an exclusive lock while running.

### "Supabase 401 / 403"

Almost always a wrong or missing `SUPABASE_SERVICE_ROLE_KEY`. The
service role key starts with `eyJ` (JWT) and is 200+ characters. The
`anon` key won't work here — writes to `transcript_chunks` need the
service role. The Vercel search function uses the `anon` key instead,
because it only reads via the `search_transcripts` RPC.

### "The CART operator changed my labels"

Symptom: coverage summary shows a big `unresolved` count, or a familiar
councilmember suddenly resolves to `Unknown`. Look at
`data/transcripts/{video_id}.json` — the raw `source_label` string is
recorded verbatim next to every utterance. If the CART operator started
writing `"CM. Jurado"` instead of `"Y. Jurado"`, that's a `roster.json`
edit, not a code change. See CONTRACT.md's "cart_label" note.

## Why not run this in CI?

- **Cookie surface.** `yt-dlp` needs a real browser cookie jar to fetch
  CART reliably. Provisioning one in GitHub Actions runners is
  brittle — the moment YouTube tightens something, the workflow breaks.
- **Cost visibility.** The embedding job spends real money against a
  Perplexity API key. Running it locally keeps that spend visible and
  attributable to a human keystroke, not a scheduled job that could
  loop on failure.
- **Cadence.** City Council meets weekly; a manual "run this after the
  meeting is captioned" workflow is the right cadence, not a cron.

The `refresh-data.yml` workflow (which pulls funding data from the LA
Ethics Commission's Socrata API) has none of these constraints; the two
data sources are deliberately kept on different operational planes.
