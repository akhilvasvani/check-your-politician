"""Machine-readable build report used by build_all.py and the CI/refresh
GitHub Actions workflows.

The scheduled refresh workflow embeds this report's summary directly in the
pull request body (updated officials, source-fetch results, record counts,
validation failures, unavailable sources) so a maintainer never has to dig
through Action logs to review a data-refresh PR.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class OfficialResult:
    official_id: str
    builder: str  # "funding" | "record"
    status: str  # "ok" | "failed" | "skipped"
    record_count: int = 0
    problems: list = field(default_factory=list)
    source_notes: list = field(default_factory=list)

    def to_dict(self):
        return {
            "official_id": self.official_id,
            "builder": self.builder,
            "status": self.status,
            "record_count": self.record_count,
            "problems": self.problems,
            "source_notes": self.source_notes,
        }


class BuildReport:
    def __init__(self):
        self.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.results: list[OfficialResult] = []
        self.unavailable_sources: list[str] = []
        self.fatal_errors: list[str] = []

    def add(self, result: OfficialResult) -> None:
        self.results.append(result)

    def add_unavailable_source(self, note: str) -> None:
        self.unavailable_sources.append(note)

    def add_fatal(self, message: str) -> None:
        self.fatal_errors.append(message)

    @property
    def ok(self) -> bool:
        """False if anything required failed. Skips alone don't fail the build."""
        if self.fatal_errors:
            return False
        return not any(r.status == "failed" for r in self.results)

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ok": self.ok,
            "results": [r.to_dict() for r in self.results],
            "unavailable_sources": self.unavailable_sources,
            "fatal_errors": self.fatal_errors,
            "summary": self.summary_line(),
        }

    def summary_line(self) -> str:
        ok_count = sum(1 for r in self.results if r.status == "ok")
        failed = [r for r in self.results if r.status == "failed"]
        skipped = [r for r in self.results if r.status == "skipped"]
        return (
            f"{ok_count} builder run(s) ok, {len(failed)} failed, "
            f"{len(skipped)} skipped, {len(self.unavailable_sources)} source(s) unavailable"
        )

    def write(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n")

    def to_markdown(self) -> str:
        """Rendered for the scheduled-refresh PR body."""
        lines = [f"**{self.summary_line()}**", ""]
        lines.append("| Official | Builder | Status | Records | Problems |")
        lines.append("| --- | --- | --- | --- | --- |")
        for r in self.results:
            problems = "; ".join(r.problems) if r.problems else "—"
            lines.append(f"| {r.official_id} | {r.builder} | {r.status} | {r.record_count} | {problems} |")
        if self.unavailable_sources:
            lines.append("")
            lines.append("**Unavailable sources:**")
            for note in self.unavailable_sources:
                lines.append(f"- {note}")
        if self.fatal_errors:
            lines.append("")
            lines.append("**Fatal errors:**")
            for err in self.fatal_errors:
                lines.append(f"- {err}")
        return "\n".join(lines)
