#!/usr/bin/env python3
"""Isolated pointer-rollback rehearsal for release candidate 39b88b36d071.

Proves ONLY the release-pointer mechanics and artifact readability of both the
live release (rollback target) and the candidate, in a private scratch tree:

  scratch/releases/<id> -> real release directory (read-only use)
  scratch/current       -> flipped atomically prev -> candidate -> prev -> candidate

and, for every state, serves ``apps/platform/public`` from scratch/current on a
loopback ephemeral port and checks the activation-controller style health
artifacts byte-for-byte. It does NOT boot Laravel, touch any database, run
migrations, authenticate, or validate the application. Therefore it can never
set ``rollbackVerified`` for the owner approval on its own: app-level rollback
(DB restore, authenticated QA) remains separate required evidence.

Never writes under /home/kmjprod, never changes /home/kmjprod/current, never
restarts services, never reads .env, never prints file contents.
"""
from __future__ import annotations

import hashlib
import http.server
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path("/home/kmjprod")
PREVIOUS = "platform-574e443a2c75"
PREVIOUS_SHA = "574e443a2c75a387aa4741e86d426c06a33e5b4c"
CANDIDATE = "platform-39b88b36d071"
CANDIDATE_SHA = "39b88b36d071d3f78f2392d609d3febc2c530165"
ARTIFACTS = (
    "apps/platform/artisan",
    "apps/platform/vendor/autoload.php",
    "apps/platform/public/build/manifest.json",
    "apps/platform/public/assets/kmj-codebridge-icon.png",
)
HEALTH_URLS = ("/assets/kmj-codebridge-icon.png", "/build/manifest.json")
MIN_FREE_BYTES = 64 * 1024 * 1024


class Blocked(RuntimeError):
    pass


def status(key: str, value: str) -> None:
    print(f"{key}={value}")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head(tree: Path) -> str | None:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={tree}", "-c", "core.fsmonitor=false", "-C", str(tree), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False, timeout=60,
        env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "GIT_CONFIG_NOSYSTEM": "1",
             "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"},
    )
    return result.stdout.strip() if result.returncode == 0 else None


def check_release(root: Path, name: str, expected_sha: str, label: str) -> Path:
    tree = root / "releases" / name
    try:
        info = os.lstat(tree)
    except FileNotFoundError:
        raise Blocked(f"{label}_MISSING") from None
    if not stat.S_ISDIR(info.st_mode):
        raise Blocked(f"{label}_NOT_DIRECTORY")
    if info.st_mode & 0o022:
        raise Blocked(f"{label}_GROUP_OR_WORLD_WRITABLE")
    if git_head(tree) != expected_sha:
        raise Blocked(f"{label}_SHA_MISMATCH")
    for item in ARTIFACTS:
        path = tree / item
        if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
            raise Blocked(f"{label}_ARTIFACT_MISSING")
    return tree


def flip(current: Path, target_rel: str) -> None:
    """Atomically point scratch/current at releases/<id> (create + rename)."""
    temp = current.parent / f".current.{secrets.token_hex(6)}"
    os.symlink(target_rel, temp)
    os.replace(temp, current)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # pragma: no cover - silence
        pass

    def list_directory(self, path):  # never list directories
        self.send_error(404)
        return None


def serve(directory: Path) -> tuple[http.server.ThreadingHTTPServer, int]:
    handler = lambda *a, **k: QuietHandler(*a, directory=str(directory), **k)  # noqa: E731
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def fetch(port: int, path: str) -> tuple[int, bytes]:
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, b""


def health(scratch_current: Path, release_tree: Path) -> None:
    public = scratch_current / "apps/platform/public"
    server, port = serve(public)
    try:
        for url in HEALTH_URLS:
            code, body = fetch(port, url)
            if code != 200 or not body:
                raise Blocked("HEALTH_ARTIFACT_NOT_SERVED")
            expected = release_tree / "apps/platform/public" / url.lstrip("/")
            if hashlib.sha256(body).hexdigest() != digest(expected):
                raise Blocked("HEALTH_ARTIFACT_DIGEST_MISMATCH")
        for hostile in ("/.env", "/../.env", "/%2e%2e/.env", "/../../.env"):
            code, _ = fetch(port, hostile)
            if code == 200:
                raise Blocked("ENV_REACHABLE_THROUGH_PUBLIC_ROOT")
    finally:
        server.shutdown()
        server.server_close()


def rehearse(root: Path, scratch_parent: Path, previous=PREVIOUS, previous_sha=PREVIOUS_SHA,
             candidate=CANDIDATE, candidate_sha=CANDIDATE_SHA) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    live = root / "current"
    if not live.is_symlink():
        raise Blocked("LIVE_POINTER_NOT_SYMLINK")
    before = os.readlink(live)
    if not re.fullmatch(r"(?:" + re.escape(str(root)) + r"/)?releases/" + re.escape(previous), before):
        raise Blocked("LIVE_NOT_ON_EXPECTED_PREVIOUS_RELEASE")
    out.append(("LIVE_POINTER_BEFORE", before))

    prev_tree = check_release(root, previous, previous_sha, "PREVIOUS")
    cand_tree = check_release(root, candidate, candidate_sha, "CANDIDATE")
    out.append(("PREVIOUS_RELEASE_VERIFIED", "PASS"))
    out.append(("CANDIDATE_RELEASE_VERIFIED", "PASS"))

    scratch_real = scratch_parent.resolve()
    if root.resolve() in (scratch_real, *scratch_real.parents) or scratch_real in (root.resolve(),):
        raise Blocked("SCRATCH_INSIDE_PRODUCTION_ROOT")
    info = os.lstat(scratch_parent)
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077):
        raise Blocked("SCRATCH_PARENT_NOT_PRIVATE")
    if shutil.disk_usage(scratch_parent).free < MIN_FREE_BYTES:
        raise Blocked("SCRATCH_FREE_SPACE")

    scratch = Path(tempfile.mkdtemp(prefix="kmj-rollback-39.", dir=scratch_parent))
    try:
        os.chmod(scratch, 0o700)
        (scratch / "releases").mkdir(mode=0o700)
        os.symlink(prev_tree, scratch / "releases" / previous)
        os.symlink(cand_tree, scratch / "releases" / candidate)
        current = scratch / "current"
        sequence = (("previous", previous, prev_tree), ("candidate", candidate, cand_tree),
                    ("rollback_to_previous", previous, prev_tree),
                    ("forward_to_candidate", candidate, cand_tree))
        for label, release, tree in sequence:
            flip(current, f"releases/{release}")
            if os.readlink(current) != f"releases/{release}" or current.resolve() != tree.resolve():
                raise Blocked(f"FLIP_{label.upper()}_FAILED")
            health(current, tree)
            out.append((f"POINTER_{label.upper()}", "PASS"))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if os.readlink(live) != before:
        raise Blocked("LIVE_POINTER_CHANGED_DURING_REHEARSAL")
    out.append(("LIVE_POINTER_AFTER", os.readlink(live)))
    out.append(("SCRATCH_REMOVED", "NO" if scratch.exists() else "YES"))
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        status("ROLLBACK_REHEARSAL", "BLOCKED:NO_ARGUMENTS_ACCEPTED")
        return 2
    home = os.environ.get("HOME", "")
    scratch_parent = Path(home) / "kmj-rollback-scratch"
    try:
        if not home or not scratch_parent.is_dir() or scratch_parent.is_symlink():
            raise Blocked("SCRATCH_PARENT_MISSING")
        lines = rehearse(ROOT, scratch_parent)
    except Blocked as error:
        status("ROLLBACK_REHEARSAL", f"BLOCKED:{error}")
        return 2
    except (OSError, subprocess.SubprocessError):
        status("ROLLBACK_REHEARSAL", "BLOCKED:IO_ERROR")
        return 2
    for key, value in lines:
        status(key, value)
    status("ROLLBACK_POINTER_MECHANICS", "PASS")
    status("APP_BOOT_DB_AUTH_QA", "NOT_ATTEMPTED")
    status("OWNER_APPROVAL_ROLLBACK_VERIFIED_MAY_BE_SET", "NO")
    status("PRODUCTION_CHANGED", "NO")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
