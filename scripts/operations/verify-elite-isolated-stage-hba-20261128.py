#!/usr/bin/env python3
"""Verify exact candidate HBA policy and live connections; never changes DBs.

--inspect: validate the installed on-disk prefix and parse status.
--verify: additionally use the private candidate password to prove positive
and explicit negative live connections against every connectable database.
The role must already be provisioned. No data rows, secrets or raw errors
are printed. This is not an installer or a receipt writer.
"""
import argparse
import importlib.util
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location("stage_hba_plan", Path(__file__).resolve().parent / "plan-elite-isolated-stage-hba-20261128.py")
plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan)
DB, ROLE = plan.DB, plan.ROLE
SHA = "710c6f3ca10310457bc7243caabc0e48476ec110"
SECRET = Path("/var/lib/kmj-main-platform-stage-runtime") / SHA / "credentials/postgres-password"
PSQL = "/usr/bin/psql"


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def current_policy():
    path = Path(plan.pg("SHOW hba_file"))
    raw = plan.read_hba(path)
    require(raw.startswith(plan.prefix()), "EXACT_HBA_PREFIX_MISSING")
    require(raw.count(plan.prefix()) == 1, "DUPLICATE_HBA_PREFIX")
    require(plan.pg("SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL") == "0",
            "HBA_PARSE_ERRORS")
    return path, raw


def database_names():
    result = plan.pg("SELECT datname FROM pg_database WHERE datallowconn ORDER BY datname")
    names = result.splitlines()
    require(1 <= len(names) <= 128 and len(set(names)) == len(names), "DATABASE_LIST_SCOPE")
    require(all(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,62}", n) for n in names),
            "DATABASE_NAME_UNSUPPORTED")
    require(DB in names, "CANDIDATE_DATABASE_MISSING")
    return names


def password():
    fd = os.open(SECRET, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) == 0o600 and info.st_size == 65,
                "CREDENTIAL_METADATA")
        raw = stream.read(66)
    require(bool(re.fullmatch(rb"[0-9a-f]{64}\n", raw)), "CREDENTIAL_FORMAT")
    return raw.strip().decode("ascii")


def probe(database, host, passfile):
    require(bool(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,62}", database)), "DATABASE_NAME_UNSUPPORTED")
    require(host in ("127.0.0.1", "/var/run/postgresql"), "HOST_SCOPE")
    env = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
           "PGPASSFILE": str(passfile), "PGCONNECT_TIMEOUT": "3", "PGSSLMODE": "prefer"}
    return subprocess.run([PSQL, "-X", "-w", "-Atq", "-v", "ON_ERROR_STOP=1",
                           "-p", "5432", "-h", host, "-U", ROLE, "-d", database],
                          input=b"SELECT current_database() || ':' || current_user;\n",
                          env=env, cwd="/", capture_output=True, timeout=8, check=False)


def rejected(result):
    return result.returncode != 0 and b"pg_hba.conf rejects connection" in result.stderr


def verify_live():
    baseline = current_policy()
    names = database_names()
    with tempfile.TemporaryDirectory(prefix="kmj-stage-hba-probe-", dir="/root") as tmp:
        file = Path(tmp) / "pgpass"
        fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write("*:5432:*:" + ROLE + ":" + password() + "\n")
        for name in names:
            require(rejected(probe(name, "/var/run/postgresql", file)), "LOCAL_SOCKET_NOT_EXPLICITLY_REJECTED")
            if name != DB:
                require(rejected(probe(name, "127.0.0.1", file)), "OTHER_DATABASE_NOT_EXPLICITLY_REJECTED")
        allowed = probe(DB, "127.0.0.1", file)
        require(allowed.returncode == 0 and allowed.stdout.strip() == (DB+":"+ROLE).encode(),
                "CANDIDATE_CONNECTION_FAILED")
    require(current_policy() == baseline and database_names() == names, "POLICY_OR_CATALOG_DRIFT")
    return len(names)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    m = p.add_mutually_exclusive_group(required=True)
    m.add_argument("--inspect", action="store_true")
    m.add_argument("--verify", action="store_true")
    args = p.parse_args()
    try:
        require(os.geteuid() == 0 and socket.gethostname().split(".")[0].lower() == "kmj-elite", "HOST_ROOT")
        current_policy()
        print("HBA_DISK_POLICY=PASS")
        if args.verify:
            print("HBA_LIVE_CONNECTIONS=PASS DATABASES_CHECKED=" + str(verify_live()))
        else:
            print("HBA_LIVE_CONNECTIONS=NOT_TESTED")
        print("DATABASE_GRANTS_CHANGED=NO POSTGRES_RELOAD=NO")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        reason = str(exc)
        print("HBA_VERIFY=BLOCKED_" + (reason if re.fullmatch("[A-Z_]+", reason) else "SYSTEM_OR_FORMAT"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
