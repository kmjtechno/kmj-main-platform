"""Read-only root attestation of one v6-preserved runtime storage snapshot.

This module never imports candidate code. Its only executable dependency is the
explicitly supplied, byte-verified PR812 v6 scanner. Consumers must attest before
and after any unprivileged materializer, and keep rejecting every other change.
"""
from __future__ import annotations

import argparse
import ctypes
import fcntl
import hashlib
import json
import os
import pwd
from pathlib import Path
import re
import stat
import subprocess
import types

V6_SHA256 = "f4d01f6e3b40c9ad774c8ada5129b241cee93dac782ce75bb0e229b26bbc95ba"
ROOT_UID = 0
SERVICE_ACCOUNT = "kmjprod"
NAME = re.compile(r"storage\.pre-shared-\d{8}T\d{6}Z\Z")
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


class Rejected(Exception):
    pass


def require(ok, reason):
    if not ok:
        raise Rejected(reason)


def canonical(value):
    p = Path(value)
    require(str(p) == str(value) == os.path.abspath(value) == os.path.realpath(value), "noncanonical_path")
    return p


def beneath(p, parent):
    return p != parent and parent in p.parents


def open_dir(path):
    fd = os.open("/", DIR_FLAGS)
    try:
        for part in path.parts[1:]:
            nxt = os.open(part, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


def inode(fd):
    s = os.fstat(fd)
    return s.st_dev, s.st_ino


def protected(s, directory=False):
    require((stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode))
            and s.st_uid == ROOT_UID and not (stat.S_IMODE(s.st_mode) & 0o077), "unprotected_state")
    if not directory:
        require(s.st_nlink == 1 and s.st_size <= 65536, "unsafe_receipt")


def load_scanner(path, release, shared, state):
    p = canonical(path)
    require(not any(p == tree or beneath(p, tree) for tree in (release, shared, state)), "dependency_inside_runtime_tree")
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        st = os.fstat(fd)
        require(stat.S_ISREG(st.st_mode) and st.st_uid == ROOT_UID and not st.st_mode & 0o022,
                "unsafe_dependency")
        for parent in p.parents:
            st = os.lstat(parent)
            require(st.st_uid == ROOT_UID and (not st.st_mode & 0o022 or st.st_mode & stat.S_ISVTX),
                    "unsafe_dependency_ancestor")
        with os.fdopen(os.dup(fd), "rb") as f:
            raw = f.read(1024 * 1024)
        require(hashlib.sha256(raw).hexdigest() == V6_SHA256, "dependency_hash_mismatch")
    finally:
        os.close(fd)
    module = types.ModuleType("trusted_pr812_v6")
    module.__file__ = str(p)
    exec(compile(raw, str(p), "exec"), module.__dict__)
    return module


def git_credentials(release):
    try:
        account = pwd.getpwnam(SERVICE_ACCOUNT)
    except KeyError as exc:
        raise Rejected("missing_service_account") from exc
    require(account.pw_uid > 0 and os.stat(release).st_uid == account.pw_uid, "wrong_git_owner")
    return account.pw_uid, account.pw_gid


def git_read(release, *args, text=True):
    # Even read-only status can invoke configured clean/process filters. Git
    # MUST run as the verified service identity, never the root attestor.
    uid, gid = git_credentials(release)
    env = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"}
    return subprocess.run(["/usr/bin/git", "--no-optional-locks", "-c", "safe.directory=" + str(release),
                           "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false", "-C", str(release), *args],
                          env=env, check=True, capture_output=True, text=text, timeout=15,
                          user=uid, group=gid, extra_groups=[], preexec_fn=no_new_privileges).stdout


def no_new_privileges():
    # Runs in the child after credential drop, before exec. Filters cannot regain
    # privilege via a setuid binary/file capability or inherited supplementary groups.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
        raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS failed")


def git_identity(release, expected):
    require(re.fullmatch(r"[0-9a-f]{40}", expected) is not None, "invalid_expected_sha")
    require(git_read(release, "rev-parse", "--show-toplevel").strip() == str(release), "wrong_repository_root")
    require(git_read(release, "rev-parse", "--verify", "HEAD").strip() == expected, "wrong_candidate_sha")


def receipt_entries(state_fd, name, scanner):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=state_fd)
    try:
        protected(os.fstat(fd))
        raw = os.read(fd, 65537)
    finally:
        os.close(fd)
    require(raw and raw.endswith(b"\n"), "incomplete_closed_receipt")
    lines = raw.split(b"\n")[:-1]
    require(len(lines) <= 200, "oversize_receipt")
    try:
        return [scanner._validate(json.loads(line.decode("utf-8", "strict"))) for line in lines]
    except (ValueError, RecursionError, scanner.Blocked) as exc:
        raise Rejected("invalid_receipt") from exc


def all_frozen(fd, scanner):
    def inspect(child):
        require(scanner.FREEZER.flags(child) & scanner.FS_IMMUTABLE_FL, "snapshot_not_immutable")
        return False
    scanner._visit_tree(fd, True, inspect)


def attest(*, release_root, app_dir, expected_sha, shared_dir, snapshot_name, state_dir, scanner_path):
    """Return exactly one repository-relative untracked directory, or reject.

    The returned string is an exact-directory exception, never a glob or a
    source-clean assertion. Callers must still inspect all Git status entries.
    """
    require(os.geteuid() == ROOT_UID, "root_attestation_required")
    release, app, shared, state = map(canonical, (release_root, app_dir, shared_dir, state_dir))
    require(beneath(app, release), "app_outside_release")
    require(not (shared == release or beneath(shared, release) or beneath(release, shared)), "shared_overlaps_release")
    require(not any(state == p or beneath(state, p) or beneath(p, state) for p in (release, shared)), "state_overlaps_runtime")
    require(isinstance(snapshot_name, str) and NAME.fullmatch(snapshot_name), "invalid_snapshot_name")
    scanner = load_scanner(scanner_path, release, shared, state)
    git_identity(release, expected_sha)
    fds = []
    try:
        for p in (app, shared, state):
            fds.append(open_dir(p))
        app_fd, shared_fd, state_fd = fds
        fcntl.flock(app_fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        protected(os.fstat(state_fd), True)
        # Root-owned ancestors prevent an application owner from moving the
        # protected directory despite apparently private mode bits.
        for parent in state.parents:
            s = os.lstat(parent)
            require(s.st_uid == ROOT_UID and (not s.st_mode & 0o022 or s.st_mode & stat.S_ISVTX), "unsafe_state_ancestor")
        key = hashlib.sha256(str(app).encode()).hexdigest()[:12]
        names = os.listdir(state_fd)
        require(key + ".journal" not in names, "active_transaction")
        matching = []
        for name in names:
            if re.fullmatch(re.escape(key) + r"\.journal\.done-\d+", name):
                entries = receipt_entries(state_fd, name, scanner)
                if entries and entries[0].get("kept") == snapshot_name:
                    matching.append(entries)
        require(len(matching) == 1, "missing_or_ambiguous_receipt")
        entries = matching[0]
        phases = [e["phase"] for e in entries]
        require(phases[0] == "begin" and phases[-1] in ("verified", "complete")
                and "verified" in phases and not any(p.startswith("rollback_") for p in phases), "not_completed_switch")
        # Phase order and required fields are stronger than generic JSON validity.
        expected = ["begin", "live_frozen", "both_frozen", "link_created", "exchanged"]
        rest = phases[5:]
        if rest[:1] == ["preserved"]:
            rest = rest[1:]
        require(phases[:5] == expected and rest[:1] == ["verified"]
                and all(p == "complete" for p in rest[1:]), "invalid_switch_history")
        require(re.fullmatch(r"[0-9a-f]{16}", entries[0].get("plan", "")) is not None, "missing_snapshot_plan")
        snapshots = [n for n in os.listdir(app_fd) if n.startswith(scanner.PRE)]
        require(snapshots == [snapshot_name], "unexpected_snapshot")
        st = os.stat("storage", dir_fd=app_fd, follow_symlinks=False)
        require(stat.S_ISLNK(st.st_mode) and os.readlink("storage", dir_fd=app_fd) == str(shared), "wrong_live_storage_link")
        live_fd = os.open("storage", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC, dir_fd=app_fd)
        fds.append(live_fd)
        require(inode(live_fd) == inode(shared_fd), "wrong_shared_identity")
        snapshot_fd = os.open(snapshot_name, DIR_FLAGS, dir_fd=app_fd)
        fds.append(snapshot_fd)
        require(inode(snapshot_fd) != inode(shared_fd), "snapshot_is_shared")
        all_frozen(snapshot_fd, scanner)
        dirs = {}
        files = scanner.scan(snapshot_fd, dirs)
        require(scanner.plan_id(files, dirs) == entries[0]["plan"], "snapshot_plan_mismatch")
        require(scanner.tree_clean(shared_fd, True), "shared_still_frozen")
        def no_append(fd):
            require(not scanner.FREEZER.flags(fd) & scanner.FS_APPEND_FL, "shared_append_only")
            return False
        scanner._visit_tree(shared_fd, True, no_append)
        require(inode(app_fd) == scanner.identity(app) and inode(shared_fd) == scanner.identity(shared), "runtime_path_replaced")
        s = os.stat(snapshot_name, dir_fd=app_fd, follow_symlinks=False)
        require((s.st_dev, s.st_ino) == inode(snapshot_fd), "snapshot_replaced")
        git_identity(release, expected_sha)
        return (app / snapshot_name).relative_to(release).as_posix() + "/"
    except scanner.Blocked as exc:
        raise Rejected("unsafe_runtime_tree:" + str(exc)) from exc
    finally:
        for fd in reversed(fds):
            os.close(fd)


def attest_snapshot(app_dir, shared, expected_snapshot, expected_sha, state_dir, *, release_root, scanner_path):
    return attest(release_root=release_root, app_dir=app_dir, expected_sha=expected_sha,
                  shared_dir=shared, snapshot_name=expected_snapshot, state_dir=state_dir,
                  scanner_path=scanner_path)


def check_source(**parameters):
    """Root attestation + source check + root reattestation; returns exact path."""
    allowed = attest(**parameters)
    release = canonical(parameters["release_root"])
    storage = (canonical(parameters["app_dir"]) / "storage").relative_to(release).as_posix()
    raw = git_read(release, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", ".",
                   ":(literal,exclude)" + storage, text=False)
    require(not filter_porcelain_z(raw, allowed), "other_source_changes")
    require(attest(**parameters) == allowed, "attestation_changed")
    return allowed


def filter_porcelain_z(raw: bytes, attested_directory: str) -> bytes:
    """Remove only ?? records for one exact, previously root-attested directory.

    Input must be `git status --porcelain=v1 -z --untracked-files=all` output.
    Rename/copy source fields are consumed as part of their original record.
    This function performs no attestation itself; root must attest again after
    the unprivileged subprocess before treating its result as admissible.
    """
    require(isinstance(raw, bytes), "status_must_be_bytes")
    require(attested_directory.endswith("/") and not attested_directory.startswith("/")
            and all(p not in ("", ".", "..") for p in attested_directory[:-1].split("/")), "invalid_attested_path")
    allowed = os.fsencode(attested_directory)
    require(not raw or raw.endswith(b"\0"), "unterminated_porcelain")
    fields, kept, i = raw.split(b"\0")[:-1], [], 0
    while i < len(fields):
        field = fields[i]
        require(len(field) >= 4 and field[2:3] == b" ", "invalid_porcelain")
        status, path = field[:2], field[3:]
        require(all(c in b" MADRCU?!T" for c in status) and path, "invalid_porcelain")
        record = [field]
        i += 1
        if b"R" in status or b"C" in status:
            require(i < len(fields) and fields[i], "missing_rename_source")
            record.append(fields[i])
            i += 1
        safe = all(p not in (b"", b".", b"..") for p in path.rstrip(b"/").split(b"/"))
        excluded = status == b"??" and safe and (path == allowed[:-1] or path.startswith(allowed))
        if not excluded:
            kept.extend(record)
    return b"\0".join(kept) + (b"\0" if kept else b"")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("release-root", "app-dir", "expected-sha", "shared-dir", "snapshot-name", "state-dir", "scanner-path"):
        parser.add_argument("--" + field, required=True)
    parser.add_argument("--check-source", action="store_true")
    try:
        parameters = vars(parser.parse_args())
        checking = parameters.pop("check_source")
        path = check_source(**parameters) if checking else attest(**parameters)
        print(json.dumps({"status": "PASS", "permissible_untracked_directory": path}))
        return 0
    except (Rejected, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
