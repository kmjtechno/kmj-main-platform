#!/usr/bin/env python3
"""Isolated application HTTP + database migration/rollback rehearsal.

Runs the PREVIOUS and the CANDIDATE Laravel code trees against ONE disposable
PostgreSQL database and proves, with real HTTP requests and real migrations:

  1. previous code builds/uses its schema and answers HTTP            (baseline S0)
  2. candidate code migrates forward; the change is ADDITIVE ONLY     (S1 ⊇ S0)
  3. candidate code answers HTTP, including its new route behaviour
  4. CODE ROLLBACK: previous code serves HTTP against the migrated DB (S1)
  5. SCHEMA ROLLBACK: the candidate's new migrations roll back and the schema
     fingerprint returns EXACTLY to S0, then re-applies to exactly S1

It never connects to a production database: the target database must be a
disposable one (name pattern, local socket or loopback only), neither code tree
may contain a ``.env`` file, the child processes get a CLEAN environment (no
inherited secrets), mail/queue/cache are inert, and storage is a scratch dir.

It does NOT prove authenticated application behaviour, a restore from backup,
data migration safety on production-size data, or release readiness. It never
prints ``rollbackVerified`` and never touches release pointers or approvals.
"""
from __future__ import annotations

import base64
import http.client
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DB_NAME = re.compile(r"^kmj_(rehearsal|release_qa)(_[a-z0-9]{1,24})?$")
DB_USER = re.compile(r"^[a-z_][a-z0-9_]{0,31}$")
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
# Resolve all path aliases before accepting a rehearsal tree. Never execute
# against the live production/staging release roots, including immutable
# release directories or paths reached through a symlinked parent.
FORBIDDEN_RUNTIME_ROOTS = (Path("/home/kmjprod"), Path("/home/kmjstage"))
ARTISAN_TIMEOUT = 600
SERVER_START_SECONDS = 40
FORBIDDEN_BODY = ("Whoops", "Stack trace", "vendor/laravel/framework")


class Blocked(RuntimeError):
    """A safety precondition failed; nothing was executed."""


def status(key: str, value: str) -> None:
    print(f"{key}={value}", flush=True)


# ---------------------------------------------------------------- guards ----
def validate_database(env: dict[str, str]) -> dict[str, str]:
    name = env.get("DB_DATABASE", "")
    if not DB_NAME.fullmatch(name):
        raise Blocked("DB_NAME_NOT_DISPOSABLE")
    user = env.get("DB_USERNAME", "")
    if not DB_USER.fullmatch(user):
        raise Blocked("DB_USER_INVALID")
    host = env.get("DB_HOST", "")
    if host not in LOOPBACK:
        # Otherwise it must be an absolute, existing unix-socket directory.
        if not host.startswith("/") or ".." in host or not Path(host).is_dir():
            raise Blocked("DB_HOST_NOT_LOCAL")
    port = env.get("DB_PORT", "5432")
    if not (port.isdigit() and 1 <= int(port) <= 65535):
        raise Blocked("DB_PORT_INVALID")
    return {
        "DB_DATABASE": name,
        "DB_USERNAME": user,
        "DB_HOST": host,
        "DB_PORT": port,
        "DB_PASSWORD": env.get("DB_PASSWORD", ""),
    }


def validate_tree(path_text: str, label: str) -> Path:
    path = Path(path_text)
    if not path_text or path.is_symlink() or not path.is_dir():
        raise Blocked(f"{label}_TREE_MISSING")
    resolved = path.resolve(strict=True)
    if any(resolved == root or root in resolved.parents for root in FORBIDDEN_RUNTIME_ROOTS):
        raise Blocked(f"{label}_TREE_IS_LIVE_RELEASE_POINTER")
    for required in ("artisan", "vendor/autoload.php", "public/index.php"):
        if not (resolved / required).is_file():
            raise Blocked(f"{label}_TREE_INCOMPLETE")
    # A production .env would make a rehearsal read real secrets and endpoints.
    if any(p.name.startswith(".env") and p.name != ".env.example" for p in resolved.iterdir()):
        raise Blocked(f"{label}_TREE_HAS_ENV_FILE")
    if os.path.lexists(resolved / "bootstrap/cache/config.php"):
        raise Blocked(f"{label}_TREE_HAS_CACHED_CONFIG")
    return resolved


def clean_env(db: dict[str, str], scratch: Path, port: int) -> dict[str, str]:
    """Child environment built from scratch: nothing inherited except PATH/LANG."""
    storage = scratch / "storage"
    for sub in (
        "app/public",
        "framework/cache/data",
        "framework/sessions",
        "framework/views",
        "logs",
    ):
        (storage / sub).mkdir(parents=True, exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "HOME": str(scratch),
        "TMPDIR": str(scratch),
        "LARAVEL_STORAGE_PATH": str(storage),
        "APP_ENV": os.environ.get("KMJ_REHEARSAL_APP_ENV", "testing"),
        "APP_DEBUG": "false",
        "APP_URL": f"http://127.0.0.1:{port}",
        "APP_KEY": "base64:" + base64.b64encode(secrets.token_bytes(32)).decode(),
        "DB_CONNECTION": "pgsql",
        "DB_URL": "",
        **db,
        "CACHE_STORE": "array",
        "SESSION_DRIVER": "array",
        "QUEUE_CONNECTION": "sync",
        "MAIL_MAILER": "array",
        "BROADCAST_CONNECTION": "null",
        "FILESYSTEM_DISK": "local",
        "LOG_CHANNEL": "stderr",
        "TELESCOPE_ENABLED": "false",
        "PULSE_ENABLED": "false",
        "NIGHTWATCH_ENABLED": "false",
    }


# --------------------------------------------------------------- database ---
def psql_rows(db: dict[str, str], sql: str) -> list[tuple[str, ...]]:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PGPASSWORD": db["DB_PASSWORD"]}
    done = subprocess.run(
        ["psql", "-X", "-A", "-t", "-F", "\x1f", "-v", "ON_ERROR_STOP=1",
         "-h", db["DB_HOST"], "-p", db["DB_PORT"], "-U", db["DB_USERNAME"],
         "-d", db["DB_DATABASE"], "-c", sql],
        env=env, capture_output=True, text=True, timeout=120, check=False,
    )
    if done.returncode != 0:
        raise RuntimeError("PSQL_FAILED")
    return [tuple(line.split("\x1f")) for line in done.stdout.splitlines() if line]


SCHEMA_QUERIES = {
    "column": "select table_name, column_name, data_type, is_nullable, coalesce(column_default,'') "
              "from information_schema.columns where table_schema='public'",
    "index": "select tablename, indexname, indexdef from pg_indexes where schemaname='public'",
    "constraint": "select conrelid::regclass::text, conname, pg_get_constraintdef(oid) "
                  "from pg_constraint where connamespace='public'::regnamespace",
}


def schema_snapshot(db: dict[str, str]) -> frozenset[tuple[str, ...]]:
    items: set[tuple[str, ...]] = set()
    for kind, sql in SCHEMA_QUERIES.items():
        for row in psql_rows(db, sql):
            items.add((kind, *row))
    return frozenset(items)


def migrations(db: dict[str, str]) -> list[str]:
    return sorted(row[0] for row in psql_rows(db, "select migration from migrations"))


def additive_only(before: frozenset, after: frozenset) -> bool:
    """Every pre-existing column/index/constraint survives unchanged (expand-only)."""
    return before <= after


# ------------------------------------------------------------------- app ----
def artisan(tree: Path, env: dict[str, str], *args: str, log: Path) -> bool:
    with log.open("ab") as out:
        done = subprocess.run(
            ["php", "artisan", *args, "--no-interaction", "--no-ansi"],
            cwd=tree, env=env, stdout=out, stderr=subprocess.STDOUT,
            timeout=ARTISAN_TIMEOUT, check=False,
        )
    return done.returncode == 0


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class Server:
    def __init__(self, tree: Path, env: dict[str, str], port: int, log: Path) -> None:
        self.port = port
        self.log = log.open("ab")
        self.proc = subprocess.Popen(
            ["php", "-S", f"127.0.0.1:{port}", "-t", "public", "public/index.php"],
            cwd=tree, env=env, stdout=self.log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    def get(self, path: str) -> tuple[int, str, str]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            conn.request("GET", path, headers={"Accept": "text/html", "Host": f"127.0.0.1:{self.port}"})
            response = conn.getresponse()
            body = response.read(200_000).decode("utf-8", "replace")
            return response.status, response.getheader("Location") or "", body
        finally:
            conn.close()

    def wait_ready(self) -> bool:
        deadline = time.monotonic() + SERVER_START_SECONDS
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                return False
            try:
                if self.get("/up")[0] == 200:
                    return True
            except OSError:
                pass
            time.sleep(0.5)
        return False

    def stop(self) -> None:
        if self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, 15)
                self.proc.wait(timeout=10)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(self.proc.pid, 9)
                except ProcessLookupError:
                    pass
        self.log.close()


def http_checks(server: Server, *, workspace_route_expected: bool) -> dict[str, str]:
    """Return {check: PASS|FAIL:<class>}. Only unauthenticated, read-only GETs."""
    results: dict[str, str] = {}

    def check(name: str, path: str, ok) -> None:
        try:
            code, location, body = server.get(path)
        except OSError:
            results[name] = "FAIL:UNREACHABLE"
            return
        if any(marker in body for marker in FORBIDDEN_BODY):
            results[name] = "FAIL:ERROR_PAGE_LEAK"
        elif ok(code, location):
            results[name] = "PASS"
        else:
            results[name] = f"FAIL:HTTP_{code}"

    check("HTTP_HEALTH_UP", "/up", lambda c, _l: c == 200)
    check("HTTP_LOGIN_PAGE", "/login", lambda c, _l: c == 200)
    check("HTTP_ROOT_NO_SERVER_ERROR", "/", lambda c, _l: c < 500)
    if workspace_route_expected:
        check(
            "HTTP_WORKSPACE_REQUIRES_LOGIN",
            "/services/kmj-codebridge/workspace",
            lambda c, loc: c in (301, 302) and "/login" in loc,
        )
    return results


def run_checks(label: str, tree: Path, env: dict[str, str], scratch: Path, *, workspace: bool) -> bool:
    port = free_port()
    env = {**env, "APP_URL": f"http://127.0.0.1:{port}"}
    server = Server(tree, env, port, scratch / f"server-{label}.log")
    try:
        if not server.wait_ready():
            status(f"{label}_SERVER_START", "FAIL")
            return False
        results = http_checks(server, workspace_route_expected=workspace)
    finally:
        server.stop()
    ok = True
    for name, value in results.items():
        status(f"{label}_{name}", value)
        ok &= value == "PASS"
    return ok


def tail(path: Path, lines: int = 25) -> None:
    if os.environ.get("KMJ_REHEARSAL_VERBOSE") == "1" and path.is_file():
        # Disposable run only: exception lines first (they carry the 500 cause).
        rows = path.read_text("utf-8", "replace").splitlines()
        hits = [r[:300] for r in rows if "Exception" in r or "ERROR" in r][:6]
        print(f"--- {path.name} exceptions ---")
        print("\n".join(hits))
        print(f"--- {path.name} (last {lines} lines) ---")
        print("\n".join(r[:300] for r in rows[-lines:]))


def main() -> int:
    if os.geteuid() == 0:
        raise Blocked("ROOT_NOT_ALLOWED")
    if len(sys.argv) != 1:
        raise Blocked("NO_ARGUMENTS_ACCEPTED")
    for tool in ("php", "psql"):
        if shutil.which(tool) is None:
            raise Blocked(f"MISSING_{tool}")
    db = validate_database(dict(os.environ))
    previous = validate_tree(os.environ.get("KMJ_REHEARSAL_PREVIOUS_APP", ""), "PREVIOUS")
    candidate = validate_tree(os.environ.get("KMJ_REHEARSAL_CANDIDATE_APP", ""), "CANDIDATE")
    if previous == candidate:
        raise Blocked("PREVIOUS_AND_CANDIDATE_IDENTICAL")
    live = psql_rows(db, "select current_database()")
    if live != [(db["DB_DATABASE"],)]:
        raise Blocked("DB_IDENTITY_MISMATCH")
    status("REHEARSAL_DATABASE", "DISPOSABLE_CONFIRMED")

    scratch = Path(tempfile.mkdtemp(prefix="kmj-app-rehearsal."))
    os.chmod(scratch, 0o700)
    log = scratch / "artisan.log"
    env = clean_env(db, scratch, 0)
    failures: list[str] = []

    def fail(name: str) -> None:
        failures.append(name)
        status(name, "FAIL")

    try:
        # 1. Baseline with PREVIOUS code.
        if not artisan(previous, env, "migrate", "--force", log=log):
            fail("PREVIOUS_MIGRATE")
            raise RuntimeError
        status("PREVIOUS_MIGRATE", "PASS")
        s0, m0 = schema_snapshot(db), migrations(db)
        if not run_checks("PREVIOUS", previous, env, scratch, workspace=False):
            failures.append("PREVIOUS_HTTP")

        # 2. Forward migration with CANDIDATE code; must be additive.
        if not artisan(candidate, env, "migrate", "--force", log=log):
            fail("CANDIDATE_MIGRATE")
            raise RuntimeError
        status("CANDIDATE_MIGRATE", "PASS")
        s1, m1 = schema_snapshot(db), migrations(db)
        new_migrations = sorted(set(m1) - set(m0))
        status("NEW_MIGRATIONS", str(len(new_migrations)))
        status("SCHEMA_ADDITIONS", str(len(s1 - s0)))
        if set(m0) - set(m1):
            fail("MIGRATION_HISTORY_REMOVED")
        if additive_only(s0, s1):
            status("SCHEMA_CHANGE_ADDITIVE_ONLY", "PASS")
        else:
            status("SCHEMA_REMOVED_OR_ALTERED", str(len(s0 - s1)))
            fail("SCHEMA_CHANGE_ADDITIVE_ONLY")
        if not new_migrations:
            status("CANDIDATE_HAS_NO_NEW_MIGRATIONS", "NOTE")

        # 3. Candidate serves HTTP on the migrated schema.
        has_workspace = (candidate / "routes" / "codebridge-workspace.php").is_file()
        status("CANDIDATE_HAS_WORKSPACE_ROUTES", "YES" if has_workspace else "NO")
        if not run_checks("CANDIDATE", candidate, env, scratch, workspace=has_workspace):
            failures.append("CANDIDATE_HTTP")

        # 4. Code rollback: previous release against the migrated database.
        if run_checks("CODE_ROLLBACK_PREVIOUS", previous, env, scratch, workspace=False):
            status("CODE_ROLLBACK_ON_MIGRATED_SCHEMA", "PASS")
        else:
            failures.append("CODE_ROLLBACK_ON_MIGRATED_SCHEMA")

        # 5. Schema rollback of exactly the candidate's new migrations, then re-apply.
        if new_migrations:
            if not artisan(candidate, env, "migrate:rollback", f"--step={len(new_migrations)}", "--force", log=log):
                fail("SCHEMA_ROLLBACK_COMMAND")
            elif schema_snapshot(db) == s0 and migrations(db) == m0:
                status("SCHEMA_ROLLBACK_RESTORES_BASELINE_EXACTLY", "PASS")
            else:
                fail("SCHEMA_ROLLBACK_RESTORES_BASELINE_EXACTLY")
            if not artisan(candidate, env, "migrate", "--force", log=log):
                fail("SCHEMA_REAPPLY_COMMAND")
            elif schema_snapshot(db) == s1 and migrations(db) == m1:
                status("SCHEMA_REAPPLY_MATCHES_FORWARD_EXACTLY", "PASS")
            else:
                fail("SCHEMA_REAPPLY_MATCHES_FORWARD_EXACTLY")
    except RuntimeError:
        failures.append("REHEARSAL_STEP_FAILED")
    except subprocess.TimeoutExpired:
        failures.append("COMMAND_TIMEOUT")
    finally:
        tail(log)
        for name in sorted(p.name for p in scratch.glob("server-*.log")):
            tail(scratch / name)
        shutil.rmtree(scratch, ignore_errors=True)

    status("APP_AUTHENTICATED_QA", "NOT_VERIFIED")
    status("RESTORE_FROM_BACKUP", "NOT_VERIFIED")
    status("PRODUCTION_DATABASE_TOUCHED", "NO")
    status("ROLLBACK_VERIFIED_FLAG", "NOT_SET_BY_THIS_SCRIPT")
    status("FAILURES", ",".join(failures) if failures else "NONE")
    status("APP_HTTP_DB_ROLLBACK_REHEARSAL", "PASS" if not failures else "FAIL")
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Blocked as exc:
        status("APP_HTTP_DB_ROLLBACK_REHEARSAL", f"BLOCKED:{exc}")
        sys.exit(2)
