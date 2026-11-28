#!/usr/bin/env python3
"""Read-only legacy staging role HBA qualification and exact scoped proposal.
Never writes HBA, changes grants, reloads PostgreSQL or prints credentials.
"""
import argparse
import hashlib
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import subprocess

STAGE = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
STAGE_TARGET = Path("/home/kmjstage/releases/b2e69decab3acd861e94e11992cd8a4cff4f2b94/apps/platform")
LIVE = Path("/home/kmjprod/current")
LIVE_TARGET = Path("/home/kmjprod/releases/platform-457481eb652f")
ENV = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
       "PGHOST": "/var/run/postgresql", "PGPORT": "5432",
       "PGUSER": "postgres", "PGPASSFILE": "/dev/null", "PGCONNECT_TIMEOUT": "3"}
PSQL = ["/usr/sbin/runuser", "-u", "postgres", "--", "/usr/bin/psql",
        "-X", "-w", "-Atq", "-v", "ON_ERROR_STOP=1", "-d", "postgres"]
DB_RE = re.compile(r"kmj_stage_[a-z0-9_]{2,53}\Z")
ROLE_RE = re.compile(r"kmjstage(?:_[a-z0-9_]{1,53})?\Z")
NAME_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,62}\Z")
MARK = b"# KMJ legacy staging role isolation v1"


def require(ok, label):
    if not ok:
        raise ValueError(label)


def pointer_guard():
    require(STAGE.is_symlink() and STAGE.resolve(strict=True) == STAGE_TARGET
            and LIVE.is_symlink() and LIVE.resolve(strict=True) == LIVE_TARGET,
            "RELEASE_POINTER_DRIFT")


def identity(raw):
    values = {}
    keys = {"DB_CONNECTION", "DB_DATABASE", "DB_USERNAME", "DB_HOST",
            "DB_PORT", "DB_URL", "DB_PASSWORD", "APP_ENV", "APP_URL"}
    for line in raw.decode("utf-8", "strict").splitlines():
        if not line or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if key.strip() not in keys:
            continue
        require(sep and key == key.strip() and key not in values, "ENV_SYNTAX")
        values[key] = value.strip()
    db, role, host = (values.get(k, "") for k in ("DB_DATABASE", "DB_USERNAME", "DB_HOST"))
    require(DB_RE.fullmatch(db) and ROLE_RE.fullmatch(role), "ENV_IDENTITY")
    require(values.get("APP_ENV") == "staging" and
            values.get("APP_URL") == "https://staging.kmjtechno.com" and
            values.get("DB_CONNECTION") == "pgsql" and
            values.get("DB_PORT", "5432") == "5432" and not values.get("DB_URL"),
            "ENV_POLICY")
    require(host in ("127.0.0.1", "localhost", "/var/run/postgresql"), "HOST_SCOPE")
    # Do not guess Laravel dotenv quoting, escaping or interpolation.
    password = values.get("DB_PASSWORD", "")
    require(re.fullmatch(r"[A-Za-z0-9_.!@%+=:/-]{8,256}", password), "PASSWORD_FORMAT")
    return db, role, host, password


def read_regular(path, owner_ids, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as handle:
        s = os.fstat(handle.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_uid in owner_ids and
                s.st_nlink == 1 and not s.st_mode & 0o022 and
                0 < s.st_size <= limit, "FILE_METADATA")
        raw = handle.read(limit + 1)
        a = os.fstat(handle.fileno())
        require(len(raw) == s.st_size and (s.st_dev, s.st_ino, s.st_mtime_ns, s.st_ctime_ns)
                == (a.st_dev, a.st_ino, a.st_mtime_ns, a.st_ctime_ns), "FILE_DRIFT")
        return raw


def pg(sql):
    r = subprocess.run(PSQL + ["-c", sql], env=ENV, cwd="/",
                       capture_output=True, timeout=20, check=False)
    require(r.returncode == 0 and len(r.stdout) <= 16384, "CATALOG_QUERY")
    return r.stdout.decode("utf-8", "strict").strip()


def catalog(db, role):
    require(DB_RE.fullmatch(db) and ROLE_RE.fullmatch(role), "IDENTITY")
    require(pg(f"""SELECT count(*) FROM pg_authid
      WHERE rolname='{role}' AND rolcanlogin AND NOT rolsuper AND NOT rolcreatedb
      AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls
      AND rolpassword LIKE 'SCRAM-SHA-256$%'
      AND NOT EXISTS (SELECT 1 FROM pg_auth_members WHERE member=pg_authid.oid)""") == "1",
            "ROLE_OR_SCRAM_UNVERIFIED")
    require(pg(f"""SELECT count(*) FROM pg_database WHERE datname='{db}'
      AND datallowconn AND has_database_privilege('{role}',oid,'CONNECT')""") == "1",
            "OWN_DB_CONNECT")
    require(pg(f"SELECT count(*) FROM pg_stat_activity WHERE usename='{role}' AND datname<>'{db}'") == "0",
            "CROSS_DB_SESSIONS")
    names = pg("SELECT datname FROM pg_database WHERE datallowconn ORDER BY datname").splitlines()
    require(db in names and 1 <= len(names) <= 128 and len(set(names)) == len(names)
            and all(NAME_RE.fullmatch(n) for n in names), "DATABASE_CATALOG")
    require(pg("SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL") == "0",
            "HBA_PARSE_ERRORS")
    return names


def prefix(db, role, host):
    require(DB_RE.fullmatch(db) and ROLE_RE.fullmatch(role), "IDENTITY")
    require(host in ("127.0.0.1", "localhost", "/var/run/postgresql"), "HOST_SCOPE")
    allow = ([f"local {db} {role} scram-sha-256"] if host == "/var/run/postgresql"
             else [f"host {db} {role} 127.0.0.1/32 scram-sha-256"])
    if host == "localhost":
        allow.append(f"host {db} {role} ::1/128 scram-sha-256")
    return ("\n".join([MARK.decode("ascii"), *allow,
            f"local replication {role} reject", f"local all {role} reject",
            f"host replication {role} all reject", f"host all {role} all reject",
            "# End KMJ legacy staging role isolation v1", ""])).encode("ascii")


def proposal(old, db, role, host):
    require(0 < len(old) <= 1048576 and b"\0" not in old and
            not old.startswith(b"\xef\xbb\xbf"), "HBA_FORMAT")
    require(MARK not in old, "EXISTING_KMJ_PREFIX")
    # Existing role references are preserved byte-for-byte; the new prefix
    # would take precedence only for this exact role.
    return prefix(db, role, host) + old


def hba():
    p = Path(pg("SHOW hba_file"))
    require(p.is_absolute() and p.name == "pg_hba.conf" and
            p.resolve(strict=True) == p, "HBA_PATH")
    for parent in p.parents:
        s = parent.lstat()
        require(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022,
                "HBA_PARENT")
        require(not any(x.startswith("system.posix_acl_") for x in
                        os.listxattr(parent, follow_symlinks=False)), "HBA_PARENT_ACL")
    return p, read_regular(p, (0, pwd.getpwnam("postgres").pw_uid), 1048576)


def probe(db, role, host, password=None):
    require(NAME_RE.fullmatch(db) and ROLE_RE.fullmatch(role), "PROBE_IDENTITY")
    require(host in ("127.0.0.1", "::1", "localhost", "/var/run/postgresql"), "PROBE_HOST")
    env = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
           "PGPASSFILE": "/dev/null", "PGCONNECT_TIMEOUT": "3", "PGSSLMODE": "prefer"}
    if password is not None:
        env["PGPASSWORD"] = password
    # No password in argv, output or file; no application queries.
    return subprocess.run(["/usr/sbin/runuser", "-u", "kmjstage", "--",
                           "/usr/bin/psql", "-X", "-w", "-Atq", "-v", "ON_ERROR_STOP=1",
                           "-p", "5432", "-h", host, "-U", role, "-d", db],
                          input=b"SELECT current_database() || ':' || current_user;\n",
                          env=env, cwd="/", capture_output=True, timeout=8, check=False)


def explicitly_rejected(r):
    return r.returncode != 0 and b"pg_hba.conf rejects connection" in r.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", required=True, action="store_true")
    parser.parse_args()
    try:
        require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite",
                "HOST_ROOT")
        pointer_guard()
        env_path = STAGE_TARGET / ".env"
        uid = pwd.getpwnam("kmjstage").pw_uid
        s = env_path.lstat()
        require(s.st_uid == uid and stat.S_IMODE(s.st_mode) in (0o400, 0o600), "ENV_METADATA")
        raw = read_regular(env_path, (uid,), 1048576)
        db, role, host, password = identity(raw)
        names = catalog(db, role)
        hba_path, old = hba()
        own = probe(db, role, host, password)
        require(own.returncode == 0 and own.stdout.strip() == (db + ":" + role).encode(),
                "CURRENT_STAGE_LOGIN_UNVERIFIED")
        print("STAGE_CURRENT_LOGIN=PASS")
        # Never send the real staging credential to another database. Explicit
        # HBA rejection is distinguishable from an auth challenge or other error.
        denied = 0
        total = 0
        for name in names:
            if name == db:
                continue
            for transport in ("127.0.0.1", "::1", "/var/run/postgresql"):
                total += 1
                if explicitly_rejected(probe(name, role, transport)):
                    denied += 1
        planned = proposal(old, db, role, host)
        require(catalog(db, role) == names and hba() == (hba_path, old)
                and read_regular(env_path, (uid,), 1048576) == raw, "INSPECTION_DRIFT")
        pointer_guard()
        print("STAGE_ROLE_RESTRICTED_SCRAM=PASS")
        print("OTHER_DB_HBA_EXPLICIT_DENIALS=" + str(denied) + "/" + str(total))
        print("HBA_BASELINE_SHA256=" + hashlib.sha256(old).hexdigest())
        print("HBA_PROPOSAL_SHA256=" + hashlib.sha256(planned).hexdigest())
        print("HBA_PLAN=PASS_READ_ONLY")
        print("LIVE_ISOLATION=NOT_ATTESTED")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        reason = str(exc)
        print("HBA_PLAN=BLOCKED_" + (reason if re.fullmatch(r"[A-Z_]+", reason) else "SYSTEM_OR_FORMAT"))
        return 2
    finally:
        print("DATABASE_GRANTS_CHANGED=NO HBA_CHANGED=NO POSTGRES_RELOAD=NO SECRET_OUTPUT=NONE")


if __name__ == "__main__":
    raise SystemExit(main())
