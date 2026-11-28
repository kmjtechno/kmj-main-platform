#!/usr/bin/env python3
"""Per-release rehearsal workspace: copies of the PREVIOUS and CANDIDATE code trees
and a DISPOSABLE PostgreSQL database, plus the root-protected config the rollback
rehearsal collector reads (source only until installed).

  --write   <sha> <expected-release>   create workspace, database, config
  --cleanup <sha> <expected-release>   drop database and role, delete workspace and config

Safety properties:
  * identity comes from the argv the runner derives from the protected approval;
  * trees are copied WITHOUT any .env file, cached config, storage tree or symlink,
    so the rehearsal can never read production secrets or reach shared storage;
  * database name/role are derived from the SHA, match the rehearsal's own
    disposable-name pattern, are loopback-only, non-superuser, and stamped with a
    random nonce comment the rehearsal independently checks;
  * prepare never drops or reuses existing state; cleanup requires exact protected
    config, both database and role nonce comments, and a verified owner. Production
    databases, the live pointer, approvals and releases are never touched.
"""
import json
import os
import re
import secrets
import shutil
import socket
import stat
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import release_admission_receipts as ra  # noqa: E402
import release_receipt_store as store  # noqa: E402
import elite_collect_rollback_rehearsal_receipt as collector  # noqa: E402

BASE = Path("/var/lib/kmj-release-rehearsal")
CONFIG = Path("/etc/kmj-codebridge/release-rehearsal.json")
PREV_ROOT = Path("/home/kmjprod/releases")
CAND_ROOT = Path("/home/kmjstage/releases")
OWNER = "root"
NAME_RE = re.compile(r"kmj_rehearsal_[0-9a-f]{12}\Z")
# Order matters for rsync: the single allowed .env.example comes before the .env* exclusion.
FILTERS = (("--include", ".env.example"), ("--exclude", ".env*"),
           ("--exclude", "/bootstrap/cache/*.php"), ("--exclude", "/storage/**"),
           ("--exclude", "/public/storage"), ("--exclude", "/node_modules/"),
           ("--exclude", "/.git/"))


def names(sha):
    name = "kmj_rehearsal_" + sha[:12]
    assert NAME_RE.fullmatch(name)
    return name


def tree_paths(sha, expected):
    return (PREV_ROOT / expected / "apps" / "platform",
            CAND_ROOT / sha / "apps" / "platform")


def sql_create(name, password, nonce):
    for value, pattern in ((name, NAME_RE), (password, re.compile(r"[0-9a-f]{32}\Z")),
                           (nonce, re.compile(r"[0-9a-f]{32}\Z"))):
        if not pattern.fullmatch(value):
            raise ValueError("BLOCKED_UNSAFE_SQL_INPUT")
    return [
        "CREATE ROLE \"{n}\" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '{p}'".format(n=name, p=password),
        'CREATE DATABASE "{n}" OWNER "{n}"'.format(n=name),
        "COMMENT ON DATABASE \"{n}\" IS 'kmj-disposable-rehearsal:{x}'".format(n=name, x=nonce),
        "COMMENT ON ROLE \"{n}\" IS 'kmj-disposable-rehearsal:{x}'".format(n=name, x=nonce),
    ]


def sql_drop(name, nonce):
    if not NAME_RE.fullmatch(name) or not re.fullmatch(r"[0-9a-f]{32}", nonce):
        raise ValueError("BLOCKED_UNSAFE_SQL_INPUT")
    # No FORCE, no IF EXISTS: unexpected state fails closed.
    return ['DROP DATABASE "{n}"'.format(n=name), 'DROP ROLE "{n}"'.format(n=name)]


def cleanup_query(name, nonce):
    if not NAME_RE.fullmatch(name) or not re.fullmatch(r"[0-9a-f]{32}", nonce):
        raise ValueError("BLOCKED_UNSAFE_SQL_INPUT")
    # Bind the database owner, both independent object comments and role scope.
    return (
        "SELECT count(*) FROM pg_database d JOIN pg_roles r ON d.datdba=r.oid "
        "WHERE d.datname='{n}' AND r.rolname='{n}' "
        "AND shobj_description(d.oid,'pg_database')='kmj-disposable-rehearsal:{x}' "
        "AND shobj_description(r.oid,'pg_authid')='kmj-disposable-rehearsal:{x}' "
        "AND NOT (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls) "
        "AND NOT EXISTS (SELECT 1 FROM pg_auth_members m WHERE m.roleid=r.oid OR m.member=r.oid)"
    ).format(n=name, x=nonce)


def query_cleanup_owner(name, nonce):
    out = subprocess.run(
        ["/usr/sbin/runuser", "-u", "postgres", "--", "/usr/bin/psql",
         "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-d", "postgres"],
        input=cleanup_query(name, nonce) + ";\n", text=True, capture_output=True,
        cwd="/", env={"PATH": "/usr/bin:/bin", "LANG": "C"}, timeout=30, check=False)
    return out.returncode == 0 and out.stdout.strip() == "1"


def protected_parent(path, uid=0):
    return (path.is_absolute() and path.resolve(strict=True) == path
            and all(stat.S_ISDIR(p.lstat().st_mode) and p.lstat().st_uid == uid
                    and not p.lstat().st_mode & 0o022 for p in (path, *path.parents)))


def rsync_argv(src, dst):
    argv = ["/usr/bin/rsync", "-a", "--no-owner", "--no-group", "--no-links", "--no-devices", "--no-specials", "--delete"]
    for flag, pattern in FILTERS:
        argv += [flag, pattern]
    return argv + [str(src) + "/", str(dst) + "/"]


def make_config(name, password, nonce, prev, cand):
    return {"env": {
        "DB_DATABASE": name, "DB_USERNAME": name, "DB_PASSWORD": password,
        "DB_HOST": "127.0.0.1", "DB_PORT": "5432",
        "KMJ_REHEARSAL_PREVIOUS_APP": str(prev), "KMJ_REHEARSAL_CANDIDATE_APP": str(cand),
        "KMJ_REHEARSAL_DB_NONCE": nonce,
    }}


def real_tree(path, root):
    """A genuine directory under its release root, no symlink anywhere on the way."""
    if not path.is_dir() or path.resolve(strict=True) != path or root not in path.parents:
        return False
    return all((path / f).is_file() for f in ("artisan", "vendor/autoload.php", "public/index.php"))


def run(argv, user=None):
    cmd = (["/usr/sbin/runuser", "-u", user, "--"] if user else []) + argv
    out = subprocess.run(cmd, cwd="/", env={"PATH": "/usr/bin:/bin", "LANG": "C"},
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                         timeout=1800)
    if out.returncode != 0:
        raise ValueError("BLOCKED_STEP_FAILED")


def psql(sql_list):
    for sql in sql_list:
        run(["/usr/bin/psql", "-X", "-v", "ON_ERROR_STOP=1", "-d", "postgres", "-c", sql], "postgres")


def write_config(config, path=CONFIG):
    tmp = path.with_name("." + path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(json.dumps(config, sort_keys=True))
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(tmp, 0o600)
    # Publish without replacing another run's configuration.
    os.link(tmp, path, follow_symlinks=False)
    tmp.unlink()


def seal_workspace(work):
    for current, dirs, files in os.walk(work, followlinks=False):
        for name in dirs + files:
            path = Path(current) / name
            st = path.lstat()
            if st.st_uid != 0 or (not stat.S_ISDIR(st.st_mode) and
                    (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1)):
                raise ValueError("BLOCKED_WORKSPACE_UNTRUSTED")
            os.chmod(path, 0o755 if stat.S_ISDIR(st.st_mode) else 0o644,
                     follow_symlinks=False)
    os.chmod(work, 0o755, follow_symlinks=False)


def prepare(sha, expected, runner=run, sql_runner=psql, base=BASE, config_path=CONFIG,
            check_trees=real_tree, seal=seal_workspace):
    prev, cand = tree_paths(sha, expected)
    if not (check_trees(prev, PREV_ROOT) and check_trees(cand, CAND_ROOT)):
        raise ValueError("BLOCKED_TREE_UNTRUSTED_OR_MISSING")
    name = names(sha)
    work = base / sha[:12]
    # Never delete an existing database, role, config or workspace on prepare.
    # A failed or interrupted run requires explicit recovery, not automatic cleanup.
    if os.path.lexists(config_path) or os.path.lexists(work):
        raise ValueError("BLOCKED_EXISTING_REHEARSAL")
    work.mkdir(parents=True, mode=0o700)
    for label, src in (("previous", prev), ("candidate", cand)):
        runner(rsync_argv(src, work / label))
    # The transient sandbox may read the copied source but never modify it.
    # Strip privileged mode bits, reject special files and all links before publish.
    seal(work)

    password, nonce = secrets.token_hex(16), secrets.token_hex(16)
    sql_runner(sql_create(name, password, nonce))
    config = make_config(name, password, nonce, work / "previous", work / "candidate")
    config.update(approvedSha=sha, expectedCurrentRelease=expected)
    write_config(config, config_path)


def cleanup(sha, expected, runner=run, sql_runner=psql, base=BASE, config_path=CONFIG,
            owner_query=query_cleanup_owner, uid=0, parent_check=protected_parent):
    # Never accept stale, missing, legacy or cross-candidate configuration.
    if not parent_check(base, uid) or not parent_check(config_path.parent, uid):
        raise ValueError("BLOCKED_CLEANUP_PARENT")
    env = collector.load_env(config_path, uid, sha, expected)
    name, nonce = names(sha), env["KMJ_REHEARSAL_DB_NONCE"]
    work = base / sha[:12]
    if (not work.is_dir() or work.is_symlink() or work.resolve(strict=True) != work
            or not shutil.rmtree.avoids_symlink_attacks):
        raise ValueError("BLOCKED_CLEANUP_WORKSPACE")
    if not owner_query(name, nonce):
        raise ValueError("BLOCKED_CLEANUP_OWNERSHIP_UNVERIFIED")
    # Fail closed on active connections; preserve config/workspace on SQL failure.
    sql_runner(sql_drop(name, nonce))
    shutil.rmtree(work)
    config_path.unlink()


def main(argv):
    if len(argv) != 4 or argv[1] not in ("--write", "--cleanup"):
        print("usage: --write|--cleanup <40-hex-sha> <platform-12hex>")
        return 2
    sha, expected = argv[2], argv[3]
    if not ra.SHA_RE.fullmatch(sha) or not ra.RELEASE_RE.fullmatch(expected):
        print("REHEARSAL_WORKSPACE=BLOCKED_INPUT")
        return 2
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        print("REHEARSAL_WORKSPACE=BLOCKED_OPERATOR_HOST")
        return 2
    try:
        if argv[1] == "--write":
            if not protected_parent(BASE.parent) or not protected_parent(CONFIG.parent):
                raise ValueError("BLOCKED_PREPARE_PARENT")
            BASE.mkdir(mode=0o755, exist_ok=True)
            if not protected_parent(BASE):
                raise ValueError("BLOCKED_PREPARE_BASE")
            prepare(sha, expected)
        else:
            cleanup(sha, expected)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print("REHEARSAL_WORKSPACE=FAIL REASON=" + type(exc).__name__ + ":" + str(exc)[:60])
        return 1
    print("REHEARSAL_WORKSPACE=" + ("READY" if argv[1] == "--write" else "CLEANED"))
    print("PRODUCTION_DATABASE_TOUCHED=NO PRODUCTION_RELEASE=NOT_ATTEMPTED APPROVAL_UPDATED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
