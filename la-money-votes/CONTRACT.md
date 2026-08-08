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

## Ownership

| Path | Owner |
| --- | --- |
| `index.html`, `official.html`, `js/app.js`, `css/style.css` | Person 4 |
| `js/graph.js` | Person 3 |
| `data/officials/*/funding.json`, `scripts/build_funding.py` | Person 1 |
| `data/officials/*/record.json`, `scripts/build_record.py` | Person 2 |
| `data/officials.json` | Person 4 (frozen after minute-0 huddle) |

Everyone commits only to their own files. Zero merge conflicts possible.
