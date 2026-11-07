# CONTRACT.md

Frozen schemas for `la-money-votes`. Committed once, never edited. If a schema
needs to change, that's a team conversation, not a solo edit.

## `data/officials.json`

Index of the 3 officials. Person 4 writes once, frozen after minute-0 huddle.

```json
[
  { "id": "mayor-bass", "name": "Karen Bass", "office": "Mayor" },
  { "id": "cd14-official", "name": "REPLACE_ME", "office": "Council District 14" },
  { "id": "cd11-official", "name": "REPLACE_ME", "office": "Council District 11" }
]
```

IDs are lowercase-hyphenated and frozen after commit.

## `data/officials/<id>/funding.json`

Owned by Person 1 (`scripts/build_funding.py` generates it).

```json
{
  "official": {
    "id": "mayor-bass",
    "name": "Karen Bass",
    "office": "Mayor",
    "reelection": { "active": true, "election_date": "2026-06-02", "committee": "Karen Bass for Mayor 2026" }
  },
  "donors": [
    { "name": "Sample PAC A", "type": "pac", "total": 5400, "employer": null,
      "contributions": [{ "date": "2025-03-01", "amount": 5400 }] },
    { "name": "Jane Sample", "type": "individual", "total": 1600, "employer": "Sample Corp",
      "contributions": [{ "date": "2025-02-10", "amount": 800 }, { "date": "2025-04-01", "amount": 800 }] },
    { "name": "Sample Realty LLC", "type": "business", "total": 800, "employer": null,
      "contributions": [{ "date": "2025-01-15", "amount": 800 }] }
  ]
}
```

## `data/officials/<id>/record.json`

Owned by Person 2 (`scripts/build_record.py` generates it).

```json
{
  "official_id": "mayor-bass",
  "items": [
    { "council_file": "23-0001", "title": "Sample Housing Ordinance", "role": "proposed",
      "date": "2023-05-01", "outcome": "passed", "term": "current" },
    { "council_file": "21-0042", "title": "Sample Transit Motion", "role": "voted_yes",
      "date": "2021-09-12", "outcome": "passed", "term": "previous" },
    { "council_file": "24-0100", "title": "Sample Budget Amendment", "role": "seconded",
      "date": "2024-02-20", "outcome": "pending", "term": "current" }
  ]
}
```

## Additions

The blocks above are the frozen originals and still describe valid files. The
fields below were added afterwards. All of them are **optional and additive** —
nothing was removed or retyped, and a consumer written against the original
shapes keeps working. Anything reading the new fields must tolerate their
absence.

### `funding.json` → `official.reelection.result`

`"won" | "lost" | "runoff" | null`. Absent/null while the election is still
ahead. The contributions export records who gave, never who won, so this is
hand-curated in `build_funding.py`'s `ELECTION_RESULTS` rather than derived.

`active` means **the campaign is still ahead of its election**, so it is checked
against `election_date`, not just the year in the committee name. It is still a
build-time snapshot: it was true the day a page was built and false the day
after the election, with no rebuild in between. Consumers that can go stale must
compare `election_date` against the current date themselves rather than trusting
`active` — `js/app.js` does this when choosing the banner's tense.

### `funding.json` → `source`

Where the donor numbers came from. Contributions are published in bulk with no
per-donor permalink, so this is a dataset-level citation, rendered once under
the donor table.

```json
{
  "name": "Los Angeles City Ethics Commission — City Campaign Contributions (and Misc. Increases to Cash)",
  "url": "https://ethics.lacity.org/",
  "committees": ["Traci Park for City Council 2026"]
}
```

### `record.json` → `source` and `items[].source_url`

`source` is the same shape minus `committees`, shown once under the record
table. `source_url` is the primary source for one row, or `null` when no stable
deep link has been verified — council files resolve to their CFMS record page,
mayoral directives currently do not and render as plain text.

```json
{
  "official_id": "cd11-official",
  "source": { "name": "LA City Clerk — Council File Management System",
              "url": "https://cityclerk.lacity.org/lacityclerkconnect/" },
  "items": [
    { "council_file": "23-0839", "title": "…", "role": "proposed",
      "date": "2023-08-11", "outcome": "passed", "term": "previous",
      "source_url": "https://cityclerk.lacity.org/lacityclerkconnect/index.cfm?fa=ccfi.viewrecord&cfnumber=23-0839" }
  ]
}
```

Only verified URLs belong in either field. On a site whose whole claim is that
you can check the numbers yourself, a link that goes somewhere approximate is
worse than no link.

### `funding.json` → `donors[].contributions[].source_url`

`source_url` is the primary-source link for one itemized contribution, or
absent/`null` when no stable filing link could be resolved. The Ethics
Commission does not publish a per-transaction permalink (see `source` above),
but it does publish every campaign statement (Form CA460) it received, each
at its own stable document URL, in a second bulk dataset: "City Campaign
Statements Filed" (`data.lacity.org` resource `br3a-db9a`, download:
`https://data.lacity.org/api/v3/views/br3a-db9a/query.json?accessType=DOWNLOAD`,
landing page `https://data.lacity.org/d/br3a-db9a`).

`build_funding.py` joins each contribution row to the exact statement that
disclosed it — on `Committee ID` + `Period Beg Date` + `Period End Date`
against that dataset's `cmt_id` + `period_from_date` + `period_to_date` — and,
on a match, takes that filing's `stmt_link` as the contribution's
`source_url`. This is a link to the actual regulatory filing (a scanned CA460
document) that reported the contribution, not a link to the single line item
inside it — the Commission does not offer anything more granular — but it is
a verified, non-guessed primary-source document, and it is exact about which
filing to check. The join is on record identifiers already present in both
official datasets, never on name-matching or inference.

Because the join needs a second local input file
(`data/raw/statements_filed.csv`, same as `contributions.csv`: downloaded
locally, never committed) that a given local checkout may not have, this
field can legitimately be absent even for a contribution that in principle
has a matching filing. Absence must always be read as "not resolved in this
build," never as "does not exist."

```json
{
  "name": "Sample PAC A", "type": "pac", "total": 5400, "employer": null,
  "contributions": [
    { "date": "2025-03-01", "amount": 5400,
      "source_url": "https://ethics.lacity.org/view/?document_id=133955" }
  ]
}
```

### `funding.json` / `record.json` → `source.retrieved_at` and `source.methodology_version`

Two more optional/additive fields on the existing `source` block (both
`funding.json`'s top-level `source` and `record.json`'s top-level `source`):

```json
{
  "name": "Los Angeles City Ethics Commission — City Campaign Contributions (and Misc. Increases to Cash)",
  "url": "https://ethics.lacity.org/",
  "committees": ["Traci Park for City Council 2026"],
  "retrieved_at": "2026-08-08",
  "methodology_version": "1.0"
}
```

- `retrieved_at` — the date (`YYYY-MM-DD`) this build actually ran, i.e. when
  the underlying source was read. Distinct from any date inside the source
  data itself (a filing date, a contribution date, a meeting date).
  **Not a freshness signal.** Despite its name, this is stamped with the
  build's local date on every successful build — including CSV builds,
  cache-backed builds and curated `record.json` builds — so it does not
  prove when the underlying source was last retrieved or reviewed. Use
  `freshness.json` (below) instead. Correcting `retrieved_at` itself is a
  separate future task; its behavior is unchanged by freshness v2.
- `methodology_version` — the pipeline's own methodology version string (see
  `scripts/pipeline/provenance.py`'s `METHODOLOGY_VERSION`), bumped whenever
  a change to *how* a field is computed (not just its committed value) could
  make a reader's prior understanding of a number wrong — e.g. changing which
  `Contribution Type` values count as a "donor," or changing how re-election
  status is derived. Consumers can use this to detect "the shape of the
  computation changed" independent of "the underlying civic data changed."

### `funding.json` → `donors[].contributions[].provenance` and `record.json` → `items[].provenance`

Every individual factual record (one itemized contribution; one record item)
now additionally carries its own `provenance` block, on top of (not instead
of) the dataset-level `source` block above. The dataset-level `source` says
"this whole file came from the LA Ethics Commission, fetched on this date";
`provenance` says the same thing again at the level of one row, plus
whatever that specific row can add — reporting period, meeting date, and a
stable record/filing ID when one exists — so a single contribution or vote
can be traced without having to fall back to the file-level citation.

```json
{
  "source_name": "Los Angeles City Ethics Commission — City Campaign Contributions (and Misc. Increases to Cash)",
  "source_url": "https://ethics.lacity.org/view/?document_id=133955",
  "retrieved_at": "2026-08-08",
  "reporting_period": { "from": "2026-01-01", "to": "2026-06-30" },
  "meeting_date": null,
  "record_id": "9999001",
  "methodology_version": "1.0"
}
```

`reporting_period` is populated for funding contributions (the campaign
statement's filing period) and is `null` for record items; `meeting_date` is
populated for record items (the council-file action or executive-directive
date) and is `null` for contributions — a given record only ever fills in
the one that applies to its source type. `record_id` is the Committee ID for
a contribution or the council-file / ED / EO number for a record item, or
`null` when no stable identifier is available. See
`scripts/pipeline/provenance.py:make_provenance()` — every builder calls this
same function, so the shape is identical across both files.

### New: `data/schemas/*.schema.json`

Each of `officials.json`, `sources_registry.json`, `funding.json`,
`record.json`, `build_report.json`, `freshness.json`, and the shared
`provenance` block now has a companion JSON Schema file documenting its
shape precisely (types, required fields, enums). These are validated against
by `scripts/pipeline/validation.py:validate_schema()` — a small hand-rolled
subset of JSON Schema (`type`, `required`, `properties`, `items`, `enum`,
`additionalProperties`), not a general implementation and not a third-party
dependency; see that module's docstring for exactly what is and isn't
supported, and extend it there (not with a new dependency) if a schema ever
needs a keyword it doesn't yet handle.

### New: `data/sources/registry.json` and `data/sources/records/<official-id>.json`

Builder configuration (which Ethics Commission committee names map to which
official, that official's known election result, and which curated-record
fixture file to read) used to be hard-coded directly in `build_funding.py`
and `build_record.py` as Python dicts. It now lives in
`data/sources/registry.json` (schema: `data/schemas/sources_registry.schema.json`)
and per-official curated record items live in
`data/sources/records/<official-id>.json` (schema:
`data/schemas/record.schema.json`'s `items` shape, minus the generated
`source_url`/`provenance` fields the builder adds). Neither of these is a new
*published* schema the frontend reads — `officials.json`, `funding.json`,
and `record.json` are still the only files `js/app.js` touches — they are
build-time input config, versioned so a `registry.json` change is reviewable
like any other data change. `scripts/pipeline/registry.py` is the only code
that should read `registry.json`; `scripts/build_record.py:load_fixture()`
is the only code that should read a `data/sources/records/*.json` fixture.

### New: `data/build_report.json` (gitignored) and `data/freshness.json` (committed)

`build_report.json` is `scripts/pipeline/report.py:BuildReport.to_dict()` —
a machine-readable summary of the most recent `build_all.py` run (per-
official, per-builder status/record-count/problems, unavailable sources,
fatal errors). It is regenerated by every run and gitignored; nothing reads
it except CI and the scheduled-refresh PR body.

`freshness.json` (schema: `data/schemas/freshness.schema.json`,
`schema_version: "2.0"`) IS committed, because its purpose is to show
honestly how fresh each official's published data is — including a builder
that failed on the most recent run. It is not gated on the overall build
succeeding; only a fatal cross-reference or preflight error (below) skips
writing it. The profile page reads it read-only through
`js/freshness.js` (started by `js/app.js`, never awaited): funding and
public-action entries are shown separately, an unsupported `schema_version`
or any fetch/parse failure shows "Update information unavailable." for
both, and an unusable single entry shows it for that dataset only.

#### freshness.json v2

```json
{
  "schema_version": "2.0",
  "generated_at": "2026-10-18T12:00:00+00:00",
  "officials": {
    "<official-id>": {
      "funding": {
        "source_type": "automated_api",
        "status": "ok",
        "attempted_at": "2026-10-18T12:00:00+00:00",
        "last_success_at": "2026-10-18",
        "source_retrieved_at": "2026-10-18T11:59:00+00:00",
        "latest_reporting_period_end": "2026-09-30",
        "displayed_donor_count": 30,
        "matched_row_count": 412,
        "donor_count": 30,
        "warning_codes": ["EMPLOYER_OCCUPATION_UNAVAILABLE"]
      },
      "record": {
        "source_type": "manual_curated",
        "status": "ok",
        "attempted_at": "2026-10-18T12:00:00+00:00",
        "last_success_at": "2026-10-18",
        "reviewed_through": null,
        "item_count": 12,
        "warning_codes": ["REVIEW_DATE_MISSING"]
      }
    }
  }
}
```

Every official in `officials.json` appears exactly once, with both
datasets. No other fields are allowed. Timestamps are UTC
`YYYY-MM-DDTHH:MM:SS+00:00` (or `Z`); dates are `YYYY-MM-DD`. No date may
be later than `generated_at`.

Two kinds of field:

- **Latest attempt** — `status`, `attempted_at`, `warning_codes` describe
  the most recent build attempt.
- **Published output** — every other field describes the data currently
  served. On `failed` or `skipped` they are carried forward unchanged from
  the previous valid `freshness.json`; a known date is never replaced with
  `null` because of a failure, and no date is ever invented.

| Field | Dataset | Meaning |
| --- | --- | --- |
| `source_type` | both | `automated_api` (Socrata API), `automated_csv` (manually downloaded CSV), `manual_curated` (record fixtures), or — funding only — `unknown`, used only for an entry migrated from v1 (v1 did not record the funding source), always with `SOURCE_TYPE_UNKNOWN`. `failed`/`skipped` carry it; the first successful funding build replaces it with `automated_api` (live or cached Socrata) or `automated_csv`. The generator cannot produce `unknown` any other way: a new official with no previous entry takes the attempted type even when its build fails or is skipped, and an entry marked `unknown` must have null `source_retrieved_at`, `latest_reporting_period_end` and `matched_row_count`. |
| `status` | both | `ok`, `failed` (previous file still served) or `skipped` (source unavailable). |
| `attempted_at` | both | The dataset-build attempt captured in this committed snapshot. It does **not** prove this was the latest GitHub Actions attempt: a scheduled run that fails before committing, or whose refresh PR is never merged, leaves no trace here. |
| `last_success_at` | both | UTC date of the last successful build of the published file. Always on or before `attempted_at`'s UTC date. On `failed`/`skipped` any earlier date is legitimate (e.g. months old). A newly successful build sets it to that build's UTC date; on `ok` the validator therefore accepts only `attempted_at`'s UTC date or the day before (the latter tolerated only because v1 builds stamped a local date). |
| `source_retrieved_at` | funding only | Time the contribution rows actually used were retrieved live from Socrata. On a live build it is that fetch's time. On a cache-backed build it is the time recorded in the cache's provenance sidecar (below), and only if the sidecar verifiably belongs to the cache contents and is not later than `attempted_at`; otherwise `null` + `SOURCE_RETRIEVED_AT_UNKNOWN`. A previous snapshot's value is never carried onto a cache-backed `ok` build, and a cache build is never stamped with the build time. Always `null` for `automated_csv` and `unknown`. Carried only on `failed`/`skipped`. |
| `latest_reporting_period_end` | funding only | Latest valid `Period End Date` across **all** committee-matched source rows (every contribution type), measured before donor aggregation and before the top-30 display cap. Values after the build date are ignored. On every `ok` build it is computed from the rows that build actually used — live, cache fallback, cache-only or CSV — and never carried from a previous snapshot; only `failed`/`skipped` carry it. `null` + `LATEST_REPORTING_PERIOD_UNKNOWN` when none is valid. It says which reporting period is represented; it is **not** "coverage through" and does not prove complete coverage. UI wording: "Latest reporting period represented ends {date}." |
| `displayed_donor_count` | funding only | Donors in the published `funding.json` (at most 30). |
| `matched_row_count` | funding only | Committee-matched source rows before aggregation and the cap. `null` when unknown (e.g. migrated from v1). |
| `donor_count` | funding only | **Deprecated** alias; always equals `displayed_donor_count`. |
| `reviewed_through` | record only | **Human-supplied only**, via an optional top-level `reviewed_through` in `data/sources/records/<id>.json`. It means a maintainer checked the project's defined official discovery sources for relevant actions through that date. It does not claim a complete historical voting record. Never derived from item dates, generated files, Git commit dates, `retrieved_at` or build dates. Presence semantics: key **absent** → carry the previous value; a valid date (on or before the build's UTC date; today is allowed) → replace it on an `ok` record build; explicit **`null`** → clear it and add `REVIEW_DATE_MISSING` (this is how a maintainer revokes a prior attestation, and it applies even if the record build fails); malformed, impossible (e.g. `2026-02-30`), non-string or future → the build fails in preflight before writing anything. |
| `item_count` | record only | Items in the published `record.json`. |
| `warning_codes` | both | Sorted, unique codes from the list below. |

Warning codes (funding may use all; record only `SOURCE_UNAVAILABLE`,
`BUILD_FAILED_PREVIOUS_DATA_SERVED`, `ZERO_ITEMS`, `REVIEW_DATE_MISSING`):

- `SOURCE_CACHE_FALLBACK` — the **contribution rows** behind the published donors came from the local Socrata cache (live fetch failed, or `--use-cache-only`), so the donor data may be older than the build.
- `SUPPORTING_SOURCE_CACHE_FALLBACK` — only the supporting statements-filed dataset (used for statement links, not donors or dates) came from the cache. Kept separate because it does not affect the age of the donor data.
- `SOURCE_RETRIEVED_AT_UNKNOWN` — present exactly when `source_retrieved_at` is `null`.
- `SOURCE_TYPE_UNKNOWN` — present exactly when `source_type` is `unknown` (a v1-migrated entry with no successful v2 funding build yet).
- `SOURCE_UNAVAILABLE` — the source (or record fixture) could not be read.
- `BUILD_FAILED_PREVIOUS_DATA_SERVED` — `failed` with an earlier success still published.
- `NO_COMMITTEE_CONFIGURED` — the official has no committee in `registry.json`.
- `NO_ROWS_MATCHED` — the source loaded but no row matched the committees.
- `ZERO_ITEMS` — the published file has zero donors/items.
- `LATEST_REPORTING_PERIOD_UNKNOWN` — present exactly when `latest_reporting_period_end` is `null`.
- `REVIEW_DATE_MISSING` — present exactly when `reviewed_through` is `null`.
- `EMPLOYER_OCCUPATION_UNAVAILABLE` — `source_type` is `automated_api`, which lacks employer/occupation.

There is deliberately **no** stale flag and no count-drop code: staleness
thresholds and the "Update information unavailable." fallback belong to the
frontend.

#### Socrata cache provenance

A live Socrata fetch writes the cache (`data/raw/.cache/*.json`, gitignored)
and then, atomically, a sidecar `<cache>.meta.json`:
`{meta_version, resource_id, where, retrieved_at, row_count, sha256}`.
The old sidecar is removed before the cache is rewritten, so an interrupted
write leaves no sidecar rather than a wrong one. A cached read trusts
`retrieved_at` only if the sidecar version, resource id, `where` filter,
row count and SHA-256 of the cache bytes all match; file mtimes are never
used. The sidecar holds only those six fields — no API token, headers,
cookies or credentials (the optional `SOCRATA_APP_TOKEN` is sent as a
request header and never persisted); the production `where` is `null`.
Both files and the sidecar's `.tmp` live in the gitignored
`data/raw/.cache/`. Crash and damage behavior: a cache with no sidecar can
still be used, but `source_retrieved_at` is `null` +
`SOURCE_RETRIEVED_AT_UNKNOWN`; a sidecar with a missing cache gives
`unavailable`; a sidecar that does not match (including a same-row-count
edit, caught by SHA-256) is ignored; an unreadable cache raises, as on main,
and stops the build before any official file is written. Each fetch's outcome (`live`, `cache_fallback`, `cache_only` or
`unavailable`, plus the verified time) is recorded per resource id (any
earlier outcome for that id is discarded when the call starts) —
contributions and statements separately — and is reset at the start of every
`build_all.run()`. The log is process-local and not thread-safe.

#### Generation, migration and preflight

`build_all.py` runs a **preflight** before any fetch or builder. Any failure
is fatal (exit 1): no `funding.json`, `record.json` or `freshness.json` is
changed, and no Socrata request is made. (The gitignored `build_report.json`
is still written, recording the fatal error.) Checks:

- `officials.json` / `registry.json` cross-reference;
- freshness configuration (schema enum matches the generator's version);
- every `--official` id exists;
- the previous `freshness.json` is missing, valid v2, or valid v1 (migrated
  in memory); malformed, partial-v1 and unknown-version files fail;
- a subset (`--official`) run requires a valid previous snapshot covering
  every official ("run a full build first to initialize freshness");
- every record attestation's `reviewed_through` (for all officials, not only
  targeted ones) is absent, `null` or a valid non-future date.

A valid **v1** file is migrated automatically by
`build_all.migrate_v1_to_v2()`, validated, and written as v2 at the end of
that build (atomic replace). Preserved: `status`, `last_success_at`, funding
`donor_count` (also as `displayed_donor_count`) and record `item_count`.
`attempted_at` and `generated_at` = v1 `generated_at`. Funding
`source_type` = `unknown`; `source_retrieved_at`,
`latest_reporting_period_end`, `matched_row_count` and `reviewed_through`
are `null` with `SOURCE_TYPE_UNKNOWN`, `SOURCE_RETRIEVED_AT_UNKNOWN`,
`LATEST_REPORTING_PERIOD_UNKNOWN` and `REVIEW_DATE_MISSING` (none provable
from v1; never backfilled from the capped `funding.json`); `ZERO_ITEMS` when
a success has a zero count. The committed file is exactly this migration of
main's v1 file.

An `--official` run rebuilds only the targeted officials and copies every
other official's entry verbatim, including its `attempted_at`. The new
snapshot is validated (also under `--skip-freshness`, the dry run, which
publishes nothing) and the build exits 1 if it is invalid. `validate_data.py` accepts a missing
file, reports a committed v1 file as legacy ("run build_all.py once"), and
fails on a malformed one.

**Step 4C: staging and effective-snapshot checks.**
`build_all.stage_snapshot(stage_root, ...)` builds every output into a
staging directory (`officials/<id>/{funding,record}.json` plus
`freshness.json`) and changes nothing under `data/officials` or
`data/freshness.json`. It then validates the *effective snapshot*: the
files that would be served, meaning this run's staged outputs plus every
retained published file.

- Builder failures: a `failed`/`skipped` status returned by a builder is a
  per-official outcome (validated partial success). An unexpected exception
  raised by either builder is fatal: the run stops and nothing may be
  published from it.
- Every staged and retained file gets the same schema and semantic checks
  as `validate_data.py`, and the staged `freshness.json` (re-read from disk)
  gets the full v2 check.
- Claim checks (`validate_data.validate_snapshot_claims`; build-time only,
  not part of the `validate_data.py` CLI):
  - freshness covers exactly the ids in `officials.json`;
  - every official has both files;
  - a dataset with neither a staged nor a previously published file is
    `NO_PUBLISHABLE_FILE`, and the run is fatal. A first-ever failure or
    skip therefore publishes nothing, and no entry claims previous data
    that does not exist;
  - for targeted officials, `ok` requires an output staged by this run;
    `failed`/`skipped` retains the published file and needs a prior
    `last_success_at`;
  - untargeted officials (`--official` runs) have nothing staged, and their
    entry equals the previous entry verbatim (an older `ok` is
    legitimate);
  - `displayed_donor_count` and `item_count` match the effective file;
  - `BUILD_FAILED_PREVIOUS_DATA_SERVED` appears only with a retained file.
- The standalone `build_funding.py` and `build_record.py` CLIs write the
  published paths directly and are outside snapshot coordination.

**Step 4C: publication, rollback and recovery.** `build_all.build_snapshot()`
is the single orchestration path; `main()` and the test suite both use it.
`build_all.run()` only builds (into a discarded temporary directory when no
`out_root` is given) and never publishes. `build_snapshot()`:

1. Takes the build lock (below). A run that is denied the lock changes
   nothing and writes no report; the CLI exits 75.
2. Preflight: the run id must match `^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$` and
   be unused, and `data/raw/.publish/` must hold no journal (any state) and
   no unexpected entry. Otherwise the run is fatal with publication
   `not_attempted`, before any builder runs. A journal-less run directory
   is an abandoned staging area and does not block.
3. Stages into `data/raw/.publish/<run_id>/staging/` and validates the
   effective snapshot (above). An exception raised while loading sources or
   staging is recorded as fatal ("build raised before publication: ..."),
   the staging area is removed, the report is written, and the exception is
   re-raised (CLI exit 1).
4. A dry run (`--skip-freshness`), an invalid snapshot or any fatal error
   ends here: the staging area is removed and nothing under `data/officials`
   or `data/freshness.json` changes (`dry_run` or `not_attempted`).
5. Publishes:
   - computes a sha256 manifest of the whole effective snapshot (every
     official's `funding.json` and `record.json`, staged or retained, plus
     the staged `freshness.json`);
   - copies every published file that will be replaced to `backup/` and
     verifies each copy before anything is replaced;
   - writes `journal.json` (`PREPARED`, then `PUBLISHING`), replaces each
     staged file with `os.replace` (freshness.json last, directory fsync
     after each), and records `PUBLISHED`;
   - re-verifies the live tree: every manifest hash, the full snapshot
     checks and the claim checks on the live files;
   - records `VERIFIED`, the commit point, then removes backups, staging,
     the journal and the run directory.
   Any failure before `VERIFIED` rolls back (freshness.json first) and
   reports `rolled_back`. If rollback cannot finish, the journal (state
   `RECOVERY_REQUIRED`) and backups are kept and the report says
   `recovery_required`. A cleanup failure after `VERIFIED` keeps the
   publication, adds the `CLEANUP_INCOMPLETE` warning (exit 1) and leaves the
   `VERIFIED` journal, which blocks the next build until `--recover`.
6. Writes the report while still holding the lock, then releases it.

Each file replacement is atomic, but a multi-file publication is not: a
process killed between replacements leaves a mixed tree and a `PUBLISHING`
journal until `--recover`. Rollback classifies every target by hash, never
overwrites a file whose content matches neither the recorded prior nor the
recorded new version, restores by copying (so a backup survives an
interrupted rollback), and is repeatable.

Journal (`data/raw/.publish/<run_id>/journal.json`, version 1): exact keys
`journal_version`, `run_id`, `state`, `updated_at`, `entries`, `manifest`,
`prior_manifest`. `prior_manifest` records the pre-publication hash of
every target in the complete snapshot, retained files included (the same
keys as `manifest`; a replaced target's value equals its entry's
`prior_sha256`, a retained target's equals its `manifest` hash). After
restoring replaced files, rollback rehashes every retained target; if any
no longer matches its prior hash, it is left untouched and rollback is not
declared complete: the run ends `RECOVERY_REQUIRED` and keeps its journal
and backups. Each entry has exactly `target`, `had_prior`, `prior_sha256`,
`new_sha256`, `staged` (`staging/<target>`) and `backup` (`backup/<target>`
or null).
Targets are `officials/<known id>/(funding|record).json` or
`freshness.json` (exactly once, last). States: `PREPARED`, `PUBLISHING`,
`PUBLISHED`, `VERIFIED`, `ROLLING_BACK`, `ROLLED_BACK`,
`RECOVERY_REQUIRED`. Recovery validates the journal first and refuses (changes
nothing) if it is malformed, names an unknown official or unsafe path,
crosses a symlink, or disagrees with its directory or manifest.

`--recover` takes the lock and resolves every run directory: journal-less
or `VERIFIED`/`ROLLED_BACK` runs are cleaned up; any other state is rolled
back, then cleaned up. It exits 0 only if every run was cleaned or rolled
back, and it never starts a build.

Lock: `fcntl.flock` (exclusive, non-blocking) on `data/raw/.build.lock`.
Holder metadata (run id, pid, mode) is written only after the lock is
acquired; the kernel releases the lock when the owner exits or is killed,
and the file is never deleted. POSIX only; local filesystems.

Report fields added to `build_report.json`: `run_id`, `mode` (`build` or
`dry_run`), `target_ids`, `publication` (`verified`, `dry_run`,
`not_attempted`, `rolled_back`, `recovery_required`), `journal_state`,
`replaced_files` (target -> `had_prior`, `prior_sha256`, `new_sha256`),
`snapshot_manifest` (target -> sha256, only when `verified`),
`publication_problems` and `publication_warnings`. Exit codes: 0 only when
the build is ok with no warnings and publication is `verified` (or `dry_run`
for a dry run); 75 when the lock is held; 1 otherwise. A validated partial
success is `verified` and exits 1.

`--verify-run RUN_ID` (with `--report-path`) is read-only and never rewrites
the report. It takes the lock, then requires: the report's `run_id` equals
RUN_ID, `mode` is `build`, `publication` is `verified`, every replaced file
matches the manifest, freshness.json was replaced, and the manifest covers
exactly every official's two files plus freshness.json. Every live file must
match its manifest hash and pass the snapshot and claim checks, and no
journal other than this run's `VERIFIED` one may remain. Untargeted entries
are checked against the live freshness.json, whose bytes the manifest hash
proves unchanged since publication.

## New: `data/districts.json`, `data/geo/council_districts.geojson`

Two more additive, optional files, introduced for the citywide map and the
donor treemap. Neither changes the shape of `officials.json`, `funding.json`,
or `record.json` — a consumer that only reads the original three files keeps
working exactly as before.

### `data/districts.json` (schema: `data/schemas/districts.schema.json`)

Geographic reference data for the index-page map: one center point per
Council District plus the Mayor's location. `mayor.center` is Los Angeles
City Hall (200 N Spring St), the seat of the Office of the Mayor — the Mayor
marker is deliberately not tied to any district polygon, since the Mayor is
elected citywide, not by district. Each `districts[]` entry's `center` is a
representative point (guaranteed to fall inside that district's own polygon)
computed from the official adopted City Council district geometry published
by the City of Los Angeles Bureau of Engineering / LA GeoHub — see `source`
in the file itself. `official_url` is each district's own `councildistrictN.lacity.gov`
page, taken from the same official dataset, not guessed.

### `data/geo/council_districts.geojson`

A topology-preserving simplification of the same official adopted district
polygons (~43 KB vs. ~1.3 MB for the full-resolution source), used only to
shade district shapes on the map. It carries `district` and `name` per
feature and nothing else; the frontend never treats it as a source of
contact info, funding, or any other fact about an official — that always
comes from `officials.json` / `funding.json` / `record.json`.

## Additions: `data/officials.json` → `party` (optional/additive)

Each entry in `data/officials.json` may carry an optional `party` object:

```json
"party": {
  "affiliation": "Democrat",
  "source": { "name": "Ballotpedia", "url": "https://ballotpedia.org/..." }
}
```

`affiliation` is one of `"Democrat"`, `"Republican"`, `"Independent"`, or
`"Not publicly listed"`. LA municipal races are officially nonpartisan (party
does not appear on the ballot), so every value here is sourced from a
credible secondary public record — an official's own Ballotpedia or
Wikipedia biography page, an official city bio, or equivalent — never
guessed or inferred from voting record, endorsements, or ideology. `source`
names that record and links to it; it is `null` only when `affiliation` is
`"Not publicly listed"` and no credible source could be found. An official
with no `party` field at all is treated identically to `"Not publicly
listed"` by the frontend — `js/app.js`'s `renderPartyField()` and
`js/map.js`'s tooltip both fall back to that label rather than leaving the
field blank. This keeps `party` fully additive: a consumer that only reads
`id`/`name`/`office` keeps working exactly as before.

## New: `data/transcripts/` (transcript-search feature, additive)

The transcript-search feature adds a new `data/transcripts/` tree that is
**entirely additive**. It does not change the shape of `officials.json`,
`funding.json`, `record.json`, or any existing schema, and it is not read
by any code path that produces those files. A consumer that only reads the
three original files keeps working exactly as before, and the existing
refresh workflow does not touch anything under this tree.

The feature is scoped to City Council meeting transcripts (YouTube CART
captions from the LA City Clerk's channel, one file per meeting), split
into per-chunk embeddings stored in Supabase, and surfaced on
`official.html` as a per-councilmember search panel. Only councilmembers
with a `resolved_official_id` in the roster (see below) currently show the
panel — every other page hides it at init.

### `data/transcripts/roster.json` (committed, human-curated)

The speaker table used by the transcript pipeline is distinct from the
published official index. `officials.json` currently has 16 profiles covering
the Mayor and Council Districts 1–15. `roster.json` currently links all 15
Council members to their profile IDs through `official_id`. The Mayor has no
entry in the transcript roster, so that profile does not expose the
councilmember transcript-search panel. This is a coverage decision and makes
no claim about whether the Mayor has spoken at a meeting.

The resolver also has procedural title labels, including `Council President`.
Those role labels require meeting-specific evidence before they can be
attributed to an individual. A name mentioned in a passage does not establish
its speaker. A future roster entry with a null `official_id` remains unlinked
and cannot be used as a per-official search identity.

The example below preserves the original contract illustration. Its three
rows and null linkage are historical examples, not the current roster.

```json
{
  "$schema": "...",
  "description": "…",
  "as_of": "2026-08-18",
  "source": {
    "name": "City of Los Angeles — Elected Officials",
    "url": "https://lacity.gov/government"
  },
  "members": [
    { "cart_label": "B. Blumenfield", "first_name": "Bob", "last_name": "Blumenfield",
      "district": 3, "official_id": null },
    { "cart_label": "Y. Jurado",     "first_name": "Ysabel", "last_name": "Jurado",
      "district": 14, "official_id": "cd14-official" },
    { "cart_label": "T. Park",       "first_name": "Traci", "last_name": "Park",
      "district": 11, "official_id": "cd11-official" }
  ]
}
```

`cart_label` is the exact string the CART stenographer writes for that
speaker in the VTT stream (typically `"<initial>. <lastname>"`); it is the
resolver's primary lookup key and MUST match the caption verbatim,
case-preserved. If the CART operator changes convention mid-term, this
field is what changes — never `first_name` / `last_name` / `district`
/ `official_id`. See `scripts/transcripts/speaker_resolver.py` for the
matching order (exact `cart_label` first, then role-only labels like
`"Council President"`, then a stdlib-Levenshtein-1 fuzzy pass for the
known CART typos, then unresolved).

### `data/transcripts/{video_id}.json` (committed, generated)

One file per ingested City Council meeting, produced by
`scripts/transcripts/build_transcripts.py`. This is the canonical
on-disk form of one meeting's transcript: if Supabase is wiped, these
files are what the pipeline re-embeds from. The raw VTT downloaded from
YouTube is NOT committed — see `.gitignore` — because it is a
byte-for-byte copy of a public source we can always re-fetch, whereas
this JSON adds the resolver's speaker attribution and trims the
pre-meeting broadcast, so it is a genuine build artifact worth keeping
under version control.

```json
{
  "video_id": "UkdZRHDB9qs",
  "meeting_date": "2026-08-04",
  "primegov_id": 12345,
  "title": "City Council Meeting",
  "language_code": "en-uYU-mmqFLq8",
  "ingested_at": "2026-08-18T22:00:00+00:00",
  "coverage": {
    "exact-role": 281,
    "exact-councilmember": 31,
    "fuzzy": 0,
    "unresolved": 0
  },
  "utterance_count": 312,
  "utterances": [
    {
      "start_sec": 2759.4,
      "end_sec": 2764.4,
      "source_label": "Clerk",
      "resolved_role": "clerk",
      "resolved_official_id": null,
      "resolved_name": "Clerk",
      "resolution_method": "exact-role",
      "text": "BLUMENFIELD, HARRIS-DAWSON, HERNANDEZ, HUTT, JURADO…"
    }
  ]
}
```

`resolved_role` is one of `"councilmember"`, `"presiding"`, `"counsel"`,
`"clerk"`, `"interpreter"`, `"reporter"`, `"public-speaker"`, or
`"unknown"`. `resolved_official_id` is populated only when the resolver
matched a `roster.json` entry with a non-null `official_id` — every
other row (public speakers, procedural roles, and councilmembers without
a site profile) has `null` there. `resolution_method` is verbatim from
`speaker_resolver.py`; `"fuzzy-from:<raw>"` records the original CART
string that a Levenshtein-1 pass mapped away from, so an audit can
distinguish exact matches from best-guess matches without re-running
the resolver.

`coverage` is a small summary of how well the resolver did on this
meeting, keyed by resolution method (with `"fuzzy-from:…"` collapsed to
`"fuzzy"`). It is used by the ingestion job's own report, not by the
frontend.

Absence of this file for a given video ID is the retry signal for the
next scheduled ingestion run — captions from a fresh livestream are not
transcoded immediately, and the pipeline treats "no VTT yet" as a normal
outcome, not an error.

### `transcript_chunks` (Supabase / Postgres, not versioned in git)

One row per 400-token chunk with 50-token overlap, produced from the
committed JSON above. Schema lives at
`data/transcripts/schema.sql`; embeddings are 1024-dim vectors from
Perplexity `pplx-embed-v1-0.6b` (unnormalized — see the schema's
comment; cosine similarity is the correct comparator). The
`(video_id, chunk_idx, embedding_model)` unique constraint makes the
ingestion job idempotent, and the `embedding_model` column is what lets
the corpus be re-embedded with a different model incrementally — a row
from a previous model coexists with its replacement until the new one
lands, and the `search_transcripts` RPC filters by `p_embedding_model`
so the two never mix in a query.

The Supabase table is not versioned in git because the JSON files above
are its source of truth; a wipe-and-rerun of
`scripts/transcripts/build_transcripts.py` recreates the same rows.
Schema *changes* to `transcript_chunks` do go through git, via
`data/transcripts/schema.sql`.

## Ownership

| Path | Owner |
| --- | --- |
| `index.html`, `official.html`, `js/app.js`, `css/style.css` | Person 4 |
| `data/officials/*/funding.json`, `scripts/build_funding.py` | Person 1 |
| `data/officials/*/record.json`, `scripts/build_record.py` | Person 2 |
| `data/officials.json` | Person 4 (frozen after minute-0 huddle) |
| `scripts/pipeline/*` (shared validation, provenance, atomic writes, registry loading, Socrata client, schema loading) | Shared — both `build_funding.py` and `build_record.py` depend on it; changes here affect both, so treat it like a shared library, not either person's private file |
| `scripts/build_all.py`, `scripts/validate_data.py` | Person 1 + Person 2 jointly (orchestrates both builders) |
| `data/sources/registry.json` | Person 1 + Person 2 jointly (funding config + record fixture paths in one file, per official) |
| `data/sources/records/<official-id>.json` | Person 2 (curated record items — same content that used to live in `build_record.py`'s `RECORDS` dict) |
| `data/schemas/*.schema.json` | Shared documentation — update alongside whichever file's shape it describes |
| `data/build_report.json` (gitignored), `data/freshness.json` | Generated by `build_all.py`; do not hand-edit |
| `.github/workflows/ci.yml`, `.github/workflows/refresh-data.yml` | Whoever touches the pipeline scripts they run |
| `tests/` | Whoever touches the code a given test file covers |
| `data/districts.json`, `data/geo/council_districts.geojson`, `js/map.js`, `css/style.css` (map/legend rules) | Owner of the citywide map feature |
| `js/treemap.js`, `css/style.css` (treemap rules) | Owner of the donor-treemap feature |
| `js/ask-ai.js`, `api/ask-official.js`, `vercel.json`, `DEPLOYMENT.md`, `css/style.css` (`.ask-ai-*` rules) | Owner of the Ask-AI Q&A feature. `api/ask-official.js` is the only code that reads `PERPLEXITY_API_KEY`; it is never read by, or exposed to, any frontend file. This feature is additive and Vercel-only — it does not change how `index.html`/`official.html` behave on the existing GitHub Pages deployment, since a missing `/api/ask-official` route there just means the module's fetch calls fail gracefully into the existing error-handling fallback message. |
| `data/transcripts/**`, `scripts/transcripts/**`, `api/search-transcripts.js`, `js/transcript-search.js`, `css/style.css` (`.transcript-search-*` rules), `.github/workflows/guard-non-goals.yml` | Owner of the transcript-search feature. `api/search-transcripts.js` and `scripts/transcripts/build_transcripts.py` are the only code that reads `PERPLEXITY_API_KEY` for embeddings and the only code that reads Supabase credentials; they are never read by, or exposed to, any frontend file. Like Ask-AI, this feature is additive and Vercel-only — a missing `/api/search-transcripts` route on the plain GitHub Pages deployment means the search panel's fetch calls fail into the existing status-line error message, and the funding/record data on the rest of the page still renders normally. `scripts/transcripts/` opts into third-party dependencies via its own `requirements-transcripts.txt` file, so it does not compromise `scripts/pipeline/`'s stdlib-only invariant. |

Everyone commits only to their own files. Zero merge conflicts possible. The
shared `scripts/pipeline/` module is the one deliberate exception to that
rule — see the row above.
