# Check Your Politician

**Follow the money. Follow the votes.**

A static, no-build-step website that shows Los Angeles city officials side by
side with two things that are usually hard to see together: **who funds
their campaigns** and **how they've actually voted / legislated**.

> Status: 🚧 hackathon-style build in progress — see [Project Status](#project-status).

<!-- ![screenshot](docs/screenshot.png) -->

---

## Table of Contents

- [Why this exists](#why-this-exists)
- [Live demo](#live-demo)
- [How it works](#how-it-works)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Data pipeline](#data-pipeline)
- [Data contract](#data-contract)
- [Tech stack](#tech-stack)
- [Ownership model](#ownership-model)
- [Project status](#project-status)
- [Roadmap](#roadmap)
- [License](#license)

---

## Why this exists

Campaign finance disclosures and legislative voting records both exist as
public data — but they live in two different places, in two different
formats, and neither one is easy for a resident to actually read. This
project pulls both together per-official, in one page, so the connection
(or lack of one) between **donors** and **decisions** is visible at a glance.

## Live demo

| ID | Real official (resolved from record data) | Link |
| --- | --- | --- |
| `mayor-bass` | Karen Bass (Mayor) | `official.html?id=mayor-bass` |
| `cd14-official` | Ysabel Jurado (CD 14) | `official.html?id=cd14-official` |
| `cd11-official` | Traci Park (CD 11) | `official.html?id=cd11-official` |

> ⚠️ `data/officials.json` still has the real names as `"REPLACE_ME"` for
> `cd14-official` / `cd11-official` — the display names above are pending
> that file being updated (see [Project Status](#project-status)).

_(Deployed link: TBD — see [Getting started](#getting-started) to run locally.)_

## How it works

```
                 ┌────────────────────┐
                 │  data/officials.json│  ← index of officials
                 └─────────┬──────────┘
                           │
        ┌──────────────────┴──────────────────┐
        ▼                                      ▼
┌───────────────────┐                ┌────────────────────┐
│ funding.json       │                │ record.json        │
│ (campaign donors)  │                │ (votes & motions)  │
│ built by           │                │ built by            │
│ build_funding.py   │                │ build_record.py     │
└─────────┬──────────┘                └──────────┬─────────┘
          │                                      │
          └──────────────────┬───────────────────┘
                              ▼
                     official.html + app.js
                              │
                              ▼
                        graph.js renders
                     an interactive funding
                     graph (Cytoscape.js)
```

1. `index.html` lists every official from `data/officials.json`.
2. Clicking an official opens `official.html?id=<official-id>`.
3. `app.js` fetches that official's `funding.json` and `record.json`.
4. `graph.js` renders the funding data as an interactive node graph —
   the official in the center, donors as nodes sized/colored by amount
   and type, click a donor for a contribution-history tooltip.
5. The voting record renders as a simple, sortable list underneath.

No build step, no framework, no bundler — open `index.html` and go.

## Project structure

```
la-money-votes/
├── index.html              # officials list
├── official.html           # one official's funding + record
├── js/
│   ├── app.js               # page wiring / fetch / render glue
│   └── graph.js              # renderFundingGraph(containerId, fundingData)
├── css/
│   └── style.css
├── data/
│   ├── officials.json        # frozen index of officials (id, name, office)
│   └── officials/
│       ├── mayor-bass/
│       │   ├── funding.json
│       │   └── record.json
│       ├── cd14-official/
│       │   ├── funding.json
│       │   └── record.json
│       └── cd11-official/
│           ├── funding.json
│           └── record.json
├── scripts/
│   ├── build_funding.py      # LA Ethics Commission campaign finance → funding.json
│   └── build_record.py       # LA City Clerk council files → record.json
└── CONTRACT.md               # frozen JSON schemas — read before editing data/
```

## Getting started

No dependencies, no build step.

```bash
git clone https://github.com/akhilvasvani/check-your-politician.git
cd check-your-politician/la-money-votes

# any static file server works, e.g.:
python -m http.server 8000
# then open http://localhost:8000
```

Regenerating data (optional — pre-built JSON is already committed):

```bash
cd la-money-votes
python scripts/build_funding.py   # writes data/officials/<id>/funding.json
python scripts/build_record.py    # writes data/officials/<id>/record.json
```

## Data pipeline

| Script | Source | Output |
| --- | --- | --- |
| `scripts/build_funding.py` | LA Ethics Commission / data.lacity.org campaign contribution disclosures | `data/officials/<id>/funding.json` |
| `scripts/build_record.py` | LA City Clerk Council File Management System (CFMS) + mayoral Executive Directives | `data/officials/<id>/record.json` |

Both scripts are pure Python stdlib — no pip installs required.

## Data contract

All JSON shapes are frozen in **[`la-money-votes/CONTRACT.md`](la-money-votes/CONTRACT.md)**.
Read it before touching anything under `data/`. tl;dr:

```jsonc
// funding.json
{
  "official": { "id", "name", "office", "reelection": { "active", "election_date", "committee" } },
  "donors": [
    { "name", "type": "individual|pac|business", "total", "employer",
      "contributions": [{ "date", "amount" }] }
  ]
}
```

```jsonc
// record.json
{
  "official_id": "...",
  "items": [
    { "council_file", "title", "role": "proposed|voted_yes|voted_no|seconded",
      "date", "outcome": "passed|failed|pending", "term": "current|previous" }
  ]
}
```

## Tech stack

- Vanilla HTML / CSS / JS — no framework, no build step
- [Cytoscape.js](https://js.cytoscape.org/) (via CDN) for the funding graph
- Python 3 stdlib for the two data-build scripts
- Static hosting — GitHub Pages / Netlify / any file host works

## Ownership model

This started as a 4-person, 1-hour build with one rule: **everyone commits
only to their own files**, so merges never conflict.

| Files | Owner |
| --- | --- |
| `index.html`, `official.html`, `js/app.js`, `css/style.css`, `data/officials.json` | Site shell / integration |
| `js/graph.js` | Funding graph |
| `scripts/build_funding.py`, `data/officials/*/funding.json` | Money pipeline |
| `scripts/build_record.py`, `data/officials/*/record.json` | Legislative record pipeline |

See [`CONTRACT.md`](la-money-votes/CONTRACT.md) for the full breakdown and
frozen schemas.

## Project status

- [x] Repo skeleton + mock data
- [x] Legislative records populated with real, sourced council files
  (`build_record.py` + `data/officials/*/record.json`)
- [ ] Real official names in `data/officials.json` — still `"REPLACE_ME"`
  for `cd14-official` (Ysabel Jurado) and `cd11-official` (Traci Park)
- [ ] Funding data populated with real LA Ethics Commission contributions
  — `build_funding.py` currently raises `NotImplementedError`;
  `funding.json` files are still the sample mock data
- [ ] Interactive funding graph — `js/graph.js` is currently the plain
  starter stub (renders a static bar list, no Cytoscape.js graph yet)
- [ ] Site shell polish / deploy

## Roadmap

- [ ] Add remaining officials beyond the initial three
- [ ] Sort/filter donor list by type, amount, date
- [ ] Link each council file / donor to its primary source
- [ ] Deploy to GitHub Pages

## License

See [`LICENSE`](LICENSE).
