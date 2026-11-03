#!/usr/bin/env python3
"""KMJ-elite: one-pass READ-ONLY release-blocker audit, no secrets or mutation.

This is diagnostic evidence, NOT backup, restore, approval or release authority.
Run as root on the exact KMJ-elite host. No arguments, shell, SSH, network,
file modifications, service starts, symlink changes or privileged delegation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys

PROD_LINK = Path("/home/kmjprod/current")
STAGE_LINK = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
PROD_APPROVAL = Path("/etc/kmj-codebridge/main-platform-production-release.json")
STAGE_APPROVAL = Path("/etc/kmj-codebridge/main-platform-staging-approval.json")
RUNNER = Path("/usr/local/libexec/kmj-codebridge/kmj-main-platform-staging-deploy.sh")
UNIT_FILE = Path("/etc/systemd/system/kmj-main-platform-staging-deploy.service")
OFFSITE_UNIT = "kmj-elite-offsite-backup.service"
STAGE_UNIT = "kmj-main-platform-staging-deploy.service"
PROD_UNIT = "kmj-main-platform-production-release.service"
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
RELEASE = re.compile(r"platform-[0-9a-f]{12}\Z")
INVOCATION = re.compile(r"[0-9a-fA-F]{32}\Z")
PROD_KEYS = frozenset({"approvedSha", "expectedCurrentRelease", "backupVerified", "rollbackVerified"})
STAGE_KEYS = frozenset({"schema", "approvedSha", "expectedCurrentSha",
                       "expectedProductionRelease", "runnerSha256", "unitSha256",
                       "backupVerified", "rollbackVerified", "storageVerified",
                       "zeroAdditionalCostVerified"})
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"}


def classify_pointer(raw: str | None, kind: str) -> str:
    """Return only a bounded release ID; no raw target path is printed."""
    if raw is None:
        return "MISSING_OR_NOT_LINK"
    patterns = (
        (r"/home/kmjprod/releases/(platform-[0-9a-f]{12})\Z",
         r"releases/(platform-[0-9a-f]{12})\Z")
        if kind == "production" else
        (r"/home/kmjstage/releases/([0-9a-f]{40})/apps/platform\Z",
         r"\.\./releases/([0-9a-f]{40})/apps/platform\Z")
    )
    for pattern in patterns:
        found = re.fullmatch(pattern, raw)
        if found:
            return found.group(1)
    return "NONCANONICAL_LINK"


def pointer(path: Path, kind: str) -> str:
    try:
        if not stat.S_ISLNK(os.lstat(path).st_mode):
            return "NOT_SYMLINK"
        value = os.readlink(path)
        if not isinstance(value, str) or len(value) > 240:
            return "NONCANONICAL_LINK"
        return classify_pointer(value, kind)
    except OSError:
        return "MISSING_OR_NOT_LINK"


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_KEY")
        result[key] = value
    return result


def reject_constant(_):
    raise ValueError("NONFINITE_JSON")


def protected_bytes(path: Path, limit: int = 16384) -> bytes | None:
    """Open only one root-protected regular inode; never follow symbolic links."""
    if not path.is_absolute() or ".." in path.parts:
        return None
    parent = path.parent
    while True:
        try:
            p = os.lstat(parent)
        except OSError:
            return None
        if (not stat.S_ISDIR(p.st_mode) or p.st_uid != 0
                or (p.st_mode & 0o022)):
            return None
        if parent == Path("/"):
            break
        parent = parent.parent
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        return None
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != 0
                or before.st_nlink != 1 or before.st_size < 1
                or before.st_size > limit or (before.st_mode & 0o022)):
            return None
        data = os.read(fd, limit + 1)
        after = os.fstat(fd)
        current = os.lstat(path)
        stamp = lambda st: (st.st_dev, st.st_ino, st.st_mode, st.st_uid,
                            st.st_nlink, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
        if len(data) != before.st_size or stamp(before) != stamp(after) or stamp(after) != stamp(current):
            return None
        return data
    except OSError:
        return None
    finally:
        os.close(fd)


def protected_json(path: Path) -> dict | None:
    raw = protected_bytes(path, 4096)
    if raw is None:
        return None
    try:
        item = json.loads(raw, object_pairs_hook=unique_pairs,
                          parse_constant=reject_constant)
    except (ValueError, UnicodeError):
        return None
    return item if isinstance(item, dict) else None


def approval_status(record: dict | None, kind: str, prod_release: str) -> str:
    if record is None:
        return "MISSING_OR_UNTRUSTED"
    if kind == "production":
        if (frozenset(record) != PROD_KEYS
                or not isinstance(record.get("approvedSha"), str)
                or not SHA.fullmatch(record["approvedSha"])
                or not isinstance(record.get("expectedCurrentRelease"), str)
                or not RELEASE.fullmatch(record["expectedCurrentRelease"])
                or type(record.get("backupVerified")) is not bool
                or type(record.get("rollbackVerified")) is not bool):
            return "SCHEMA_INVALID"
        if record["expectedCurrentRelease"] != prod_release:
            return "STALE_CURRENT"
        return ("PASS" if record["backupVerified"] and record["rollbackVerified"]
                else "BACKUP_OR_ROLLBACK_FLAGS_FALSE")
    if (frozenset(record) != STAGE_KEYS
            or record.get("schema") != "kmj.main-platform.staging-approval.v1"
            or not all(isinstance(record.get(key), str) and SHA.fullmatch(record[key])
                       for key in ("approvedSha", "expectedCurrentSha"))
            or record["approvedSha"] == record["expectedCurrentSha"]
            or not isinstance(record.get("expectedProductionRelease"), str)
            or not RELEASE.fullmatch(record["expectedProductionRelease"])
            or not all(isinstance(record.get(key), str) and DIGEST.fullmatch(record[key])
                       for key in ("runnerSha256", "unitSha256"))
            or not all(type(record.get(key)) is bool for key in
                       ("backupVerified", "rollbackVerified", "storageVerified",
                        "zeroAdditionalCostVerified"))):
        return "SCHEMA_INVALID"
    if record["expectedProductionRelease"] != prod_release:
        return "STALE_PRODUCTION"
    return ("PASS" if all(record[k] for k in
            ("backupVerified", "rollbackVerified", "storageVerified",
             "zeroAdditionalCostVerified")) else "OWNER_FLAGS_FALSE")


def installed_digest_state(path: Path, approved: dict | None, key: str) -> str:
    blob = protected_bytes(path, 131072 if path == RUNNER else 16384)
    if blob is None:
        return "MISSING_OR_UNTRUSTED"
    if not isinstance(approved, dict) or not isinstance(approved.get(key), str):
        return "UNVERIFIABLE_APPROVAL"
    return ("PASS" if hashlib.sha256(blob).hexdigest() == approved[key]
            else "DIGEST_MISMATCH")


def property(unit: str, key: str) -> str | None:
    if unit not in {OFFSITE_UNIT, STAGE_UNIT, PROD_UNIT} or key not in {
        "LoadState", "ActiveState", "Result", "ExecMainStatus", "InvocationID",
        "NeedDaemonReload", "FragmentPath", "DropInPaths",
    }:
        return None
    try:
        output = subprocess.run(
            ["/usr/bin/systemctl", "show", unit, f"--property={key}",
             "--value", "--no-pager"],
            capture_output=True, timeout=8, check=False, env=ENV)
        if output.returncode != 0 or len(output.stdout) > 4096:
            return None
        return output.stdout.decode("utf-8", "strict").strip()
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        return None


def classify_ssh_failure(raw: str) -> str:
    if re.search(r"Permission denied \(publickey", raw, re.I):
        return "PUBLICKEY_AUTH_DENIED"
    if re.search(r"Load key|invalid format|incorrect passphrase", raw, re.I):
        return "LOCAL_KEY_FAILURE"
    if re.search(r"Host key verification failed|REMOTE HOST IDENTIFICATION HAS CHANGED", raw, re.I):
        return "HOSTKEY_MISMATCH"
    if re.search(r"timed out|No route to host|Connection refused|Network is unreachable", raw, re.I):
        return "NETWORK_OR_REMOTE"
    return "UNCLASSIFIED"


def offsite_status() -> tuple[str, str]:
    if property(OFFSITE_UNIT, "ExecMainStatus") != "255" or property(OFFSITE_UNIT, "Result") != "exit-code":
        return "NOT_EXIT_255", "NOT_APPLICABLE"
    invocation = property(OFFSITE_UNIT, "InvocationID")
    if not invocation or not INVOCATION.fullmatch(invocation):
        return "EXIT_255", "JOURNAL_UNAVAILABLE"
    try:
        proc = subprocess.run(
            ["/usr/bin/journalctl", "--no-pager", "--output=cat", "--lines=200",
             "_SYSTEMD_INVOCATION_ID=" + invocation],
            capture_output=True, timeout=12, check=False, env=ENV)
        if proc.returncode or len(proc.stdout) > 65536:
            return "EXIT_255", "JOURNAL_UNAVAILABLE"
        return "EXIT_255", classify_ssh_failure(proc.stdout.decode("utf-8", "replace"))
    except (OSError, subprocess.TimeoutExpired):
        return "EXIT_255", "JOURNAL_UNAVAILABLE"


def report() -> dict[str, str]:
    result = {}
    prod = pointer(PROD_LINK, "production")
    stage = pointer(STAGE_LINK, "staging")
    pa = protected_json(PROD_APPROVAL)
    sa = protected_json(STAGE_APPROVAL)
    result["PRODUCTION_RELEASE"] = prod
    result["PRODUCTION_APPROVAL"] = approval_status(pa, "production", prod)
    result["STAGING_POINTER"] = stage
    result["STAGING_APPROVAL"] = approval_status(sa, "staging", prod)
    # Never credit a checksum from an invalid/missing owner approval.
    trusted = sa if result["STAGING_APPROVAL"] == "PASS" else None
    result["STAGING_RUNNER"] = installed_digest_state(RUNNER, trusted, "runnerSha256")
    result["STAGING_UNIT_FILE"] = installed_digest_state(UNIT_FILE, trusted, "unitSha256")
    result["STAGING_UNIT_LOAD"] = property(STAGE_UNIT, "LoadState") or "UNKNOWN"
    result["STAGING_UNIT_RELOAD"] = property(STAGE_UNIT, "NeedDaemonReload") or "UNKNOWN"
    result["STAGING_UNIT_ACTIVE"] = property(STAGE_UNIT, "ActiveState") or "UNKNOWN"
    if result["STAGING_APPROVAL"] == "PASS" and stage != sa["expectedCurrentSha"]:
        result["STAGING_POINTER_MATCH"] = "NO"
    elif result["STAGING_APPROVAL"] == "PASS":
        result["STAGING_POINTER_MATCH"] = "YES"
    else:
        result["STAGING_POINTER_MATCH"] = "UNVERIFIABLE_APPROVAL"
    result["OFFSITE_EXIT"], result["OFFSITE_FAILURE_CLASS"] = offsite_status()
    result["BACKUP_RESTORE"] = "NOT_ATTESTED_BY_READONLY_AUDIT"
    result["PRODUCTION_MUTATION"] = "NONE"
    result["AUDIT_MODE"] = "READ_ONLY"
    return result


def main(argv: list[str]) -> int:
    if (len(argv) != 1 or os.geteuid() != 0
            or socket.gethostname().split(".")[0].lower() != "kmj-elite"):
        print("ONEPASS_AUDIT=BLOCKED_ROOT_HOST_OR_ARGS")
        return 2
    data = report()
    for key, value in data.items():
        # Only source-selected enum values, canonical release IDs and property
        # values validated against a fixed vocabulary may leave this boundary.
        if key.startswith("STAGING_UNIT_") and key in {
            "STAGING_UNIT_LOAD", "STAGING_UNIT_RELOAD", "STAGING_UNIT_ACTIVE"
        } and value not in {
            "loaded", "not-found", "unknown", "no", "yes", "inactive",
            "active", "failed", "activating", "deactivating", "UNKNOWN",
        }:
            value = "UNKNOWN"
        print(f"{key}={value}")
    print("ONEPASS_AUDIT=READ_ONLY_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
