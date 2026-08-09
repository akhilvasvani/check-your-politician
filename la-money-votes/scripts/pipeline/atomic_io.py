"""Write-validated-or-don't-write helpers.

The one rule every builder in this pipeline follows: never let a partial or
malformed build overwrite a previously-committed, valid JSON file. That
means validating a payload BEFORE it touches disk, and writing via a
temp-file-then-rename so a crash mid-write can't leave a truncated file
either.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def atomic_write_json(path: Path, payload) -> None:
    """Write `payload` to `path` as pretty-printed JSON, atomically.

    Writes to a temp file in the same directory first, then os.replace()s it
    over the destination. os.replace is atomic on POSIX and Windows, so a
    reader (or a `git status`) never sees a half-written file, and a crash
    mid-write leaves the original file untouched.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def write_if_valid(path: Path, payload, problems: list) -> bool:
    """Write `payload` to `path` only if `problems` (from a validator) is empty.

    Returns True if the file was written, False if it was skipped because
    `problems` was non-empty — in which case any prior file at `path` is left
    exactly as it was. Callers are expected to have already appended any
    validation problems to `problems` before calling this.
    """
    if problems:
        return False
    atomic_write_json(path, payload)
    return True
