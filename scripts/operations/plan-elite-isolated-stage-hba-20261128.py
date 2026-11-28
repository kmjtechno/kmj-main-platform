#!/usr/bin/env python3
"""Inspect and propose a role-specific HBA prefix without changing PostgreSQL.

The proposed first-match rules permit exactly the candidate DB on IPv4
loopback, and reject this role on every other local/TCP connection, including
physical replication. Existing HBA bytes and database ACLs remain unchanged.
A plan hash is NOT evidence that the policy has been installed or loaded.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import subprocess

DB = "kmj_stage_710c6f3ca103"
ROLE = "kmjstage_710c6f3ca103"
MARK = "# KMJ candidate isolation 710c6f3ca103"
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/var/lib/postgresql",
       "LANG": "C", "LC_ALL": "C", "PGHOST": "/var/run/postgresql",
       "PGPORT": "5432", "PGUSER": "postgres", "PGPASSFILE": "/dev/null"}
PSQL = ["/usr/sbin/runuser", "-u", "postgres", "--", "/usr/bin/psql",
        "-X", "-Atq", "-v", "ON_ERROR_STOP=1", "-d", "postgres"]


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def prefix():
    # PostgreSQL database token "all" excludes physical replication, so
    # explicit replication rejections are required independently.
    return (
        f"{MARK}\n"
        f"host {DB} {ROLE} 127.0.0.1/32 scram-sha-256\n"
        f"local replication {ROLE} reject\n"
        f"local all {ROLE} reject\n"
        f"host replication {ROLE} all reject\n"
        f"host all {ROLE} all reject\n"
        "# End KMJ candidate isolation 710c6f3ca103\n"
    ).encode("ascii")


def proposal(old):
    require(0 < len(old) <= 1048576 and b"\x00" not in old and not old.startswith(b"\xef\xbb\xbf"),
            "HBA_FORMAT")
    # Refuse an existing reference to this exact role or marker, even in a
    # comment, rather than accidentally installing a duplicate policy.
    require(ROLE.encode() not in old and MARK.encode() not in old,
            "CANDIDATE_HBA_ALREADY_REFERENCED")
    return prefix() + old


def pg(sql):
    p = subprocess.run(PSQL + ["-c", sql], env=ENV, cwd="/",
                       capture_output=True, timeout=15, check=False)
    require(p.returncode == 0 and len(p.stdout) <= 4096, "PG_QUERY_FAILED")
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inspect", action="store_true", required=True)
    p.parse_args()
    try:
        require(os.geteuid() == 0 and socket.gethostname().split(".")[0].lower() == "kmj-elite",
                "HOST_ROOT")
        require(pg("SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL") == "0",
                "EXISTING_HBA_PARSE_ERRORS")
        require(pg(f"SELECT count(*) FROM pg_roles WHERE rolname='{ROLE}'") == "0",
                "ROLE_ALREADY_EXISTS")
        path = Path(pg("SHOW hba_file"))
        old = read_hba(path)
        planned = proposal(old)
        require(read_hba(path) == old, "HBA_DRIFT")
        print("HBA_BASELINE_SHA256=" + hashlib.sha256(old).hexdigest())
        print("HBA_PROPOSAL_SHA256=" + hashlib.sha256(planned).hexdigest())
        print("HBA_EXISTING_PARSE_ERRORS=0")
        print("HBA_PLAN=PASS_READ_ONLY")
        print("HBA_POLICY_INSTALLED=NO")
        print("DATABASE_GRANTS_CHANGED=NO POSTGRES_RELOAD=NO")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        reason = str(exc)
        print("HBA_PLAN=BLOCKED_" + (reason if re.fullmatch("[A-Z_]+", reason) else "SYSTEM_OR_FORMAT"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
