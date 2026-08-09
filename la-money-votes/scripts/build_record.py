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
- cd2-official    (Adrin Nazarian): single term in progress since 2024-12-09
  (per https://clerk.lacity.gov/articles/current-elected-officials) ->
  everything "current".
- cd1, cd4, cd5, cd6, cd7, cd8, cd9, cd10, cd12, cd13, cd15-official: added
  2026-08-09 (V1-roster completion). Every officeholder's current term is
  still ongoing as of this update (including cd9-official/Curren Price and,
  once separately confirmed as termed-out, cd3-official/Bob Blumenfield), so
  every item below is "current". Items were found via the CFMS Advanced
  Search's structured Mover/Seconder checkbox filters (not a Title/Subject
  text search, which does not reliably surface these motions — see each
  official's research notes in /home/user/workspace/v1_roster/records/ for
  full per-item methodology and any excluded/ambiguous candidates), then
  each item's own record page (fa=ccfi.viewrecord) was opened individually
  to confirm council file number, title, Mover/Second name, date, and
  Council-action outcome before inclusion.

Every item also carries a "source_url" pointing at the primary record it was
read from, so a reader can check any row without taking our word for it. See
source_url_for() for which items can be deep-linked and which cannot.

To regenerate: update RECORDS below only with entries you can point to a
real council_file / activity for, then run this script.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFICIALS_INDEX = ROOT / "data" / "officials.json"

# Primary-source roots. Only verified, stable URLs belong here — a dead or
# guessed link on a transparency site is worse than no link at all.
CFMS_ROOT = "https://cityclerk.lacity.org/lacityclerkconnect/"
CFMS_VIEWRECORD = CFMS_ROOT + "index.cfm?fa=ccfi.viewrecord&cfnumber={council_file}"
MAYOR_ROOT = "https://mayor.lacity.gov/"

# Council file numbers look like "25-0542", with an optional "-S<n>" suffix for
# a numbered sub-file ("25-0600-S17").
COUNCIL_FILE_PATTERN = re.compile(r"^\d{2}-\d{4}(?:-S\d+)?$")

# Where each official's items come from, shown once under the record table.
DEFAULT_SOURCE = {
    "name": "LA City Clerk — Council File Management System",
    "url": CFMS_ROOT,
}
SOURCES = {
    # Bass files no Council Files; her items are her own numbered directives.
    "mayor-bass": {
        "name": "Office of the Mayor — Executive Directives and Emergency Executive Orders",
        "url": MAYOR_ROOT,
    },
}

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
    "cd2-official": [
        {"council_file": "25-0057", "title": "648 and 800 West Avenue 37 / Mt. Washington / Criminal Activity / Illegal Dumping / Temporary Closure",
         "role": "seconded", "date": "2025-07-30", "outcome": "passed", "term": "current"},
        {"council_file": "25-0964", "title": "New Financial Policy / Exceeding Contract Spending",
         "role": "seconded", "date": "2025-08-20", "outcome": "pending", "term": "current"},
        {"council_file": "25-1036", "title": "Chapter 11.20 of Title 11 / Health and Safety of the Los Angeles County Code / Maximum Indoor Temperature / Rental Housing",
         "role": "proposed", "date": "2025-09-03", "outcome": "passed", "term": "current"},
        {"council_file": "26-0195-S4", "title": "Keep Hollywood Home / FilmLA / Episodic Series / Feature Film / Commercial Production Retention Program",
         "role": "proposed", "date": "2026-02-13", "outcome": "pending", "term": "current"},
        {"council_file": "26-0705", "title": "Non-Profit Private Country/Golf Clubs (Social Clubs) / Annual Parcel Tax / November 2026 Ballot",
         "role": "proposed", "date": "2026-05-08", "outcome": "pending", "term": "current"},
    ],
    "cd1-official": [
        {"council_file": "24-1219-S1", "title": "Street Sweeping Policies and Routes / Department of Transportation / No Parking Restrictions Compliance",
         "role": "proposed", "date": "2025-08-01", "outcome": "passed", "term": "current"},
        {"council_file": "26-0955", "title": "Bureau of Street Lighting / Assessment Ballot Failure / Funding / Maintain Workforce / Baseline Services",
         "role": "proposed", "date": "2026-06-26", "outcome": "passed", "term": "current"},
        {"council_file": "26-1075", "title": "North Alameda Street / Alhambra Avenue / Main Street / Alameda Triangle / Triangular Parcel / Street Vacation Proceedings",
         "role": "proposed", "date": "2026-08-05", "outcome": "pending", "term": "current"},
        {"council_file": "24-1577", "title": "Salaries / Contractual Services / Field Equipment / Operating Supplies / General City Purposes Fund",
         "role": "proposed", "date": "2026-06-23", "outcome": "passed", "term": "current"},
        {"council_file": "26-0864", "title": "Strengthen Emergency Preparedness and Response Capabilities / Pre-Incident Vendor Qualification Programs / Emergency Response Agreements / Port Related Disasters",
         "role": "seconded", "date": "2026-06-10", "outcome": "pending", "term": "current"},
    ],
    "cd4-official": [
        {"council_file": "26-0600-S7", "title": "Budget Motion / Recreation and Parks / Runyon Canyon Park / Daily Security Services 7 p.m. to 1 a.m. / Funding",
         "role": "proposed", "date": "2026-05-21", "outcome": "pending", "term": "current"},
        {"council_file": "25-0600-S22", "title": "Budget Motion / Los Angeles Housing Department / Controller / Quarterly Advances / Interim Housing Contracts / Los Angeles Homeless Services Authority",
         "role": "proposed", "date": "2025-05-22", "outcome": "passed", "term": "current"},
        {"council_file": "25-0006-S13", "title": "Special Motion 13 / Impacted Workers / Resources and Assistance / 2025 Windstorm and Wildfire Recovery",
         "role": "seconded", "date": "2025-01-14", "outcome": "passed", "term": "current"},
        {"council_file": "25-0600-S28", "title": "Budget Motion / Civil + Human Rights and Equity Department / Public Information Director / Funding",
         "role": "seconded", "date": "2025-05-22", "outcome": "pending", "term": "current"},
        {"council_file": "26-0600-S8", "title": "Budget Motion / North Atwater East Bank Riverway Project / Capital and Technology Improvement Expenditure Program Funding",
         "role": "seconded", "date": "2026-05-21", "outcome": "pending", "term": "current"},
    ],
    "cd5-official": [
        {"council_file": "25-0647-S2", "title": "Special 1 Motion / Fiscal Year 2024-25 and 2025-26 / Los Angeles Police Department / Reserve Fund Loan / June 10, 2025 Local Emergency / Overtime Cost",
         "role": "proposed", "date": "2025-06-18", "outcome": "passed", "term": "current"},
        {"council_file": "25-0006-S18", "title": "Special Motion 18 / City Budget Impacts / Front-Funding Strategies / FEMA Reimbursement / 2025 Windstorm and Wildfire Recovery",
         "role": "proposed", "date": "2025-02-26", "outcome": "passed", "term": "current"},
        {"council_file": "24-1360", "title": "Leave Time Expansion / Late Term and Term Stillbirth / Emotional and Physical Recovery Resources / Los Angeles Administrative Code / Amendment",
         "role": "proposed", "date": "2024-12-11", "outcome": "passed", "term": "current"},
        {"council_file": "25-0006-S17", "title": "Special Motion 17 / Low Water Pressure / Dry Hydrants / Santa Ynez Reservoir / 2025 Windstorm and Wildfire Recovery",
         "role": "seconded", "date": "2025-07-01", "outcome": "passed", "term": "current"},
    ],
    "cd6-official": [
        {"council_file": "26-1063", "title": "CARE+ Cleanup Efforts / Council District 6 / AB1290 Fund / Police Department Fund",
         "role": "proposed", "date": "2026-08-04", "outcome": "pending", "term": "current"},
        {"council_file": "26-1064", "title": "Northeast Graffiti Busters (NEGB) / AB1290 Fund / Supplemental Beautification Services / Council District 6",
         "role": "proposed", "date": "2026-08-04", "outcome": "pending", "term": "current"},
        {"council_file": "25-1434", "title": "Illegal Dumping Enforcement / Trash Collection / Council District 6 / AB1290 Fund",
         "role": "proposed", "date": "2025-12-03", "outcome": "passed", "term": "current"},
        {"council_file": "25-1435", "title": "AB1290 Fund / CARE+ Cleanup / Police Department Fund / Overtime / Council District 6",
         "role": "proposed", "date": "2025-12-03", "outcome": "passed", "term": "current"},
        {"council_file": "23-0973-S1", "title": "Northeast Graffiti Busters (NEGB) / Beautification Services / Council District 6 / Neighborhood Service Enhancements / General City Purposes Fund / Transfer / Contractual Services / 2024-25",
         "role": "proposed", "date": "2024-11-08", "outcome": "passed", "term": "current"},
    ],
    "cd7-official": [
        {"council_file": "25-1178", "title": "Los Angeles Tourism and Convention Board / Dine LA / Waive Participation Fee",
         "role": "proposed", "date": "2025-10-07", "outcome": "passed", "term": "current"},
        {"council_file": "26-0425", "title": "Bert and Jane Boeckmann / Roscoe Boulevard / Langdon Avenue / Permanent Ceremonial Signage",
         "role": "proposed", "date": "2026-03-24", "outcome": "passed", "term": "current"},
        {"council_file": "26-0029", "title": "Illegal Cannabis Operators / Cannabis Support Units / Improvement and Enforcement /Current Procedures and Practices",
         "role": "proposed", "date": "2026-01-09", "outcome": "passed", "term": "current"},
        {"council_file": "26-0963", "title": "Additional CARE+ Service Day and Overtime Costs / Council District 7 / Bureau of Sanitaion Fund / General City Purposes Fund",
         "role": "proposed", "date": "2026-06-30", "outcome": "passed", "term": "current"},
    ],
    "cd8-official": [
        {"council_file": "26-0974", "title": "9402 South Broadway (Site) / City-owned Property / Community Development Block Grant (CDBG) funds / Exclusive Negotiating Agreement Extension",
         "role": "proposed", "date": "2026-07-01", "outcome": "passed", "term": "current"},
        {"council_file": "26-0438", "title": "Purpose Driven Solutions Consulting, LLC / Management and Production of Community Events / General City Purpose Fund / Council District 8 / Transfer of Funds",
         "role": "proposed", "date": "2026-03-24", "outcome": "passed", "term": "current"},
        {"council_file": "25-0331", "title": "Unarmed Crisis Response / Single City-Wide Program / Crisis and Incident Response Through Community Led Engagement (CIRCLE) / Unarmed Model of Crisis Response (UMCR)",
         "role": "proposed", "date": "2025-03-25", "outcome": "passed", "term": "current"},
        {"council_file": "25-0605", "title": "BRIDGE Housing Corporation / 8505 Evermont Place / Vermont and Manchester Project / Sustainable Transit Infrastructure Improvements / Affordable Housing and Sustainable Communities (AHSC) Fund",
         "role": "proposed", "date": "2025-06-04", "outcome": "passed", "term": "current"},
        {"council_file": "25-0219", "title": "Office of Strategic Partnership / Harbor Freight Tools Foundation / Donation",
         "role": "proposed", "date": "2025-02-28", "outcome": "passed", "term": "current"},
        {"council_file": "25-1509-S1", "title": "Keep Hollywood Home / Special Conditions Repeal / Unified Filming Framework / FilmLA",
         "role": "seconded", "date": "2025-12-12", "outcome": "passed", "term": "current"},
    ],
    "cd9-official": [
        {"council_file": "26-1048", "title": "2026 Latino Heritage Month / Celebrations and Special Events / Council District 9 / General City Purpose Fund",
         "role": "proposed", "date": "2026-08-04", "outcome": "pending", "term": "current"},
        {"council_file": "26-0929", "title": "Enforcement and Investigation of Illegal Dumping / Council District 9 / AB1290 Fund",
         "role": "proposed", "date": "2026-06-24", "outcome": "passed", "term": "current"},
        {"council_file": "25-1072", "title": "Additional Street Sweeping Services / Council District 9 / AB1290 Fund",
         "role": "proposed", "date": "2025-09-12", "outcome": "passed", "term": "current"},
        {"council_file": "25-0340", "title": "South Los Angeles Wetlands Improvements Project / Council District 9 / AB 1290 Fund",
         "role": "proposed", "date": "2025-03-28", "outcome": "passed", "term": "current"},
        {"council_file": "26-0204", "title": "Executive Directive 17 / Ensure Protection for City Residents / Federal Immigration Enforcement Operations / Ordinance",
         "role": "seconded", "date": "2026-02-13", "outcome": "passed", "term": "current"},
    ],
    "cd10-official": [
        {"council_file": "25-0932", "title": "Community DASH Buses / Special Events Advertisement / Commercial and Promotional Advertising",
         "role": "proposed", "date": "2025-08-13", "outcome": "passed", "term": "current"},
        {"council_file": "24-0600-S14", "title": "Budget Motion / Transportation Committee Jurisdiction / Transportation Grant Funds",
         "role": "proposed", "date": "2024-05-23", "outcome": "passed", "term": "current"},
        {"council_file": "24-0600-S11", "title": "Budget Motion / Aging / Rapid Response Senior Meals Program / Funding / Reserve for Extraordinary Liability / Unappropriated Balance Fund",
         "role": "proposed", "date": "2024-05-23", "outcome": "passed", "term": "current"},
        {"council_file": "25-0600-S12", "title": "Budget Motion / Los Angeles Fire Department / Critical Staffing Needs / Innovation Fund",
         "role": "proposed", "date": "2025-05-22", "outcome": "pending", "term": "current"},
        {"council_file": "25-0006-S4", "title": "Special Motion 4 / Disaster Center Site / Emergency Management Department / Federal Emergency Management Agency (FEMA) / Council District 11 / 2025 Windstorm and Wildfire Recovery",
         "role": "seconded", "date": "2025-01-14", "outcome": "passed", "term": "current"},
    ],
    "cd12-official": [
        {"council_file": "26-1045", "title": "Speed Tables and T-Curbs Installation / Sesnon East Speed Reduction Project / Sunshine Canyon Community Amenities Trust Fund / Council District 12",
         "role": "proposed", "date": "2026-08-04", "outcome": "pending", "term": "current"},
        {"council_file": "26-0474", "title": "Additional Police Services / AB 1290 Fund / Topanga Division / Council District 12",
         "role": "proposed", "date": "2026-03-27", "outcome": "passed", "term": "current"},
        {"council_file": "26-0378", "title": "FIFA World Cup Community Celebration / Neighborhood Service Enhancements / Department of Recreation and Parks (RAP) / Transfer of Funds / Council District 12",
         "role": "proposed", "date": "2026-03-13", "outcome": "passed", "term": "current"},
        {"council_file": "26-0333", "title": "Friends of Oakridge / Sunshine Canyon Community Amenities Trust Fund / Council District 12",
         "role": "proposed", "date": "2026-03-10", "outcome": "passed", "term": "current"},
        {"council_file": "26-0206", "title": "AB1290 Fund / Supporting Community Programs and Groups / General City Purposes Fund / Council District 12",
         "role": "proposed", "date": "2026-02-13", "outcome": "passed", "term": "current"},
    ],
    "cd13-official": [
        {"council_file": "26-0812", "title": "Ross Stores, Inc / Compensatory Penalties / Notice of Violation / Civil and Human Rights Law",
         "role": "proposed", "date": "2026-06-02", "outcome": "passed", "term": "current"},
        {"council_file": "26-0813", "title": "Harvard Motor Inn / Compensatory Penalties / Notice of Violation / Civil and Human Rights Law",
         "role": "proposed", "date": "2026-06-02", "outcome": "passed", "term": "current"},
        {"council_file": "26-0638", "title": "Voting Rights / Noncitizen Enfranchisement / Municipal Elections / Los Angeles Unified School District Board of Education / Charter Amendment / November 2026 Ballot",
         "role": "proposed", "date": "2026-04-29", "outcome": "passed", "term": "current"},
        {"council_file": "24-0947", "title": "Protected Bicycle Lane Maintenance / Street Sweepers / Equipment and Personnel",
         "role": "proposed", "date": "2024-08-16", "outcome": "passed", "term": "current"},
        {"council_file": "26-0617", "title": "Sam Watson Way / 80th Street / Main Street / Permanent Ceremonial Signage",
         "role": "seconded", "date": "2026-04-24", "outcome": "passed", "term": "current"},
    ],
    "cd15-official": [
        {"council_file": "26-0686", "title": "Additional Beautification Services / Council District 15 / General City Purposes Fund",
         "role": "proposed", "date": "2026-05-06", "outcome": "passed", "term": "current"},
        {"council_file": "26-0733", "title": "McCoy Avenue / Fencing Project / Council District 15 / General City Purposes Fund / General Services Fund",
         "role": "proposed", "date": "2026-05-15", "outcome": "passed", "term": "current"},
        {"council_file": "26-0864", "title": "Strengthen Emergency Preparedness and Response Capabilities / Pre-Incident Vendor Qualification Programs / Emergency Response Agreements / Port Related Disasters",
         "role": "proposed", "date": "2026-06-10", "outcome": "pending", "term": "current"},
        {"council_file": "26-1065", "title": "Community Beautification Efforts and Clean Team Services / Council District 14 / Los AngelesConservation Corps",
         "role": "seconded", "date": "2026-08-04", "outcome": "pending", "term": "current"},
        {"council_file": "26-0968", "title": "Meet and Confer Obligations / Los Angeles Police Department Charter Amendment",
         "role": "seconded", "date": "2026-06-30", "outcome": "passed", "term": "current"},
    ],
    "cd3-official": [
        {"council_file": "26-1078", "title": "Additional Police Services / AB1290 Fund / Council District 3 / Police Fund",
         "role": "proposed", "date": "2026-08-05", "outcome": "pending", "term": "current"},
        {"council_file": "26-0071-S1", "title": "Permanent Supportive Housing Projects / Elderberry and the Nova / 2026-27 Street Strategies / Supplemental Funding / Council District 3",
         "role": "proposed", "date": "2026-06-30", "outcome": "passed", "term": "current"},
        {"council_file": "25-0863", "title": "Los Angeles Municipal Code Section 56.16 / Repeal",
         "role": "proposed", "date": "2025-08-01", "outcome": "pending", "term": "current"},
        {"council_file": "25-0916", "title": "Interim Control Ordinance / Tobacco, Nicotine, and Related Products / Prohibition of Establishment or Expansion / Operations Near Sensitive Uses",
         "role": "seconded", "date": "2025-08-12", "outcome": "passed", "term": "current"},
        {"council_file": "26-2000", "title": "2026 City Council Standing Committees / New Committee Structure",
         "role": "seconded", "date": "2026-08-04", "outcome": "pending", "term": "current"},
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


def source_url_for(council_file: str):
    """Primary-source URL for one record item, or None when none is verified.

    Council files resolve to their own CFMS record page. Mayoral Executive
    Directives and Emergency Executive Orders ("ED-9", "EO-1") are published as
    individual PDFs on mayor.lacity.gov under no URL pattern we've been able to
    verify, so they get no per-item link and fall back to the source note that
    the UI renders under the table.
    """
    council_file = (council_file or "").strip()
    if COUNCIL_FILE_PATTERN.match(council_file):
        return CFMS_VIEWRECORD.format(council_file=council_file)
    return None


def build_record(official_id: str) -> None:
    out_path = ROOT / "data" / "officials" / official_id / "record.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    items = RECORDS.get(official_id)
    if items is None:
        raise NotImplementedError(f"No curated record data for {official_id}")
    items = [
        dict(item, source_url=source_url_for(item.get("council_file")))
        for item in items
    ]
    payload = {
        "official_id": official_id,
        "source": SOURCES.get(official_id, DEFAULT_SOURCE),
        "items": items,
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n")


def main() -> None:
    officials = json.loads(OFFICIALS_INDEX.read_text())
    for official in officials:
        build_record(official["id"])


if __name__ == "__main__":
    main()
