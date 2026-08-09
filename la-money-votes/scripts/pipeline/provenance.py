"""Canonical provenance block shared by funding.json and record.json rows.

Every factual record in this pipeline (one contribution, one legislative
item) carries a `provenance` object with the same shape, per CONTRACT.md:

    {
      "source_name": str,
      "source_url": str | null,
      "retrieved_at": "YYYY-MM-DD",
      "reporting_period": {"from": "YYYY-MM-DD"|null, "to": "YYYY-MM-DD"|null} | null,
      "meeting_date": "YYYY-MM-DD" | null,
      "record_id": str | null,
      "methodology_version": str
    }

`reporting_period` is used for funding rows (the disclosure period a
contribution was reported in). `meeting_date` is used for record rows (the
Council/committee meeting or directive date). A row only fills in whichever
of the two applies to its record type; the other stays null.
"""

from __future__ import annotations

METHODOLOGY_VERSION = "1.0"


def make_provenance(
    source_name: str,
    source_url=None,
    retrieved_at: str = "",
    reporting_period=None,
    meeting_date=None,
    record_id=None,
    methodology_version: str = METHODOLOGY_VERSION,
) -> dict:
    return {
        "source_name": source_name,
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "reporting_period": reporting_period,
        "meeting_date": meeting_date,
        "record_id": record_id,
        "methodology_version": methodology_version,
    }
