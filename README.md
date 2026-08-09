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
- An interactive Cytoscape.js funding graph
- Donor filtering by type and sorting by donor, type, employer, contribution count, latest contribution, and total
- Expandable contribution detail with filing links where a verified source match is available
- Filterable legislative-record tables, split into current and previous terms
- Council-file source links where an item-level primary record is available
- A static GitHub Pages deployment workflow

## V1 scope

V1 covers the **Mayor and City Council Districts 1–15**. City Attorney and Controller profiles are deliberately out of scope because their work should be represented with an office-appropriate public-actions model, rather than being forced into a City Council voting schema.

The official roster is checked against the City of Los Angeles and City Clerk current-elected-officials directories.

## How it works

```text
data/officials.json
        │
        ├── data/officials/<official-id>/funding.json
        │       └── campaign donors and contribution history
        │
        └── data/officials/<official-id>/record.json
                └── council files, roles, outcomes, and terms

index.html ──> official.html?id=<official-id> ──> js/app.js
                                                   └── js/graph.js (Cytoscape.js)
```

1. `index.html` reads `data/officials.json` and lists the covered officials.
2. Each card opens `official.html?id=<official-id>`.
3. `js/app.js` loads the funding and public-action JSON for that official.
4. `js/graph.js` renders a donor graph with the official at the center and donors sized by contribution total.
5. The profile page renders donor controls, contribution details, and the official's record of proposals, seconding, and votes.

There is no framework or build step: the site is vanilla HTML, CSS, JavaScript, static JSON, and Python standard-library data scripts.

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

## Project structure

```text
la-money-votes/
├── index.html                         # Official directory
├── official.html                      # Per-official profile
├── css/style.css                      # Site styles
├── js/
│   ├── app.js                         # Data loading and UI rendering
│   └── graph.js                       # Cytoscape funding graph
├── data/
│   ├── officials.json                 # Official index
│   └── officials/<official-id>/
│       ├── funding.json               # Donors and contribution detail
│       └── record.json                # Public-action records
├── scripts/
│   ├── build_funding.py               # Ethics disclosure → funding.json
│   └── build_record.py                # CFMS/directives → record.json
└── CONTRACT.md                        # Data contract and ownership boundaries
```

## Run locally

```bash
git clone https://github.com/akhilvasvani/check-your-politician.git
cd check-your-politician/la-money-votes
python -m http.server 8000
```

Open `http://localhost:8000`. A static server is required because profile pages fetch JSON files.

## Data contract

Read [`la-money-votes/CONTRACT.md`](la-money-votes/CONTRACT.md) before changing data or scripts. It defines the JSON structure used by the application, including the optional, additive source-link fields.

Key rules:

- Do not silently change a JSON shape. Document and implement any schema extension in `CONTRACT.md`.
- Use primary public records where possible.
- Do not guess committee identity, donor identity, source links, votes, roles, dates, or outcomes. Flag or omit unresolved data instead.
- Keep data provenance visible to users.

## Deployment

The repository includes a GitHub Actions workflow that deploys `la-money-votes/` to GitHub Pages on pushes to `main`. In GitHub, enable **Settings → Pages → Source → GitHub Actions** once for the repository.

## License

MIT. See [`LICENSE`](LICENSE).
