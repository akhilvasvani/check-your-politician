"""Step 4C publication: run ids, the build lock, the publication journal,
backups, publish, rollback, recovery and cleanup.

Everything here works relative to a `data_root` (la-money-votes/data) passed
in by the caller, so the test suite can point it at a temporary repository.

Layout (all gitignored under data/raw/):
    data/raw/.build.lock                 flock()ed by the active run
    data/raw/.publish/<run_id>/staging/  officials/<id>/{funding,record}.json, freshness.json
    data/raw/.publish/<run_id>/backup/   copies of every published file replaced by the run
    data/raw/.publish/<run_id>/journal.json

Guarantees and limits:
- Every single-file replacement is an os.replace() (atomic per file). A
  multi-file publication is NOT crash-atomic: a process killed between
  replacements leaves a mixed tree until `build_all.py --recover` rolls it
  back from the journal and backups.
- Backups are copied and verified before the first replacement; freshness.json
  is replaced last and restored first.
- Rollback never overwrites a file whose content matches neither the recorded
  prior nor the recorded new hash, and never consumes the only copy of a
  backup (restores are copies). Recovery is repeatable.
- Journals are validated before recovery touches anything. Every path is
  derived from the target name (never taken from the journal verbatim) and
  must stay inside data/ without symlinks.
- The lock is fcntl.flock() on data/raw/.build.lock: the kernel releases it
  when the owning process exits or dies, so there is no stale-lock state, and
  the lock file is never deleted. POSIX only (Linux/macOS), local filesystems.
- Containment: before the lock is taken (and so before any build, recovery,
  verification or cleanup), data/, data/raw/ and data/raw/.publish/ must be
  real directories and .build.lock a regular file, none of them symlinks;
  the lock file is opened with O_NOFOLLOW. These are point-in-time checks
  that stop a misconfigured or planted symlink layout. They do not protect
  against another process concurrently swapping directories for symlinks
  while a run is in progress.
- The journal records the prior hash of every file in the snapshot
  (replaced and retained). Rollback is complete only when every one of them
  is back at its prior hash; otherwise the run stays RECOVERY_REQUIRED.
"""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pipeline import atomic_io

JOURNAL_VERSION = 1
JOURNAL_NAME = "journal.json"

STATE_PREPARED = "PREPARED"
STATE_PUBLISHING = "PUBLISHING"
STATE_PUBLISHED = "PUBLISHED"
STATE_VERIFIED = "VERIFIED"
STATE_ROLLING_BACK = "ROLLING_BACK"
STATE_ROLLED_BACK = "ROLLED_BACK"
STATE_RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
STATES = frozenset(
    {
        STATE_PREPARED,
        STATE_PUBLISHING,
        STATE_PUBLISHED,
        STATE_VERIFIED,
        STATE_ROLLING_BACK,
        STATE_ROLLED_BACK,
        STATE_RECOVERY_REQUIRED,
    }
)

# Report `publication` values.
PUB_VERIFIED = "verified"
PUB_DRY_RUN = "dry_run"
PUB_NOT_ATTEMPTED = "not_attempted"
PUB_ROLLED_BACK = "rolled_back"
PUB_RECOVERY_REQUIRED = "recovery_required"

CLEANUP_INCOMPLETE = "CLEANUP_INCOMPLETE"

LOCK_BUSY_EXIT = 75  # EX_TEMPFAIL: another build/recovery holds the lock

RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_OFFICIAL_TARGET_RE = re.compile(r"^officials/([^/]+)/(funding|record)\.json$")
FRESHNESS_TARGET = "freshness.json"

_ENTRY_KEYS = {"target", "had_prior", "prior_sha256", "new_sha256", "staged", "backup"}
_JOURNAL_KEYS = {"journal_version", "run_id", "state", "updated_at", "entries", "manifest", "prior_manifest"}


class PublishError(Exception):
    pass


class UnsafeLayout(PublishError):
    """data/, data/raw/, data/raw/.publish/ or .build.lock is a symlink or
    the wrong kind of file. Raised before anything is changed."""


class LockBusy(Exception):
    def __init__(self, holder):
        super().__init__(f"build lock is held by {holder}")
        self.holder = holder


# --- paths -------------------------------------------------------------------


def raw_dir(data_root: Path) -> Path:
    return Path(data_root) / "raw"


def publish_dir(data_root: Path) -> Path:
    return raw_dir(data_root) / ".publish"


def lock_path(data_root: Path) -> Path:
    return raw_dir(data_root) / ".build.lock"


def run_dir(data_root: Path, run_id: str) -> Path:
    return publish_dir(data_root) / run_id


def layout_problems(data_root: Path) -> list:
    """Problems with the directories every entry point writes under. Checked
    before the lock is opened, so nothing is created or changed when a
    problem is found."""
    data_root = Path(data_root)
    problems = []
    if data_root.is_symlink() or not data_root.is_dir():
        return [f"{data_root}: data root must be a real directory, not a symlink"]
    raw, pdir, lock = raw_dir(data_root), publish_dir(data_root), lock_path(data_root)
    for path, label in ((raw, "data/raw"), (pdir, "data/raw/.publish")):
        if os.path.lexists(path) and (path.is_symlink() or not path.is_dir()):
            problems.append(f"{label} must be a real directory, not a symlink or file")
            return problems  # nothing below it can be trusted
    if os.path.lexists(lock) and (lock.is_symlink() or not lock.is_file()):
        problems.append("data/raw/.build.lock must be a regular file, not a symlink")
    return problems


def new_run_id(now=None) -> str:
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return f"local-{moment:%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"


def validate_run_id(run_id) -> list:
    if not isinstance(run_id, str) or not RUN_ID_RE.match(run_id):
        return [f"invalid run id {run_id!r}: must match {RUN_ID_RE.pattern}"]
    return []


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _current_sha(path: Path):
    """sha256 of a regular file, or None if it does not exist."""
    if not os.path.lexists(path):
        return None
    if Path(path).is_symlink() or not Path(path).is_file():
        return "<not-a-regular-file>"
    return sha256_file(path)


def _no_symlinks_within(base: Path, path: Path) -> bool:
    """True if `path` lies inside `base` and no existing component between
    them (including `path`) is a symlink."""
    base = Path(base)
    path = Path(path)
    try:
        rel = path.relative_to(base)
    except ValueError:
        return False
    if base.is_symlink():
        return False
    current = base
    for part in rel.parts:
        if part in ("", ".", ".."):
            return False
        current = current / part
        if current.is_symlink():
            return False
    try:
        return path.resolve(strict=False).is_relative_to(base.resolve(strict=False))
    except OSError:
        return False


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


# Small indirections so failure-injection tests can patch one operation.
def _replace(src: Path, dst: Path) -> None:
    os.replace(src, dst)


def _copy_file(src: Path, dst: Path) -> None:
    """Copy bytes src -> dst via a temp file in dst's directory + os.replace,
    fsynced. Never moves src."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(dst.parent), prefix=f".{dst.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as out, open(src, "rb") as inp:
            shutil.copyfileobj(inp, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, dst)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    fsync_dir(dst.parent)


def _unlink(path: Path) -> None:
    os.unlink(path)


def _remove_tree(path: Path) -> None:
    shutil.rmtree(path)


# --- lock ----------------------------------------------------------------------


class RunLock:
    """Exclusive, non-blocking flock() on data/raw/.build.lock.

    Ownership: only the process holding the flock owns the lock; holder
    metadata (run id, pid, mode) is written only after the flock is acquired
    and truncated before release. A process that is denied the lock changes
    nothing. The kernel drops the flock if the owner dies, so a killed run
    never leaves a lock behind; the file itself is never deleted."""

    def __init__(self, data_root: Path, run_id: str, mode: str):
        self.data_root = Path(data_root)
        self.path = lock_path(data_root)
        self.run_id = run_id
        self.mode = mode
        self._fd = None

    def acquire(self) -> "RunLock":
        problems = layout_problems(self.data_root)
        if problems:
            raise UnsafeLayout("; ".join(problems))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o644)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise UnsafeLayout("data/raw/.build.lock must be a regular file, not a symlink") from None
            raise
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise UnsafeLayout("data/raw/.build.lock must be a regular file")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(fd)
            if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):
                raise LockBusy(read_lock_holder(self.path)) from None
            raise
        except BaseException:
            os.close(fd)
            raise
        meta = json.dumps(
            {"run_id": self.run_id, "pid": os.getpid(), "mode": self.mode, "acquired_at": _utc_now()}
        ).encode()
        try:
            os.ftruncate(fd, 0)
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, meta + b"\n")
            os.fsync(fd)
        except BaseException:
            # Not owned: drop the flock and the descriptor before re-raising.
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
            raise
        self._fd = fd
        return self

    def release(self) -> None:
        if self._fd is None:
            return
        try:
            os.ftruncate(self._fd, 0)
        finally:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()
        return False


def read_lock_holder(path: Path) -> str:
    """Best-effort description of the current holder (diagnostics only)."""
    try:
        data = json.loads(Path(path).read_text() or "{}")
        return f"run {data.get('run_id')!r} (pid {data.get('pid')}, mode {data.get('mode')})"
    except (OSError, ValueError):
        return "another process"


# --- journal -------------------------------------------------------------------


def journal_path(rdir: Path) -> Path:
    return Path(rdir) / JOURNAL_NAME


def write_journal(rdir: Path, journal: dict, state: str) -> None:
    journal["state"] = state
    journal["updated_at"] = _utc_now()
    atomic_io.atomic_write_json(journal_path(rdir), journal)
    fsync_dir(rdir)


def _target_paths(data_root: Path, rdir: Path, target: str):
    return (
        Path(data_root) / target,
        Path(rdir) / "staging" / target,
        Path(rdir) / "backup" / target,
    )


def _valid_target(target, official_ids) -> bool:
    if target == FRESHNESS_TARGET:
        return True
    if not isinstance(target, str):
        return False
    m = _OFFICIAL_TARGET_RE.match(target)
    return bool(m) and m.group(1) in official_ids


def validate_journal(journal, rdir: Path, data_root: Path, official_ids) -> list:
    """Every problem that makes a journal unsafe to act on. Recovery refuses
    to change anything when this returns problems."""
    problems = []
    rdir = Path(rdir)
    data_root = Path(data_root)
    official_ids = set(official_ids)
    if not isinstance(journal, dict):
        return ["journal: top level must be an object"]
    keys = set(journal)
    if keys != _JOURNAL_KEYS:
        return [f"journal: keys must be exactly {sorted(_JOURNAL_KEYS)}, got {sorted(keys)}"]
    if journal["journal_version"] != JOURNAL_VERSION:
        problems.append(f"journal: unsupported journal_version {journal['journal_version']!r}")
    run_id = journal["run_id"]
    problems.extend(f"journal: {p}" for p in validate_run_id(run_id))
    if run_id != rdir.name:
        problems.append(f"journal: run_id {run_id!r} does not match its directory {rdir.name!r}")
    if journal["state"] not in STATES:
        problems.append(f"journal: unknown state {journal['state']!r}")
    if not _no_symlinks_within(publish_dir(data_root), rdir):
        problems.append("journal: run directory is not a plain directory inside data/raw/.publish")
    entries = journal["entries"]
    if not isinstance(entries, list) or not entries:
        return problems + ["journal: entries must be a non-empty list"]
    seen = set()
    for i, entry in enumerate(entries):
        where = f"journal: entries[{i}]"
        if not isinstance(entry, dict) or set(entry) != _ENTRY_KEYS:
            problems.append(f"{where}: keys must be exactly {sorted(_ENTRY_KEYS)}")
            continue
        target = entry["target"]
        if not _valid_target(target, official_ids):
            problems.append(f"{where}: unsafe or unknown target {target!r}")
            continue
        if target in seen:
            problems.append(f"{where}: duplicate target {target!r}")
        seen.add(target)
        had_prior = entry["had_prior"]
        if not isinstance(had_prior, bool):
            problems.append(f"{where}: had_prior must be a boolean")
            continue
        if entry["staged"] != f"staging/{target}":
            problems.append(f"{where}: staged path must be 'staging/{target}'")
        expected_backup = f"backup/{target}" if had_prior else None
        if entry["backup"] != expected_backup:
            problems.append(f"{where}: backup path must be {expected_backup!r}")
        if not (isinstance(entry["new_sha256"], str) and _SHA_RE.match(entry["new_sha256"])):
            problems.append(f"{where}: new_sha256 must be a sha256 hex digest")
        prior = entry["prior_sha256"]
        if had_prior:
            if not (isinstance(prior, str) and _SHA_RE.match(prior)):
                problems.append(f"{where}: prior_sha256 must be a sha256 hex digest when had_prior")
        elif prior is not None:
            problems.append(f"{where}: prior_sha256 must be null when not had_prior")
        published, staged, backup = _target_paths(data_root, rdir, target)
        if not _no_symlinks_within(data_root, published):
            problems.append(f"{where}: target path escapes data/ or crosses a symlink")
        if not _no_symlinks_within(rdir, staged) or not _no_symlinks_within(rdir, backup):
            problems.append(f"{where}: staging/backup path escapes the run directory or crosses a symlink")
    targets = [e.get("target") for e in entries if isinstance(e, dict)]
    if targets.count(FRESHNESS_TARGET) != 1 or targets[-1] != FRESHNESS_TARGET:
        problems.append("journal: freshness.json must appear exactly once, as the last entry")
    manifest = journal["manifest"]
    if not isinstance(manifest, dict) or FRESHNESS_TARGET not in manifest:
        problems.append("journal: manifest must be an object that includes freshness.json")
    else:
        for target, sha in manifest.items():
            if not _valid_target(target, official_ids) or not (isinstance(sha, str) and _SHA_RE.match(sha)):
                problems.append(f"journal: invalid manifest entry {target!r}")
        for entry in entries:
            if isinstance(entry, dict) and entry.get("target") in manifest:
                if manifest[entry["target"]] != entry.get("new_sha256"):
                    problems.append(f"journal: manifest hash for {entry['target']!r} differs from its entry")
            elif isinstance(entry, dict):
                problems.append(f"journal: replaced target {entry.get('target')!r} missing from manifest")
    prior = journal["prior_manifest"]
    if not isinstance(prior, dict) or not isinstance(manifest, dict) or set(prior) != set(manifest):
        problems.append("journal: prior_manifest must be an object with exactly the manifest's targets")
        return problems
    by_target = {e.get("target"): e for e in entries if isinstance(e, dict)}
    for target, sha in prior.items():
        if not (sha is None or (isinstance(sha, str) and _SHA_RE.match(sha))):
            problems.append(f"journal: invalid prior_manifest entry {target!r}")
        elif target in by_target:
            if by_target[target].get("prior_sha256") != sha:
                problems.append(f"journal: prior_manifest hash for {target!r} differs from its entry")
        elif sha != manifest.get(target):
            problems.append(f"journal: retained target {target!r} must have the same prior and manifest hash")
    return problems


def load_journal(rdir: Path):
    """(journal, problem) without raising for unreadable/malformed JSON."""
    path = journal_path(rdir)
    try:
        raw = path.read_bytes()
        return json.loads(raw.decode("utf-8")), None
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return None, f"journal could not be read: {type(exc).__name__}: {exc}"


def unresolved_runs(data_root: Path) -> list:
    """Problems that must block a new build: any journal, or any entry in
    data/raw/.publish that is not a plain, validly named run directory.
    A journal-less run directory is an abandoned staging area (nothing was
    published from it) and does not block."""
    problems = layout_problems(data_root)
    if problems:
        return problems
    pdir = publish_dir(data_root)
    if not pdir.exists():
        return problems
    if pdir.is_symlink() or not pdir.is_dir():
        return [f"{pdir}: not a plain directory"]
    for child in sorted(pdir.iterdir()):
        if child.is_symlink() or not child.is_dir() or validate_run_id(child.name):
            problems.append(f"unexpected entry in data/raw/.publish: {child.name!r} (remove it manually)")
            continue
        if os.path.lexists(journal_path(child)):
            journal, problem = load_journal(child)
            state = journal.get("state") if isinstance(journal, dict) else None
            problems.append(f"unresolved publication journal for run {child.name!r} (state {state or problem!r})")
    return problems


# --- publish ---------------------------------------------------------------------


class PublishResult:
    def __init__(self):
        self.publication = PUB_NOT_ATTEMPTED
        self.replaced = {}  # target -> {"had_prior", "prior_sha256", "new_sha256"}
        self.manifest = {}  # target -> sha256 for the whole effective snapshot
        self.problems = []
        self.warnings = []
        self.state = None

    def to_dict(self):
        return {
            "publication": self.publication,
            "journal_state": self.state,
            "replaced_files": self.replaced,
            "snapshot_manifest": self.manifest,
            "publication_problems": self.problems,
            "publication_warnings": self.warnings,
        }


def target_for(official_id: str, dataset: str) -> str:
    return f"officials/{official_id}/{dataset}.json"


def build_manifest(snapshot) -> dict:
    """target -> sha256 for every required official output in the effective
    snapshot (staged or retained) plus the staged freshness.json."""
    manifest = {}
    for (official_id, dataset), path in sorted(snapshot.effective_paths.items()):
        manifest[target_for(official_id, dataset)] = sha256_file(path)
    manifest[FRESHNESS_TARGET] = sha256_file(Path(snapshot.stage_root) / FRESHNESS_TARGET)
    return manifest


def publish_snapshot(snapshot, data_root: Path, rdir: Path, run_id: str, verify):
    """Publish a validated StagedSnapshot. `verify(manifest)` re-validates the
    live tree against the full snapshot manifest and returns problems. Returns a PublishResult; never raises for
    ordinary I/O failures (they become rolled_back / recovery_required)."""
    data_root = Path(data_root)
    rdir = Path(rdir)
    result = PublishResult()
    targets = [target_for(o, d) for o, d in sorted(snapshot.staged)] + [FRESHNESS_TARGET]

    # 1. Manifest and entries. Retained files are hashed now; publication
    #    verification later proves they are still exactly these bytes.
    try:
        result.manifest = build_manifest(snapshot)
        entries = []
        for target in targets:
            published, staged, backup = _target_paths(data_root, rdir, target)
            if not _no_symlinks_within(data_root, published):
                raise PublishError(f"{target}: target path crosses a symlink")
            prior = _current_sha(published)
            if prior == "<not-a-regular-file>":
                raise PublishError(f"{target}: published path is not a regular file")
            entries.append(
                {
                    "target": target,
                    "had_prior": prior is not None,
                    "prior_sha256": prior,
                    "new_sha256": sha256_file(staged),
                    "staged": f"staging/{target}",
                    "backup": f"backup/{target}" if prior is not None else None,
                }
            )
        # 2. Backups: copied and verified before any replacement.
        for entry in entries:
            if not entry["had_prior"]:
                continue
            published, _, backup = _target_paths(data_root, rdir, entry["target"])
            _copy_file(published, backup)
            if sha256_file(backup) != entry["prior_sha256"]:
                raise PublishError(f"{entry['target']}: backup does not match the published file")
            if sha256_file(published) != entry["prior_sha256"]:
                raise PublishError(f"{entry['target']}: published file changed while backing up")
    except (OSError, PublishError) as exc:
        result.problems.append(f"backup preparation failed: {exc}")
        _discard_run_dir(rdir, result)
        return result

    # The whole previous snapshot: replaced targets at their prior hash (or
    # absent), retained targets at the hash they are served with.
    prior_manifest = dict(result.manifest)
    prior_manifest.update({e["target"]: e["prior_sha256"] for e in entries})
    journal = {
        "journal_version": JOURNAL_VERSION,
        "run_id": run_id,
        "state": STATE_PREPARED,
        "updated_at": _utc_now(),
        "entries": entries,
        "manifest": result.manifest,
        "prior_manifest": prior_manifest,
    }
    try:
        write_journal(rdir, journal, STATE_PREPARED)
        write_journal(rdir, journal, STATE_PUBLISHING)
    except OSError as exc:
        result.problems.append(f"could not write the publication journal: {exc}")
        # Nothing has been replaced; if a journal exists it is PREPARED or
        # PUBLISHING with every target still at its prior hash, which
        # recovery handles. Try to clean up now.
        _discard_run_dir(rdir, result)
        return result

    # 3. Replace: data files in order, freshness.json last.
    try:
        for entry in entries:
            published, staged, _ = _target_paths(data_root, rdir, entry["target"])
            published.parent.mkdir(parents=True, exist_ok=True)
            _replace(staged, published)
            fsync_dir(published.parent)
            result.replaced[entry["target"]] = {
                "had_prior": entry["had_prior"],
                "prior_sha256": entry["prior_sha256"],
                "new_sha256": entry["new_sha256"],
            }
        write_journal(rdir, journal, STATE_PUBLISHED)
    except OSError as exc:
        result.problems.append(f"replacement failed: {exc}")
        result.replaced = {}
        return _rollback_into(result, journal, rdir, data_root)

    # 4. Post-publication verification, then the commit point.
    try:
        problems = verify(result.manifest)
    except Exception as exc:  # noqa: BLE001 - any verification error means not verified
        problems = [f"verification raised {type(exc).__name__}: {exc}"]
    if problems:
        result.problems.extend(f"post-publication verification: {p}" for p in problems)
        result.replaced = {}
        return _rollback_into(result, journal, rdir, data_root)
    try:
        write_journal(rdir, journal, STATE_VERIFIED)
    except OSError as exc:
        result.problems.append(f"could not record VERIFIED: {exc}")
        result.replaced = {}
        return _rollback_into(result, journal, rdir, data_root)
    result.publication = PUB_VERIFIED
    result.state = STATE_VERIFIED

    # 5. Cleanup (repeatable). A failure leaves the VERIFIED journal behind,
    #    which blocks the next build until --recover finishes cleanup.
    cleanup_problems = cleanup_run(rdir)
    if cleanup_problems:
        result.warnings.append(CLEANUP_INCOMPLETE)
        result.problems.extend(f"cleanup: {p}" for p in cleanup_problems)
    else:
        result.state = None
    return result


def _discard_run_dir(rdir: Path, result: PublishResult) -> None:
    """Nothing was replaced: remove staging/backups/journal of this run."""
    problems = cleanup_run(rdir)
    result.problems.extend(f"cleanup: {p}" for p in problems)
    result.state = None if not problems else "UNCLEANED"


def _rollback_into(result, journal, rdir, data_root):
    state, problems = rollback(journal, rdir, data_root)
    result.problems.extend(problems)
    result.state = state
    if state == STATE_ROLLED_BACK:
        result.publication = PUB_ROLLED_BACK
        cleanup_problems = cleanup_run(rdir)
        if cleanup_problems:
            result.problems.extend(f"cleanup: {p}" for p in cleanup_problems)
            result.warnings.append(CLEANUP_INCOMPLETE)
        else:
            result.state = None
    else:
        result.publication = PUB_RECOVERY_REQUIRED
    return result


# --- rollback / recovery / cleanup ----------------------------------------------


def rollback(journal: dict, rdir: Path, data_root: Path):
    """Restore every target to its prior state (freshness.json first).
    Returns (final_state, problems). Repeatable: each target is classified by
    hash before anything is touched; restores are copies, so backups survive
    a failed or interrupted rollback."""
    rdir = Path(rdir)
    data_root = Path(data_root)
    problems = []
    try:
        write_journal(rdir, journal, STATE_ROLLING_BACK)
    except OSError as exc:
        return STATE_RECOVERY_REQUIRED, [f"could not record ROLLING_BACK: {exc}"]

    for entry in reversed(journal["entries"]):
        target = entry["target"]
        published, _, backup = _target_paths(data_root, rdir, target)
        try:
            current = _current_sha(published)
            if entry["had_prior"]:
                if current == entry["prior_sha256"]:
                    continue  # never replaced, or already restored
                if current is not None and current != entry["new_sha256"]:
                    problems.append(f"{target}: content matches neither the prior nor the new version; not touched")
                    continue
                if not backup.is_file() or backup.is_symlink() or sha256_file(backup) != entry["prior_sha256"]:
                    problems.append(f"{target}: backup missing or does not match the recorded prior hash")
                    continue
                _copy_file(backup, published)
                if sha256_file(published) != entry["prior_sha256"]:
                    problems.append(f"{target}: restored file does not match the prior hash")
            else:
                if current is None:
                    continue  # never published, or already removed
                if current != entry["new_sha256"]:
                    problems.append(f"{target}: content matches neither the prior nor the new version; not touched")
                    continue
                _unlink(published)
                fsync_dir(published.parent)
        except OSError as exc:
            problems.append(f"{target}: restore failed: {exc}")

    # Complete only if the whole previous snapshot is back, including files
    # this run never replaced. Retained files are never written here.
    replaced_targets = {e["target"] for e in journal["entries"]}
    for target, prior in sorted(journal["prior_manifest"].items()):
        if target in replaced_targets:
            continue
        try:
            current = _current_sha(Path(data_root) / target)
        except OSError as exc:
            current = f"<unreadable: {exc}>"
        if current != prior:
            problems.append(
                f"{target}: retained file does not match its prior hash {prior} (now {current}); not touched"
            )

    if problems:
        try:
            write_journal(rdir, journal, STATE_RECOVERY_REQUIRED)
        except OSError as exc:
            problems.append(f"could not record RECOVERY_REQUIRED: {exc}")
        return STATE_RECOVERY_REQUIRED, problems
    try:
        write_journal(rdir, journal, STATE_ROLLED_BACK)
    except OSError as exc:
        return STATE_RECOVERY_REQUIRED, [f"could not record ROLLED_BACK: {exc}"]
    return STATE_ROLLED_BACK, []


def cleanup_run(rdir: Path) -> list:
    """Remove backups, then staging, then the journal, then the run dir.
    Repeatable: already-missing pieces are fine."""
    rdir = Path(rdir)
    problems = []
    for sub in ("backup", "staging"):
        path = rdir / sub
        if os.path.lexists(path):
            try:
                if path.is_symlink() or not path.is_dir():
                    _unlink(path)
                else:
                    _remove_tree(path)
            except OSError as exc:
                problems.append(f"could not remove {sub}/: {exc}")
    if problems:
        return problems  # keep the journal: it still describes what remains
    for leftover in sorted(rdir.glob(".*.tmp")) if rdir.exists() else []:
        try:
            _unlink(leftover)
        except OSError as exc:
            problems.append(f"could not remove {leftover.name}: {exc}")
    jpath = journal_path(rdir)
    if os.path.lexists(jpath):
        try:
            _unlink(jpath)
        except OSError as exc:
            return problems + [f"could not remove the journal: {exc}"]
    if rdir.exists():
        try:
            rdir.rmdir()
        except OSError as exc:
            problems.append(f"could not remove the run directory: {exc}")
    return problems


def recover_run(rdir: Path, data_root: Path, official_ids):
    """Resolve one run directory. Returns (outcome, problems) where outcome is
    'cleaned', 'rolled_back', 'refused' or 'recovery_required'."""
    rdir = Path(rdir)
    if not os.path.lexists(journal_path(rdir)):
        # Journal-less: staging (and possibly unverified backups) only;
        # nothing was published from it.
        problems = cleanup_run(rdir)
        return ("cleaned", []) if not problems else ("recovery_required", problems)
    journal, problem = load_journal(rdir)
    if problem:
        return "refused", [problem]
    problems = validate_journal(journal, rdir, data_root, official_ids)
    if problems:
        return "refused", problems
    state = journal["state"]
    if state in (STATE_VERIFIED, STATE_ROLLED_BACK):
        problems = cleanup_run(rdir)
        return ("cleaned", []) if not problems else ("recovery_required", problems)
    # PREPARED, PUBLISHING, PUBLISHED, ROLLING_BACK, RECOVERY_REQUIRED: not
    # committed -> roll back (a PREPARED journal finds every target at its
    # prior hash and changes nothing).
    final, problems = rollback(journal, rdir, data_root)
    if final != STATE_ROLLED_BACK:
        return "recovery_required", problems
    cleanup_problems = cleanup_run(rdir)
    if cleanup_problems:
        return "recovery_required", cleanup_problems
    return "rolled_back", []


def recover_all(data_root: Path, official_ids):
    """Resolve every run directory under data/raw/.publish. Returns a list of
    (name, outcome, problems). Entries that are not plain, validly named
    directories are refused and never touched."""
    problems = layout_problems(data_root)
    if problems:
        return [(str(raw_dir(data_root)), "refused", problems + ["nothing was touched"])]
    pdir = publish_dir(data_root)
    results = []
    if not pdir.exists():
        return results
    if pdir.is_symlink() or not pdir.is_dir():
        return [(str(pdir), "refused", ["data/raw/.publish is not a plain directory"])]
    for child in sorted(pdir.iterdir()):
        if child.is_symlink() or not child.is_dir() or validate_run_id(child.name):
            results.append((child.name, "refused", ["not a plain, validly named run directory; not touched"]))
            continue
        outcome, problems = recover_run(child, data_root, official_ids)
        results.append((child.name, outcome, problems))
    return results
