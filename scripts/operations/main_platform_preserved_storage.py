#!/usr/bin/env python3
"""Narrow, evidence-bound attestation of the preserved pre-shared storage directory.

After the reviewed storage switch (main_platform_storage_switch.py) a candidate release holds:

    apps/platform/storage                          -> symlink to /home/kmjprod/shared/storage
    apps/platform/storage.pre-shared-<UTC stamp>/  -> the original, frozen, tracked-placeholder tree

Git reports the second path as untracked, which would fail every "candidate is a clean exact checkout" gate.
A blanket ignore would hide anything an attacker (or a bug) drops into the release, so this module exempts ONE
exact directory name, and only when ALL of the following hold:

  * exactly one entry named storage.pre-shared-<stamp> exists, and it is a real directory (never a symlink),
    owned by a trusted uid, not group/world writable;
  * a CLOSED root journal receipt for this exact app dir records begin(kept == that name) .. verified .. complete,
    no rollback phases, and there is no open journal for the app dir (no transaction in flight);
  * the protected state directory and the receipt are owned by a trusted uid with no group/other access;
  * the directory CONTENT still hashes to the persistent-file plan id recorded in the journal (so a file added,
    changed or removed afterwards makes the attestation fail);
  * Git tracks nothing under that path (the exemption can never hide a tracked file).

Everything else stays under ordinary exact-HEAD Git status. This module only reads.

CLI: main_platform_preserved_storage.py <candidate-release-dir> [--state-dir DIR]
  prints NONE | ATTESTED <name> | UNATTESTED <reason>; exit 0 for NONE/ATTESTED, 2 otherwise.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

DEFAULT_STATE_DIR = "/var/lib/kmj-main-platform-storage-switch"
sys.dont_write_bytecode = True  # root must not drop .pyc files into the release/checkout
PRE_PREFIX = "storage.pre-shared-"
NAME_RE = re.compile(r"\Astorage\.pre-shared-\d{8}T\d{6}Z\Z")
LINK_RE = re.compile(r"\A\.kmj-storage-link-[0-9a-f]{16}\Z")
PHASES = {"begin", "live_frozen", "both_frozen", "link_created", "exchanged", "preserved", "verified", "complete"}
ROLLBACK_PREFIX = "rollback_"
MAX_RECEIPT = 65536
HEX16 = re.compile(r"\A[0-9a-f]{16}\Z")


def _trusted(uid: int, extra: tuple[int, ...]) -> bool:
    return uid in (0, os.geteuid(), *extra)


def _protected_state_dir(path: Path, extra: tuple[int, ...]) -> str | None:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        return "STATE_DIR_MISSING"
    try:
        info = os.fstat(fd)
    finally:
        os.close(fd)
    if not _trusted(info.st_uid, extra) or stat.S_IMODE(info.st_mode) & 0o077:
        return "STATE_DIR_NOT_PROTECTED"
    if str(path) != os.path.realpath(path):
        return "STATE_DIR_NOT_CANONICAL"
    cur = Path("/")
    for part in path.parent.parts[1:]:
        cur = cur / part
        try:
            anc = os.lstat(cur)
        except OSError:
            return "STATE_DIR_ANCESTOR_UNREADABLE"
        if anc.st_mode & 0o022 and not anc.st_mode & stat.S_ISVTX:
            return "STATE_DIR_ANCESTOR_WRITABLE"
    return None


def _read_receipt(state: Path, name: str, extra: tuple[int, ...]) -> list[dict] | None:
    """Strictly parse one journal file; None when unsafe or malformed (a torn/garbled receipt attests nothing)."""
    try:
        dfd = os.open(state, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        return None
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=dfd)
    except OSError:
        return None
    finally:
        os.close(dfd)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not _trusted(info.st_uid, extra)
                or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > MAX_RECEIPT):
            return None
        raw = os.read(fd, MAX_RECEIPT + 1)
    finally:
        os.close(fd)
    if not raw.endswith(b"\n"):
        return None  # unterminated tail: not a closed, complete receipt
    out: list[dict] = []
    try:
        for line in raw.decode("utf-8", "strict").splitlines():
            entry = json.loads(line)
            if (not isinstance(entry, dict) or not isinstance(entry.get("t"), int)
                    or not (entry.get("phase") in PHASES or str(entry.get("phase")).startswith(ROLLBACK_PREFIX))):
                return None
            for key in ("kept",):
                if key in entry and not (isinstance(entry[key], str) and NAME_RE.match(entry[key])):
                    return None
            if "link" in entry and not (isinstance(entry["link"], str) and LINK_RE.match(entry["link"])):
                return None
            for key in ("plan", "shared_plan"):
                if key in entry and not (isinstance(entry[key], str) and HEX16.match(entry[key])):
                    return None
            out.append(entry)
    except (ValueError, RecursionError):
        return None
    return out or None


def _switch_module():
    path = Path(__file__).resolve().with_name("main_platform_storage_switch.py")
    spec = importlib.util.spec_from_file_location("kmj_storage_switch_for_attest", path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _tracked_under(candidate: Path, rel: str) -> bool | None:
    try:
        result = subprocess.run(
            ["git", "-c", f"safe.directory={candidate}", "-c", "core.fsmonitor=false", "-C", str(candidate),
             "ls-files", "-z", "--", rel],
            check=False, capture_output=True, timeout=60,
            env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "GIT_CONFIG_NOSYSTEM": "1",
                 "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"})
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return bool(result.stdout)


def attest(candidate: Path, state_dir: str | Path = DEFAULT_STATE_DIR,
           extra_trusted_uids: tuple[int, ...] = ()) -> tuple[str, str | None]:
    """Return ("NONE", None) | ("ATTESTED", name) | ("UNATTESTED", reason)."""
    app = Path(candidate) / "apps/platform"
    try:
        names = sorted(n for n in os.listdir(app) if n.startswith(PRE_PREFIX))
    except OSError:
        return "UNATTESTED", "APP_DIR_UNREADABLE"
    if not names:
        return "NONE", None
    if len(names) != 1:
        return "UNATTESTED", "MULTIPLE_PRESERVED_ENTRIES"
    name = names[0]
    if not NAME_RE.match(name):
        return "UNATTESTED", "PRESERVED_NAME_INVALID"
    try:
        info = os.lstat(app / name)
    except OSError:
        return "UNATTESTED", "PRESERVED_UNREADABLE"
    if (not stat.S_ISDIR(info.st_mode) or not _trusted(info.st_uid, extra_trusted_uids)
            or info.st_mode & 0o022):
        return "UNATTESTED", "PRESERVED_NOT_A_TRUSTED_DIRECTORY"

    state = Path(state_dir)
    problem = _protected_state_dir(state, extra_trusted_uids)
    if problem:
        return "UNATTESTED", problem
    key = hashlib.sha256(os.path.realpath(app).encode()).hexdigest()[:12]
    try:
        files = os.listdir(state)
    except OSError:
        return "UNATTESTED", "STATE_DIR_UNREADABLE"
    if f"{key}.journal" in files:
        return "UNATTESTED", "OPEN_JOURNAL_TRANSACTION_IN_FLIGHT"
    receipts = sorted(n for n in files if n.startswith(f"{key}.journal.done-"))
    good = None
    for receipt in receipts:
        entries = _read_receipt(state, receipt, extra_trusted_uids)
        if entries is None:
            continue
        phases = [e["phase"] for e in entries]
        if any(e["phase"].startswith(ROLLBACK_PREFIX) and e.get("kept") == name for e in entries):
            return "UNATTESTED", "ROLLBACK_RECORDED_FOR_PRESERVED_DIR"
        kept = next((e.get("kept") for e in entries if e["phase"] == "begin"), None)
        if kept != name:
            continue
        if (phases[0] == "begin" and phases[-1] == "complete" and "verified" in phases
                and phases.index("verified") < len(phases) - 1):
            good = entries
    if good is None:
        return "UNATTESTED", "NO_COMPLETE_CLOSED_JOURNAL_RECEIPT_FOR_NAME"
    plan = next((e.get("plan") for e in good if e["phase"] == "begin"), None)
    if plan is None:
        return "UNATTESTED", "JOURNAL_HAS_NO_PLAN_IDENTITY"

    try:
        sw = _switch_module()
        if sw is None:
            return "UNATTESTED", "CONTENT_CHECK_UNAVAILABLE"
        fd = sw.open_dir(app / name)
        try:
            dirs: dict = {}
            current = sw.plan_id(sw.scan(fd, dirs), dirs)
        finally:
            os.close(fd)
    except BaseException as exc:  # Blocked/OSError/anything: an unreadable tree attests nothing
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        return "UNATTESTED", "CONTENT_CHECK_FAILED"
    if current != plan:
        return "UNATTESTED", "PRESERVED_CONTENT_DIFFERS_FROM_JOURNAL"

    tracked = _tracked_under(Path(candidate), f"apps/platform/{name}")
    if tracked is None:
        return "UNATTESTED", "GIT_LS_FILES_UNVERIFIED"
    if tracked:
        return "UNATTESTED", "TRACKED_FILES_UNDER_PRESERVED_PATH"
    return "ATTESTED", name


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--state-dir=")]
    state = next((a.split("=", 1)[1] for a in argv if a.startswith("--state-dir=")), DEFAULT_STATE_DIR)
    if len(args) != 1:
        print("UNATTESTED USAGE")
        return 2
    status, detail = attest(Path(args[0]), state)
    print(status if detail is None else f"{status} {detail}")
    return 0 if status in ("NONE", "ATTESTED") else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
