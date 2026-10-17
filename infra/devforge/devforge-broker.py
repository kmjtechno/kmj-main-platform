#!/usr/bin/env python3
"""Local-only, fixed-action KMJ DevForge service broker.

Never accepts paths, URLs, repositories, command strings or shell arguments.
Provision once as root; PHP-FPM can access only the local Unix socket.
"""
import grp
import json
import os
import pathlib
import pwd
import socket
import struct
import subprocess
import threading
import time
import urllib.request

SOCK = "/run/kmj-devforge/control.sock"
WEB_USER = os.environ.get("DEVFORGE_WEB_USER", "www-data")
BASE = pathlib.Path("/opt/kmj-devforge")
DATA = pathlib.Path("/var/lib/kmj-devforge")
CREDENTIALS = DATA / "initial-admin-credentials.txt"
ACTIONS = frozenset(("status", "install", "start", "stop", "restart"))
MUTATIONS = ACTIONS - {"status"}
LOCK = threading.Lock()
RUNTIME = {"last_action": None, "last_error": None, "completed_at": None}
COMPOSE = ["docker", "compose", "--project-name", "kmj-devforge", "-f", str(BASE / "compose.yaml")]


def command(*args, timeout=120):
    return subprocess.run(
        [*args], capture_output=True, text=True, timeout=timeout,
        check=False, cwd=str(BASE),
    )


def service_state():
    try:
        r = command("docker", "inspect", "--format", "{{.State.Status}}", "kmj-devforge-server", timeout=5)
        state = r.stdout.strip() if r.returncode == 0 else "not_installed"
        if state not in ("running", "created", "exited", "restarting", "dead", "paused"):
            state = "unknown"
    except (OSError, subprocess.TimeoutExpired):
        state = "unavailable"
    healthy = False
    if state == "running":
        try:
            with urllib.request.urlopen("http://127.0.0.1:3030/api/healthz", timeout=2) as response:
                healthy = response.status == 200
        except Exception:
            pass
    return {
        "broker_ready": True, "state": state, "healthy": healthy,
        "busy": LOCK.locked(), "last_action": RUNTIME["last_action"],
        "last_error": RUNTIME["last_error"], "access": "loopback_only",
        "completed_at": RUNTIME["completed_at"],
    }


def ensure_preconditions():
    if not (BASE / "compose.yaml").is_file() or (BASE / "compose.yaml").is_symlink():
        raise RuntimeError("COMPOSE_NOT_PROVISIONED")
    if not DATA.is_dir():
        raise RuntimeError("STATE_DIRECTORY_MISSING")
    if os.statvfs(str(BASE)).f_bavail * os.statvfs(str(BASE)).f_frsize < 10 * 1024**3:
        raise RuntimeError("LOW_DISK_SPACE")
    for args in [("docker", "info"), (*COMPOSE, "config", "-q")]:
        try:
            r = command(*args, timeout=12)
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError("DOCKER_UNAVAILABLE") from None
        if r.returncode:
            raise RuntimeError("DOCKER_OR_COMPOSE_UNAVAILABLE")


def verify_running():
    for _ in range(60):
        if service_state()["healthy"]:
            return
        time.sleep(2)
    raise RuntimeError("GIT_FORGE_HEALTH_TIMEOUT")


def create_admin_once():
    if CREDENTIALS.exists():
        return
    result = command(
        *COMPOSE, "exec", "-T", "server",
        "gitea", "admin", "user", "create", "--admin",
        "--username", "kmjadmin", "--email", "kmjtechnonet@gmail.com",
        "--random-password", "--random-password-length", "32", timeout=30,
    )
    if result.returncode:
        # A partial install is not declared successful. No secret is returned on socket.
        raise RuntimeError("INITIAL_ADMIN_CREATION_FAILED")
    fd = os.open(str(CREDENTIALS), os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(result.stdout)
        handle.flush()
        os.fsync(handle.fileno())


def perform(action):
    try:
        ensure_preconditions()
        if action == "install":
            result = command(*COMPOSE, "pull", "server", timeout=300)
            if result.returncode:
                raise RuntimeError("IMAGE_PULL_FAILED")
            result = command(*COMPOSE, "up", "-d", timeout=120)
        elif action in ("start", "stop", "restart"):
            result = command(*COMPOSE, action, timeout=120)
        else:
            raise RuntimeError("ACTION_NOT_ALLOWED")
        if result.returncode:
            raise RuntimeError("CONTAINER_ACTION_FAILED")
        if action != "stop":
            verify_running()
        if action == "install":
            create_admin_once()
        RUNTIME["last_error"] = None
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        # Static reason codes only, never leak command output or credentials.
        code = str(exc) if isinstance(exc, RuntimeError) else "HOST_EXECUTION_FAILED"
        RUNTIME["last_error"] = code[:80]
    finally:
        RUNTIME["completed_at"] = int(time.time())
        LOCK.release()


def reply(request):
    if not isinstance(request, dict) or set(request) != {"action"}:
        return {"ok": False, "error": "INVALID_REQUEST"}
    action = request.get("action")
    if action not in ACTIONS:
        return {"ok": False, "error": "ACTION_NOT_ALLOWED"}
    if action == "status":
        return {"ok": True, **service_state()}
    if not LOCK.acquire(blocking=False):
        return {"ok": False, "error": "OPERATION_IN_PROGRESS"}
    RUNTIME["last_action"] = action
    RUNTIME["last_error"] = None
    threading.Thread(target=perform, args=(action,), daemon=True).start()
    return {"ok": True, "accepted": True, "action": action}


def handle(peer, expected_uid):
    try:
        peer.settimeout(3)
        creds = peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
        _, uid, _ = struct.unpack("3i", creds)
        if uid not in (0, expected_uid):
            response = {"ok": False, "error": "PEER_DENIED"}
        else:
            data = bytearray()
            while len(data) <= 256:
                chunk = peer.recv(257 - len(data))
                if not chunk:
                    break
                data.extend(chunk)
                if b"\n" in data:
                    break
            if len(data) > 256 or b"\n" not in data or data.count(b"\n") != 1:
                response = {"ok": False, "error": "INVALID_FRAME"}
            else:
                try:
                    request = json.loads(data.split(b"\n", 1)[0])
                    response = reply(request)
                except (ValueError, UnicodeDecodeError, TypeError):
                    response = {"ok": False, "error": "INVALID_JSON"}
        peer.sendall((json.dumps(response, separators=(",", ":")) + "\n").encode("utf-8"))
    except (OSError, TimeoutError):
        pass
    finally:
        peer.close()


def main():
    if os.geteuid() != 0:
        raise SystemExit("ROOT_REQUIRED")
    target = pwd.getpwnam(WEB_USER)
    path = pathlib.Path(SOCK)
    if path.exists() or path.is_symlink():
        if path.is_socket():
            path.unlink()
        else:
            raise SystemExit("SOCKET_PATH_CONFLICT")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(SOCK)
        os.chown(SOCK, 0, target.pw_gid)
        os.chmod(SOCK, 0o660)
        server.listen(12)
        while True:
            peer, _ = server.accept()
            threading.Thread(target=handle, args=(peer, target.pw_uid), daemon=True).start()


if __name__ == "__main__":
    main()
