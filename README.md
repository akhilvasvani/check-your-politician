# Check Your Politician

**Follow the money. Follow the votes.**

A static civic-transparency site for Los Angeles that places two public records side by side for each official:

- **Campaign funding:** who contributed to the official's campaign committees
- **Public actions:** how the official has proposed, seconded, or voted on legislative matters

The project makes public records easier to inspect. It does not assert that a contribution caused a particular decision.

## Status

**V1 is complete.** The application covers the sitting Mayor of Los Angeles and all 15 City Council districts: **16 profiles total**.

V1 includes:

- An index of all 16 officials
- Per-official funding and public-action profiles
- Donor filtering by type and sorting by donor, type, employer, contribution count, latest contribution, and total
- Expandable contribution detail with filing links where a verified source match is available
- Filterable legislative-record tables, split into current and previous terms
- Council-file source links where an item-level primary record is available
- A Vercel deployment (static site + one serverless function for Ask-AI)

A later addition (still V1, same data contract) adds two more views on top of the same underlying data:

- A citywide Leaflet map with one marker per Council district plus a separate, clearly-labeled Mayor marker, hover/focus tooltips, keyboard navigation, and a no-JS fallback list
- A squarified donor treemap (area proportional to contribution total, color-coded by donor type) with an accessible legend and a click/focus detail panel, alongside the existing sortable donor table

Each profile also shows a **Party** field (Democrat, Republican, Independent, or "Not publicly listed"), sourced from a credible public record such as Ballotpedia or Wikipedia and cited with a source link — see "Party affiliation data" below.

## V1 scope

V1 covers the **Mayor and City Council Districts 1–15**. City Attorney and Controller profiles are deliberately out of scope because their work should be represented with an office-appropriate public-actions model, rather than being forced into a City Council voting schema.

The official roster is checked against the City of Los Angeles and City Clerk current-elected-officials directories.

## How it works

```text
data/officials.json
        │       └── id, name, office, and optional party affiliation + source
        │
        ├── data/officials/<official-id>/funding.json
        │       └── campaign donors and contribution history
        │
        └── data/officials/<official-id>/record.json
                └── council files, roles, outcomes, and terms

data/districts.json + data/geo/council_districts.geojson
        └── district centroids/boundaries and the Mayor's citywide location, read by js/map.js

index.html ──> official.html?id=<official-id> ──> js/app.js
                                                   ├── js/map.js (Leaflet citywide + mini map)
                                                   └── js/treemap.js (donor treemap)
```

1. `index.html` reads `data/officials.json` and lists the covered officials, and `js/map.js` reads `data/districts.json`/`council_districts.geojson` to render the citywide map above that list.
2. Each card, and each map marker, opens `official.html?id=<official-id>`.
3. `js/app.js` loads the funding, public-action, and district JSON for that official, plus its own `party` entry from `data/officials.json`.
4. `js/treemap.js` renders the funding data as a squarified treemap.
5. The profile page renders the Party field with its source link, donor controls, contribution details, the official's record of proposals, seconding, and votes, and a district mini-map.

There is no framework or build step: the site is vanilla HTML, CSS, JavaScript, static JSON, and Python standard-library data scripts. The map uses the Leaflet CDN build (no API key, no bundler) with OpenStreetMap tiles.

## Data sources and methodology

### Campaign finance

Funding data is built from Los Angeles Ethics Commission campaign-contribution disclosures. `scripts/build_funding.py` resolves candidate-controlled campaign committees, groups itemized donor contributions, and writes `funding.json`. Public matching funds, unitemized aggregates, and candidate self-loans are not presented as ordinary donors.

Where a contribution can be matched to a verified Ethics Commission filing, its contribution record includes a `source_url` linking to the underlying filing. A missing link means that no verified filing match is available in the data snapshot; it is not a claim that no public filing exists.

### Legislative and mayoral actions

`record.json` is built from Los Angeles City Clerk Council File Management System (CFMS) records and, for the Mayor where applicable, mayoral executive directives. Councilmember actions are verified against role-specific records rather than inferred from text matches. Records that cannot be independently confirmed are excluded.

Each item describes the official's role (`proposed`, `seconded`, `voted_yes`, or `voted_no`), outcome, date, and term. The app links to a primary council-file record when a verified item-level URL is available.

### Interpretation and limitations

- The site shows funding and actions side by side for public scrutiny; it does **not** infer causation.
- Campaign-finance data reflects the available disclosure snapshot and should be read with its retrieval date and underlying filing in mind.
- A profile can have incomplete contribution-level source links when the local disclosure snapshot lacks a verified committee/filing match. The interface labels that limitation rather than fabricating a link.
- Legislative records are curated, verifiable public actions—not a complete account of every action an official has taken.

### District boundaries and the citywide map

District centroids and the citywide map (`data/districts.json`, `data/geo/council_districts.geojson`) use the City of Los Angeles's own adopted Council District boundaries: [LA GeoHub, "LA City Council Districts (Adopted 2021)"](https://geohub.lacity.org/datasets/lahub::la-city-council-districts-adopted-2021/about), also served from the [Boundaries MapServer](https://maps.lacity.org/lahub/rest/services/Boundaries/MapServer/13). The Mayor's marker uses Los Angeles City Hall's public address/coordinates and is rendered with a visually distinct marker and label — it is never plotted as, or implied to be, a district. `js/map.js` loads the Leaflet library from its public CDN and map tile imagery from the public OpenStreetMap tile servers; no API key or secret is required or stored anywhere in this repo.

### Party affiliation data

`data/officials.json` (schema: `data/schemas/officials.schema.json`) models each official's party affiliation as an optional, structured `party` field — never hard-coded HTML. LA municipal elections are officially nonpartisan (party does not appear on the ballot), so `affiliation` (`"Democrat"`, `"Republican"`, `"Independent"`, or `"Not publicly listed"`) is drawn from a credible secondary public record for each individual official — their own Ballotpedia or Wikipedia biography page, or an equivalent official bio — never guessed or inferred from voting record or ideology. Every populated entry carries a `source` (`name` + `url`) rendered as a citation next to the Party field on the profile page and in the citywide map's hover/focus tooltip. An official with no verifiable source renders "Not publicly listed" rather than a fabricated value.

## Project structure

```text
la-money-votes/
├── index.html                         # Official directory + citywide map
├── official.html                      # Per-official profile (party field, district map, donor treemap, record)
├── css/style.css                      # Site styles
├── js/
│   ├── app.js                         # Data loading and UI rendering
│   ├── map.js                         # Leaflet citywide map + per-official mini map (district markers + Mayor marker)
│   ├── treemap.js                     # Squarified donor treemap (from-scratch squarify() implementation, no charting dependency)
│   └── ask-ai.js                      # "Ask about this official" Q&A module + mobile floating button (official.html)
├── api/
│   └── ask-official.js                # Vercel serverless function: calls the Perplexity Sonar API server-side, returns answer + citations
├── vercel.json                        # Vercel config (function timeout) — see DEPLOYMENT.md for the full deploy guide
├── DEPLOYMENT.md                      # Step-by-step: importing into Vercel, subdomain + CNAME setup, PERPLEXITY_API_KEY
├── data/
│   ├── officials.json                 # Official index, including optional party affiliation + source (frozen shape plus additive `party` field, read by the frontend)
│   ├── officials/<official-id>/
│   │   ├── funding.json               # Donors and contribution detail (published)
│   │   └── record.json                # Public-action records (published)
│   ├── districts.json                 # District centroids + official website links + Mayor's citywide entry (published)
│   ├── geo/council_districts.geojson  # City of Los Angeles adopted (2021) Council District boundaries (published)
│   ├── sources/
│   │   ├── registry.json              # Builder config per official (committees, election result, record fixture path)
│   │   └── records/<official-id>.json # Curated record items, one file per official (build_record.py's input)
│   ├── schemas/*.schema.json          # JSON Schema documentation for every file above, including districts.schema.json and officials.schema.json
│   ├── build_report.json              # Machine-readable report from the last build_all.py run (gitignored)
│   └── freshness.json                 # Per-official build status/timestamps (published, not yet read by the frontend)
├── scripts/
│   ├── pipeline/                      # Shared library: validation, provenance, atomic writes, registry loading, Socrata client, schema loading
│   ├── build_funding.py               # Ethics Commission API/CSV → funding.json, one or all officials
│   ├── build_record.py                # Curated fixtures → record.json, one or all officials
│   ├── build_all.py                   # Orchestrates both builders for every official, with per-official failure isolation
│   └── validate_data.py               # Schema/cross-reference-validates whatever is currently committed, no network
├── tests/                             # unittest suite, fixtures only, no live network calls
└── CONTRACT.md                        # Data contract and ownership boundaries
```

## Run locally

```bash
git clone https://github.com/akhilvasvani/check-your-politician.git
cd check-your-politician/la-money-votes
python -m http.server 8000
```

Open `http://localhost:8000`. A static server is required because profile pages fetch JSON files.

## Rebuilding the data

All commands run from `la-money-votes/` and use only the Python standard library — nothing to `pip install`.

```bash
# rebuild funding.json for every official, live from the LA Ethics Commission's public Socrata API
python3 scripts/build_funding.py --fetch-socrata

# ...or offline, from a manually-downloaded CSV export (see "Source policy" below for the two dataset URLs)
python3 scripts/build_funding.py --csv-path data/raw/contributions.csv

# only one official
python3 scripts/build_funding.py --fetch-socrata --official mayor-bass

# rebuild record.json (curated fixtures under data/sources/records/, no network)
python3 scripts/build_record.py
python3 scripts/build_record.py --official cd11-official

# run both builders for every official at once, with per-official failure isolation
python3 scripts/build_all.py --fetch-socrata

# validate whatever is currently committed, without rebuilding anything (no network)
python3 scripts/validate_data.py

# run the test suite (fixtures only, no network)
python3 -m unittest discover
```

`build_all.py` writes `data/build_report.json` (gitignored — a machine-
readable summary of what happened) on every run, and `data/freshness.json`
(committed) reflecting the real per-official status, including any failure.
It never lets a failed or partially-invalid build overwrite a previously
committed, valid `funding.json` or `record.json` — see CONTRACT.md's
"Additions" section and `scripts/pipeline/atomic_io.py`.

## Source policy

Prefer, in this order: an official API or open-data portal > a stable
official downloadable export > hand-curated entries individually verified
against an official page, cross-checked with news coverage. Browser
automation against an official site is a last resort, used only when no
stable data endpoint or downloadable export exists. Every factual record
must resolve to a URL in `scripts/pipeline/validation.py`'s
`ALLOWED_SOURCE_DOMAINS` allowlist (the LA Ethics Commission, City Clerk,
Mayor's office, City Controller, and `lacity.gov` itself) — anything else
fails validation rather than being trusted.

| Data | Source | Access method |
| --- | --- | --- |
| Campaign contributions | LA Ethics Commission, "City Campaign Contributions (and Misc. Increases to Cash)" | Public Socrata API, dataset [`m6g2-gc6c`](https://data.lacity.org/d/m6g2-gc6c), no auth required |
| Campaign statement filing links (for `contributions[].source_url`) | LA Ethics Commission, "City Campaign Statements Filed" | Public Socrata API, dataset [`br3a-db9a`](https://data.lacity.org/d/br3a-db9a), no auth required |
| Council votes, motions, ordinances | LA City Clerk's Council File Management System (CFMS) | **No official bulk API, CSV, or JSON export exists** (confirmed — CFMS is not built on Legistar, which is where such an export would normally live). Hand-curated per item at `data/sources/records/<official-id>.json`, each entry individually verified against its own CFMS record page and cross-checked with news coverage, then versioned like any other data change. An unofficial third-party paid API exists for CFMS; it was deliberately not used here — the project's policy is to prefer free, official access, and to ask before adopting any paid service. |
| Mayoral executive directives/orders | mayor.lacity.gov | Individually verified PDFs; no discoverable stable per-item URL pattern, so these render without a per-item source link (dataset-level citation only) |

### Known limitation: employer/occupation on automated funding refreshes

The Socrata contributions dataset (`m6g2-gc6c`) does **not** include donor
occupation or employer — those two fields exist only in the Ethics
Commission's manual CSV export UI, not its API. `build_funding.py
--fetch-socrata` therefore writes `employer: null` for every donor, and adds
a `source_notes` warning to the build report when it does. This is a real
gap in the public API, not a bug, and it means the currently-committed
`funding.json` files (built from a manually-downloaded CSV) are richer than
what an automated refresh alone can produce. See "How refresh PRs are
reviewed" below — this is exactly the kind of thing a reviewer should look
for before merging.

## Refresh schedule

`.github/workflows/refresh-data.yml` runs `build_all.py --fetch-socrata`
twice a week (Monday and Thursday, 08:00 UTC) and on manual dispatch. It
never pushes to `main` — it opens or updates a pull request on the
`automated/data-refresh` branch containing whatever data actually changed,
with the full build report embedded in the PR body.

## How refresh PRs are reviewed

An automated refresh PR is not auto-mergeable. Before merging one, a
maintainer should:

1. Read the build report table in the PR body — confirm no official shows
   `failed`, and understand why any `skipped`/unavailable-source rows exist.
2. Check the diff for `employer`/`occupation` regressions (see "known
   limitation" above) — an automated refresh will null these out for any
   donor whose only source is the live API.
3. Spot-check a couple of changed dollar amounts or dates against the
   linked `source_url` before trusting the diff.
4. Confirm CI (schema validation + tests) passed on the PR.

Only then merge — Vercel Production picks up the push to `main` and
redeploys automatically.

## Methodology and known limitations

- The site presents sourced, factual funding and public-action records side
  by side. It does not claim, and its data model has no field for, causation
  between a contribution and a vote or position — see CONTRACT.md.
- Every contribution and record item carries a `provenance` block (source
  name, source URL, retrieval date, reporting period or meeting date, a
  stable record ID when one exists, and a methodology version) — see
  CONTRACT.md "Additions."
- Legislative/voting data is hand-curated (no official bulk export exists —
  see "Source policy" above) and is therefore a curated, verifiable sample
  of an official's public actions, not a complete voting record.
- Automated funding refreshes lack donor employer/occupation (a public-API
  limitation, documented above) — the richer, manually-downloaded-CSV
  version of that field is not overwritten unless a maintainer merges a
  refresh PR that removes it.
- `data/freshness.json` is generated on every build but is not yet
  surfaced in the UI — see "suggested next phase" in the PR that introduced
  the current data pipeline.
- Party affiliation is sourced from secondary public records (Ballotpedia,
  Wikipedia, or an equivalent official bio) because LA municipal races are
  officially nonpartisan and party does not appear on the ballot itself —
  see "Party affiliation data" above.
- The donor treemap visualizes the same itemized-contribution snapshot as the
  existing donor table (same `funding.json`, same reporting period); it does
  not introduce any new donor amounts or identities.
- District centroids in `data/districts.json` are simplified single points
  (not full polygon renders) for marker placement; the full adopted boundary
  polygons are in `data/geo/council_districts.geojson` for any future choropleth
  or overlay use.

## Data contract

Read [`la-money-votes/CONTRACT.md`](la-money-votes/CONTRACT.md) before changing data or scripts. It defines the JSON structure used by the application, including the optional, additive source-link fields.

Key rules:

- Do not silently change a JSON shape. Document and implement any schema extension in `CONTRACT.md`.
- Use primary public records where possible.
- Do not guess committee identity, donor identity, source links, votes, roles, dates, or outcomes. Flag or omit unresolved data instead.
- Keep data provenance visible to users.

## Deployment

The site is deployed on **Vercel**, which serves the static site (`index.html`,
`official.html`, `css/`, `js/`, `data/`) and the one serverless function
that powers the "Ask about this official" feature (`api/ask-official.js`).
A static-only host (like GitHub Pages, previously used here) can't run that
function, which is why the project moved to Vercel.

- **Production** — pushes to `main` auto-deploy to Vercel Production
  (`check-your-politician.vercel.app`).
- **Preview** — every other branch/PR gets its own Vercel Preview
  deployment; the `feature/ask-ai-vercel-district-label` branch is
  additionally bound to the `lapolitician.akhilvasvani.com` custom
  subdomain for pre-merge testing.

See [`la-money-votes/DEPLOYMENT.md`](la-money-votes/DEPLOYMENT.md) for the
full step-by-step (importing into Vercel, custom-domain/CNAME setup,
`PERPLEXITY_API_KEY`, and the rate-limiting env vars for Ask-AI).

## License

MIT. See [`LICENSE`](LICENSE).
