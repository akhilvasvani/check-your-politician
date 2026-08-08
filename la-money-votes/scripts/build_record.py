#!/usr/bin/env python3
"""la-money-votes — build_record.py, Person 2 owns this file.

Writes data/officials/<id>/record.json for each official listed in
data/officials.json. Output conforms to the schema frozen in CONTRACT.md.

DATA SOURCE (Plan B — hand-curated, no invented entries):
Every item below was looked up individually on LACityClerk Connect (the
Council File Management System at cityclerk.lacity.org/lacityclerkconnect)
by council file number, cross-checked against news coverage / official
councilmember and mayoral press releases. Mayor Bass does not sponsor or
vote on Council Files (she is not a Council member), so her items use her
own numbered Executive Directives ("ED-#") and Emergency Executive Orders
("EO-#") from mayor.lacity.gov in the council_file field instead.

Term cutoffs used to classify "current" vs "previous":
- mayor-bass:    single term in progress since 2022-12-12 -> everything "current".
- cd14-official  (Ysabel Jurado): single term in progress since 2024-12-09 ->
  everything "current".
- cd11-official  (Traci Park): first term 2022-12-12 to ~2026-06-30, second
  term (won outright in the June 2, 2026 primary) starting ~2026-07-01.
  No confirmed, sourced Council File exists yet for her second term as of
  this script's last update, so every item below is "previous".

To regenerate: update RECORDS below only with entries you can point to a
real council_file / activity for, then run this script.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFICIALS_INDEX = ROOT / "data" / "officials.json"

RECORDS = {
    "cd14-official": [
        {"council_file": "24-1563", "title": "Additional Patrols / Interim Homeless Housing Sites / Council District 11 / General City Purposes Fund",
         "role": "voted_no", "date": "2025-01-07", "outcome": "passed", "term": "current"},
        {"council_file": "25-0542", "title": "LGBT Heritage Month / City Hall Illumination / Council District 14 / Heritage Month Celebration and Special Events",
         "role": "proposed", "date": "2025-05-16", "outcome": "passed", "term": "current"},
        {"council_file": "25-0600-S17", "title": "Budget Motion / Bureau of Street Services / Public Toilet Maintenance Contracts / Funding",
         "role": "proposed", "date": "2025-05-22", "outcome": "pending", "term": "current"},
        {"council_file": "25-0577", "title": "Bureau of Homelessness Oversight / Local State of Emergency on Homelessness / Termination",
         "role": "proposed", "date": "2025-05-28", "outcome": "passed", "term": "current"},
        {"council_file": "25-0645", "title": "Special Motion / Community Impact / Civil Disturbance / Local Small Businesses / Graffiti Removal / Outside Funding",
         "role": "proposed", "date": "2025-06-10", "outcome": "passed", "term": "current"},
        {"council_file": "25-0881", "title": "LA County Registrar-Recorder / City Clerk Summit / We Speak Your Language Events Summit",
         "role": "proposed", "date": "2025-08-05", "outcome": "passed", "term": "current"},
        {"council_file": "25-0887", "title": "Waive Vehicle Towing Fees / Waive Impound Storage Fee / Individuals Detained by Federal Immigration Enforcement Agencies",
         "role": "proposed", "date": "2025-08-06", "outcome": "passed", "term": "current"},
        {"council_file": "25-0002-S62", "title": "SB 627 (Wiener) / No Secret Police Act / Face Covering Prohibition / Identifying Uniform / ICE Raids",
         "role": "voted_yes", "date": "2025-08-19", "outcome": "passed", "term": "current"},
        {"council_file": "26-0011-S6", "title": "Repair Work / Street Lighting Crew / Street Furniture Fund / Council District 5 and 11 / Overtime Funding",
         "role": "voted_yes", "date": "2026-02-24", "outcome": "passed", "term": "current"},
        {"council_file": "25-0006-S38", "title": "Climate Resilience District / Pacific Palisades / 2025 Windstorm and Wildfire Recovery",
         "role": "voted_yes", "date": "2026-03-27", "outcome": "passed", "term": "current"},
    ],
    "cd11-official": [
        {"council_file": "23-0839", "title": "Temescal Canyon Road / Pacific Coast Highway / West Bowdoin Street / Structural Instability / Water Seepage / Roadway Damage",
         "role": "proposed", "date": "2023-08-11", "outcome": "passed", "term": "previous"},
        {"council_file": "24-1563", "title": "Additional Patrols / Interim Homeless Housing Sites / Council District 11 / General City Purposes Fund",
         "role": "proposed", "date": "2024-12-10", "outcome": "passed", "term": "previous"},
        {"council_file": "25-0006-S58", "title": "LA Region Small Business Relief Fund / LA Region Worker Relief Fund / 2025 Windstorm and Wildfire Recovery",
         "role": "voted_yes", "date": "2025-02-07", "outcome": "passed", "term": "previous"},
        {"council_file": "25-0006-S67", "title": "Burn Zone Soil / Testing and Remediation / Park Property / Parkways / Medians / Pacific Palisades / 2025 Windstorm and Wildfire Recovery",
         "role": "voted_yes", "date": "2025-04-23", "outcome": "passed", "term": "previous"},
        {"council_file": "26-0011-S6", "title": "Repair Work / Street Lighting Crew / Street Furniture Fund / Council District 5 and 11 / Overtime Funding",
         "role": "proposed", "date": "2026-02-13", "outcome": "passed", "term": "previous"},
        {"council_file": "25-0006-S38", "title": "Climate Resilience District / Pacific Palisades / 2025 Windstorm and Wildfire Recovery",
         "role": "voted_yes", "date": "2026-03-27", "outcome": "passed", "term": "previous"},
        {"council_file": "25-0006-S88", "title": "Sales Tax Relief for Purchases / Palisades Reconstruction / 1% Share of Sales Tax",
         "role": "proposed", "date": "2026-03-27", "outcome": "pending", "term": "previous"},
    ],
    "mayor-bass": [
        {"council_file": "ED-1", "title": "Expedition of Permits and Clearances for Temporary Shelters and Affordable Housing Types",
         "role": "proposed", "date": "2022-12-16", "outcome": "passed", "term": "current"},
        {"council_file": "ED-2", "title": "Inside Safe Initiative",
         "role": "proposed", "date": "2022-12-21", "outcome": "passed", "term": "current"},
        {"council_file": "ED-3", "title": "Emergency Use of Viable City-Owned Property",
         "role": "proposed", "date": "2023-02-10", "outcome": "passed", "term": "current"},
        {"council_file": "ED-4", "title": "Identifying Barriers to Small Business Creation, Development and Growth",
         "role": "proposed", "date": "2023-06-22", "outcome": "passed", "term": "current"},
        {"council_file": "ED-5", "title": "Improving Customer Experience",
         "role": "proposed", "date": "2023-10-30", "outcome": "passed", "term": "current"},
        {"council_file": "ED-7", "title": "Streamlining and Accelerating Housing Production",
         "role": "proposed", "date": "2023-11-08", "outcome": "passed", "term": "current"},
        {"council_file": "ED-8", "title": "Uplifting Our Economy Through Entertainment Production",
         "role": "proposed", "date": "2024-08-06", "outcome": "passed", "term": "current"},
        {"council_file": "ED-9", "title": "Streamlining Capital Project Delivery and Equitably Investing in the Public Right of Way",
         "role": "proposed", "date": "2024-10-16", "outcome": "passed", "term": "current"},
        {"council_file": "EO-1", "title": "Emergency Executive Order — Expedited Community Rebuilding and Recovery (Palisades Fire)",
         "role": "proposed", "date": "2025-01-13", "outcome": "passed", "term": "current"},
        {"council_file": "ED-10", "title": "Artificial Intelligence Pilot Program",
         "role": "proposed", "date": "2025-04-22", "outcome": "passed", "term": "current"},
        {"council_file": "EO-9", "title": "Local Prohibition on SB 9 in Burn Areas",
         "role": "proposed", "date": "2025-07-30", "outcome": "passed", "term": "current"},
        {"council_file": "ED-15", "title": "Mayoral Review of Proprietary Department Actions and Streamlining of Procurement Processes",
         "role": "proposed", "date": "2025-09-24", "outcome": "passed", "term": "current"},
    ],
}


def build_record(official_id: str) -> None:
    out_path = ROOT / "data" / "officials" / official_id / "record.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    items = RECORDS.get(official_id)
    if items is None:
        raise NotImplementedError(f"No curated record data for {official_id}")
    payload = {"official_id": official_id, "items": items}
    out_path.write_text(json.dumps(payload, indent=2) + "\n")


def main() -> None:
    officials = json.loads(OFFICIALS_INDEX.read_text())
    for official in officials:
        build_record(official["id"])


if __name__ == "__main__":
    main()
