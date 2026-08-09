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

`freshness.json` (schema: `data/schemas/freshness.schema.json`) IS committed,
because its entire purpose is to honestly show, at a glance, how fresh each
official's published data is — including a builder that failed on the most
recent run. It is not gated on the overall build succeeding; only a fatal
cross-reference error (which means there is nothing per-official to report)
skips writing it. `js/app.js` does not currently read this file — it is a
maintainer/reviewer-facing artifact for now, not yet wired into the UI; see
the "suggested next phase" note in the PR this was introduced in.

## Ownership

| Path | Owner |
| --- | --- |
| `index.html`, `official.html`, `js/app.js`, `css/style.css` | Person 4 |
| `js/graph.js` | Person 3 |
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

Everyone commits only to their own files. Zero merge conflicts possible. The
shared `scripts/pipeline/` module is the one deliberate exception to that
rule — see the row above.
