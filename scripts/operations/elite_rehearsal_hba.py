#!/usr/bin/env python3
"""Root-only, role-specific rehearsal HBA plan, install and live verification.

No existing database ACL changes. Install is separate from rehearsal, requires
exact reviewed baseline/proposal hashes and the protected release identity.
Only the new role may use its own disposable database on IPv4 loopback.
"""
import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import tempfile
import time

NAME = re.compile(r"kmj_rehearsal_[0-9a-f]{12}\Z")
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/var/lib/postgresql",
       "LANG": "C", "LC_ALL": "C", "PGHOST": "/var/run/postgresql",
       "PGPORT": "5432", "PGUSER": "postgres", "PGPASSFILE": "/dev/null"}
PSQL = ["/usr/sbin/runuser", "-u", "postgres", "--", "/usr/bin/psql",
        "-X", "-w", "-Atq", "-v", "ON_ERROR_STOP=1", "-d", "postgres"]


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def prefix(name):
    require(bool(NAME.fullmatch(name)), "REHEARSAL_ROLE_INVALID")
    return (
        f"# KMJ rehearsal isolation {name}\n"
        f"host {name} {name} 127.0.0.1/32 scram-sha-256\n"
        f"local replication {name} reject\n"
        f"local all {name} reject\n"
        f"host replication {name} all reject\n"
        f"host all {name} all reject\n"
        f"# End KMJ rehearsal isolation {name}\n"
    ).encode("ascii")


def proposal(old, name):
    require(0 < len(old) <= 1048576 and b"\x00" not in old and not old.startswith(b"\xef\xbb\xbf"),
            "HBA_FORMAT")
    require(name.encode() not in old, "REHEARSAL_HBA_ALREADY_REFERENCED")
    return prefix(name) + old


def pg(sql):
    p = subprocess.run(PSQL, input=(sql + ";\n").encode(), env=ENV, cwd="/",
                       capture_output=True, timeout=15, check=False)
    require(p.returncode == 0 and len(p.stdout) <= 16384, "PG_QUERY_FAILED")
    return p.stdout.decode("utf-8", "strict").strip()


def read_hba(path):
    require(path.is_absolute() and path == path.resolve(strict=True), "HBA_PATH")
    require(path.name == "pg_hba.conf", "HBA_FILENAME")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        import pwd
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and before.st_uid in (0, pwd.getpwnam("postgres").pw_uid)
                and not before.st_mode & 0o022 and 0 < before.st_size <= 1048576,
                "HBA_METADATA")
        data = stream.read(1048577)
        after = os.fstat(stream.fileno())
        require(len(data) == before.st_size and
                (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns),
                "HBA_DRIFT")
    return data


def sha(data):
    return hashlib.sha256(data).hexdigest()


def trusted_parent(path):
    for p in (path.parent, *path.parent.parents):
        s = p.lstat()
        require(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022,
                "HBA_PARENT_UNTRUSTED")
        require(not any(x.startswith("system.posix_acl_") for x in os.listxattr(p, follow_symlinks=False)),
                "HBA_PARENT_ACL")


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_replace(path, expected, payload, metadata):
    require(read_hba(path) == expected, "HBA_CONTENT_DRIFT")
    current = path.lstat()
    require((current.st_dev, current.st_ino, current.st_uid, current.st_gid, stat.S_IMODE(current.st_mode))
            == (metadata.st_dev, metadata.st_ino, metadata.st_uid, metadata.st_gid, stat.S_IMODE(metadata.st_mode)),
            "HBA_INODE_DRIFT")
    require(not os.listxattr(path, follow_symlinks=False), "HBA_EXTENDED_ATTRIBUTES")
    fd, tmp = tempfile.mkstemp(prefix=".kmj-hba-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fchown(handle.fileno(), metadata.st_uid, metadata.st_gid)
            os.fchmod(handle.fileno(), stat.S_IMODE(metadata.st_mode))
            os.fsync(handle.fileno())
        require(read_hba(path) == expected, "HBA_CONTENT_DRIFT")
        os.replace(tmp, path)
        sync_dir(path.parent)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)


def policy(name):
    path = Path(pg("SHOW hba_file"))
    trusted_parent(path)
    raw = read_hba(path)
    require(raw.startswith(prefix(name)) and raw.count(prefix(name)) == 1,
            "REHEARSAL_HBA_PREFIX_MISSING")
    require(pg("SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL") == "0",
            "HBA_PARSE_ERRORS")
    return path, raw


def databases(name, present):
    result = pg("SELECT datname FROM pg_database WHERE datallowconn ORDER BY datname")
    names = result.splitlines()
    require(1 <= len(names) <= 128 and len(set(names)) == len(names)
            and all(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,62}", n) for n in names),
            "DATABASE_LIST_SCOPE")
    require((name in names) == present, "REHEARSAL_DATABASE_STATE")
    return names


def probe(name, database, host, passfile="/dev/null", positive=False):
    require(bool(NAME.fullmatch(name)) and bool(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,62}", database))
            and host in ("127.0.0.1", "/var/run/postgresql"), "PROBE_SCOPE")
    return subprocess.run(["/usr/bin/psql", "-X", "-w", "-Atq", "-v", "ON_ERROR_STOP=1",
                           "-p", "5432", "-h", host, "-U", name, "-d", database],
                          input=(b"SELECT current_database() || ':' || current_user;\n" if positive else b"\\q\n"),
                          env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
                               "PGPASSFILE": str(passfile), "PGCONNECT_TIMEOUT": "3",
                               "PGSSLMODE": "prefer"}, cwd="/", capture_output=True,
                          timeout=8, check=False)


def rejected(p):
    return p.returncode != 0 and b"pg_hba.conf rejects connection" in p.stderr


def verify(name, password=None, nonce=None):
    """Check first-match disk policy and actual explicit rejections.
    With no password, verify before creating the login; otherwise verify its
    exact nonce-bound ownership and a positive SCRAM-authenticated connection.
    """
    baseline = policy(name)
    present = password is not None
    names = databases(name, present)
    if not present:
        require(pg(f"SELECT count(*) FROM pg_roles WHERE rolname='{name}'") == "0",
                "REHEARSAL_ROLE_EXISTS")
    else:
        require(bool(re.fullmatch(r"[0-9a-f]{32}", password)) and
                bool(re.fullmatch(r"[0-9a-f]{32}", nonce or "")), "REHEARSAL_CREDENTIAL_FORMAT")
        require(pg(
            "SELECT count(*) FROM pg_database d JOIN pg_roles r ON d.datdba=r.oid "
            f"WHERE d.datname='{name}' AND r.rolname='{name}' AND r.rolcanlogin "
            "AND NOT (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls) "
            "AND NOT EXISTS (SELECT 1 FROM pg_auth_members m WHERE m.roleid=r.oid OR m.member=r.oid) "
            f"AND shobj_description(d.oid,'pg_database')='kmj-disposable-rehearsal:{nonce}' "
            f"AND shobj_description(r.oid,'pg_authid')='kmj-disposable-rehearsal:{nonce}' "
            "AND NOT EXISTS (SELECT 1 FROM aclexplode(coalesce(d.datacl,acldefault('d',d.datdba))) a "
            "WHERE a.grantee=0 AND a.privilege_type IN ('CONNECT','TEMPORARY','CREATE'))"
        ) == "1", "REHEARSAL_OWNER_OR_ACL_UNVERIFIED")
    for db in names:
        require(rejected(probe(name, db, "/var/run/postgresql")), "REHEARSAL_SOCKET_NOT_REJECTED")
        if db != name:
            require(rejected(probe(name, db, "127.0.0.1")), "REHEARSAL_CROSS_DB_NOT_REJECTED")
    if not present:
        require(rejected(probe(name, name, "/var/run/postgresql")), "REHEARSAL_SOCKET_NOT_REJECTED")
        challenge = probe(name, name, "127.0.0.1")
        require(challenge.returncode != 0 and b"no password supplied" in challenge.stderr,
                "REHEARSAL_SCRAM_CHALLENGE_MISSING")
    else:
        with tempfile.TemporaryDirectory(prefix="kmj-rehearsal-pgpass-", dir="/root") as tmp:
            file = Path(tmp) / "pgpass"
            fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "w", encoding="ascii") as out:
                out.write("127.0.0.1:5432:" + name + ":" + name + ":" + password + "\n")
            allowed = probe(name, name, "127.0.0.1", file, positive=True)
            require(allowed.returncode == 0 and allowed.stdout.strip() == (name+":"+name).encode(),
                    "REHEARSAL_POSITIVE_LOGIN_FAILED")
    require(policy(name) == baseline and databases(name, present) == names, "HBA_OR_CATALOG_DRIFT")
    return len(names)


def guard(approved, expected, name):
    import main_platform_autopublish_gate as gate
    approval = gate.protected_json(gate.APPROVAL)
    require(approval.get("approvedSha") == approved and approval.get("expectedCurrentRelease") == expected,
            "PROTECTED_APPROVAL_DRIFT")
    live = Path("/home/kmjprod/current")
    require(live.is_symlink() and live.resolve(strict=True) == Path("/home/kmjprod/releases") / expected,
            "LIVE_POINTER_DRIFT")
    require(pg(f"SELECT count(*) FROM pg_roles WHERE rolname='{name}'") == "0", "REHEARSAL_ROLE_EXISTS")
    databases(name, False)
    require(pg("SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL") == "0", "HBA_PARSE_ERRORS")


def reload():
    require(pg("SELECT pg_reload_conf()") == "t", "RELOAD_SIGNAL_FAILED")
    require(pg("SELECT 1") == "1", "ADMIN_CONNECTION_FAILED")


def install(path, old, new, approved, expected, name):
    metadata = path.lstat()
    backup_dir = Path(tempfile.mkdtemp(prefix="kmj-rehearsal-hba-backup-", dir="/root"))
    backup = backup_dir / "pg_hba.conf.original"
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(old)
        out.flush()
        os.fsync(out.fileno())
    sync_dir(backup_dir)
    sync_dir(backup_dir.parent)
    print("HBA_BACKUP=" + str(backup), flush=True)
    try:
        guard(approved, expected, name)
        atomic_replace(path, old, new, metadata)
        guard(approved, expected, name)
        reload()
        # Reload acknowledgement alone is not live policy evidence.
        for i in range(10):
            try:
                verify(name)
                break
            except ValueError:
                if i == 9:
                    raise
                time.sleep(0.3)
        guard(approved, expected, name)
        require(read_hba(path) == new, "HBA_POST_RELOAD_DRIFT")
    except BaseException:
        if read_hba(path) == new:
            atomic_replace(path, new, old, path.lstat())
            reload()
            require(read_hba(path) == old, "HBA_ROLLBACK_READBACK")
            print("HBA_ROLLBACK=ORIGINAL_BYTES_RESTORED_RELOAD_SIGNAL_SENT")
        elif read_hba(path) != old:
            print("HBA_ROLLBACK=BLOCKED_UNEXPECTED_DRIFT")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--install", action="store_true")
    parser.add_argument("--sha", required=True)
    parser.add_argument("--expected-release", required=True)
    parser.add_argument("--baseline-sha256", default="")
    parser.add_argument("--proposal-sha256", default="")
    parser.add_argument("--confirm", default="")
    a = parser.parse_args()
    try:
        require(os.geteuid() == 0 and socket.gethostname().split(".")[0].lower() == "kmj-elite", "HOST_ROOT")
        require(bool(re.fullmatch(r"[0-9a-f]{40}", a.sha)) and
                bool(re.fullmatch(r"platform-[0-9a-f]{12}", a.expected_release)), "RELEASE_IDENTITY")
        name = "kmj_rehearsal_" + a.sha[:12]
        lock = Path("/root/.kmj-stage-hba-install.lock")
        fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            s = os.fstat(fd)
            require(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1
                    and stat.S_IMODE(s.st_mode) == 0o600, "LOCK_METADATA")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            guard(a.sha, a.expected_release, name)
            path = Path(pg("SHOW hba_file"))
            trusted_parent(path)
            old = read_hba(path)
            new = proposal(old, name)
            print("HBA_BASELINE_SHA256=" + sha(old))
            print("HBA_PROPOSAL_SHA256=" + sha(new))
            if a.install:
                require(a.confirm == "OWNER_APPROVES_REVIEWED_REHEARSAL_HBA_ONLY"
                        and sha(old) == a.baseline_sha256 and sha(new) == a.proposal_sha256,
                        "OWNER_OR_REVIEWED_PINS_MISMATCH")
                install(path, old, new, a.sha, a.expected_release, name)
                print("REHEARSAL_HBA=PASS_PRE_ROLE_LIVE_ISOLATION")
            else:
                print("REHEARSAL_HBA=PLAN_ONLY")
        finally:
            os.close(fd)
        print("EXISTING_DATABASE_ACLS_CHANGED=NO PRODUCTION_RELEASE=NOT_ATTEMPTED")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        reason = str(e)
        print("REHEARSAL_HBA=BLOCKED_" + (reason if re.fullmatch("[A-Z_]+", reason) else "SYSTEM_OR_FORMAT"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
