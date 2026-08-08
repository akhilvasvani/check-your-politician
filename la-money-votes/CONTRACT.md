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

## Ownership

| Path | Owner |
| --- | --- |
| `index.html`, `official.html`, `js/app.js`, `css/style.css` | Person 4 |
| `js/graph.js` | Person 3 |
| `data/officials/*/funding.json`, `scripts/build_funding.py` | Person 1 |
| `data/officials/*/record.json`, `scripts/build_record.py` | Person 2 |
| `data/officials.json` | Person 4 (frozen after minute-0 huddle) |

Everyone commits only to their own files. Zero merge conflicts possible.
