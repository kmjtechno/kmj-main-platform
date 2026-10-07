"""Outbound GitHub control bridge for the durable KMJ autonomy queue.

The bridge reads one pinned repository/ref through an isolated bare Git mirror.
It never checks out, resets, cleans, merges, deploys, or executes manifest text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import tempfile
import time
from typing import Any

import httpx

from controller.task_queue import TaskQueue

LOG = logging.getLogger("kmj.github-control")
COMMAND_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_KINDS = {"plan", "review", "text", "patch"}
MAX_MANIFEST_BYTES = 262144
MAX_COMMANDS = 32
MAX_PROMPT_BYTES = 65536


class ControlError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _git(args: list[str], *, timeout: int = 45, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if check and result.returncode:
        raise ControlError("GITHUB_FETCH_FAILED")
    return result


class GitMirrorSource:
    def __init__(self, mirror: Path, remote_url: str, ref: str, manifest_path: str):
        self.mirror = Path(mirror)
        self.remote_url = remote_url
        self.ref = ref
        self.manifest_path = manifest_path
        if not ref or ref.startswith("-") or ".." in ref or any(ch.isspace() for ch in ref):
            raise ValueError("INVALID_CONTROL_REF")
        if (not manifest_path or manifest_path.startswith("/")
                or ".." in Path(manifest_path).parts):
            raise ValueError("INVALID_MANIFEST_PATH")

    @property
    def remote_ref(self) -> str:
        return "refs/remotes/origin/kmj-control"

    def _ensure_mirror(self) -> None:
        self.mirror.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.mirror.parent, 0o700)
        if not self.mirror.exists():
            self.mirror.mkdir(mode=0o700)
            _git(["init", "--bare", str(self.mirror)])
            _git(["-C", str(self.mirror), "remote", "add", "origin", self.remote_url])
        if not (self.mirror / "HEAD").is_file():
            raise ControlError("CONTROL_MIRROR_INVALID")
        remote = _git(["-C", str(self.mirror), "remote", "get-url", "origin"]).stdout.strip()
        if remote != self.remote_url:
            raise ControlError("CONTROL_REMOTE_MISMATCH")

    def fetch(self, previous_sha: str | None) -> tuple[str, bytes]:
        self._ensure_mirror()
        _git([
            "-C", str(self.mirror), "fetch", "--no-tags", "--prune", "origin",
            f"+refs/heads/{self.ref}:{self.remote_ref}",
        ])
        source_sha = _git(["-C", str(self.mirror), "rev-parse", self.remote_ref]).stdout.strip()
        if not SHA.fullmatch(source_sha):
            raise ControlError("CONTROL_SOURCE_SHA_INVALID")
        if previous_sha and previous_sha != source_sha:
            if not SHA.fullmatch(previous_sha):
                raise ControlError("CONTROL_PREVIOUS_SHA_INVALID")
            ancestry = _git(
                ["-C", str(self.mirror), "merge-base", "--is-ancestor", previous_sha, source_sha],
                check=False,
            )
            if ancestry.returncode == 1:
                raise ControlError("CONTROL_SOURCE_HISTORY_REWIND")
            if ancestry.returncode != 0:
                raise ControlError("CONTROL_ANCESTRY_UNKNOWN")
        spec = f"{source_sha}:{self.manifest_path}"
        size = _git(["-C", str(self.mirror), "cat-file", "-s", spec]).stdout.strip()
        if not size.isdigit() or int(size) > MAX_MANIFEST_BYTES:
            raise ControlError("CONTROL_MANIFEST_TOO_LARGE")
        payload = _git(["-C", str(self.mirror), "show", spec]).stdout.encode("utf-8")
        if len(payload) > MAX_MANIFEST_BYTES:
            raise ControlError("CONTROL_MANIFEST_TOO_LARGE")
        return source_sha, payload


def _exact_keys(value: dict[str, Any], expected: set[str], code: str) -> None:
    if set(value) != expected:
        raise ControlError(code)


def _canonical_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def normalize_manifest(
    raw: bytes,
    *,
    repository: str,
    ref: str,
    allowed_projects: set[str],
) -> list[dict[str, Any]]:
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ControlError("CONTROL_MANIFEST_TOO_LARGE")
    try:
        manifest = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ControlError("CONTROL_MANIFEST_INVALID") from None
    if not isinstance(manifest, dict):
        raise ControlError("CONTROL_MANIFEST_INVALID")
    _exact_keys(manifest, {"schema_version", "repository", "ref", "commands"}, "CONTROL_MANIFEST_KEYS_INVALID")
    if manifest["schema_version"] != 1:
        raise ControlError("CONTROL_SCHEMA_UNSUPPORTED")
    if manifest["repository"] != repository:
        raise ControlError("CONTROL_REPOSITORY_MISMATCH")
    if manifest["ref"] != ref:
        raise ControlError("CONTROL_REF_MISMATCH")
    commands = manifest["commands"]
    if not isinstance(commands, list) or not 1 <= len(commands) <= MAX_COMMANDS:
        raise ControlError("CONTROL_COMMAND_COUNT_INVALID")

    normalized: list[dict[str, Any]] = []
    command_ids: set[str] = set()
    task_ids: set[str] = set()
    mutators = 0
    for command in commands:
        if not isinstance(command, dict):
            raise ControlError("CONTROL_COMMAND_INVALID")
        operation = command.get("operation")
        if operation not in {"pause", "resume", "enqueue", "status"}:
            raise ControlError("CONTROL_OPERATION_UNSUPPORTED")
        expected = {"id", "operation", "task"} if operation == "enqueue" else {"id", "operation"}
        _exact_keys(command, expected, "CONTROL_COMMAND_KEYS_INVALID")
        command_id = command.get("id")
        if not isinstance(command_id, str) or not COMMAND_ID.fullmatch(command_id):
            raise ControlError("CONTROL_COMMAND_ID_INVALID")
        if command_id in command_ids:
            raise ControlError("CONTROL_COMMAND_ID_DUPLICATE")
        command_ids.add(command_id)
        if operation in {"pause", "resume"}:
            mutators += 1
            if mutators > 1:
                raise ControlError("CONTROL_STATE_AMBIGUOUS")
        clean: dict[str, Any] = {"id": command_id, "operation": operation}
        if operation == "enqueue":
            task = command.get("task")
            if not isinstance(task, dict):
                raise ControlError("CONTROL_TASK_INVALID")
            allowed = {"id", "project", "kind", "prompt", "data_classification", "max_attempts"}
            if not set(task).issubset(allowed) or not {"id", "project", "kind", "prompt"}.issubset(task):
                raise ControlError("CONTROL_TASK_KEYS_INVALID")
            task_id = task.get("id")
            project = task.get("project")
            kind = task.get("kind")
            prompt = task.get("prompt")
            classification = task.get("data_classification", "confidential")
            max_attempts = task.get("max_attempts", 3)
            if not isinstance(task_id, str) or not COMMAND_ID.fullmatch(task_id):
                raise ControlError("CONTROL_TASK_ID_INVALID")
            if task_id in task_ids:
                raise ControlError("CONTROL_TASK_ID_DUPLICATE")
            task_ids.add(task_id)
            if project not in allowed_projects:
                raise ControlError("CONTROL_PROJECT_DENIED")
            if kind not in ALLOWED_KINDS:
                raise ControlError("CONTROL_TASK_KIND_DENIED")
            if (not isinstance(prompt, str) or not prompt.strip()
                    or len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES):
                raise ControlError("CONTROL_PROMPT_INVALID")
            if classification not in {"confidential", "public"}:
                raise ControlError("CONTROL_CLASSIFICATION_INVALID")
            if type(max_attempts) is not int or not 1 <= max_attempts <= 10:
                raise ControlError("CONTROL_MAX_ATTEMPTS_INVALID")
            clean["task"] = {
                "id": task_id,
                "project": project,
                "payload": {
                    "kind": kind,
                    "prompt": prompt,
                    "data_classification": classification,
                },
                "max_attempts": max_attempts,
            }
        clean["content_hash"] = _canonical_hash(clean)
        normalized.append(clean)
    return normalized


class GitHubStatusWriter:
    """Optional issue-comment status publication using a dedicated credential file."""

    def __init__(self, repository: str, token_file: Path | None, issue_number: int | None):
        self.repository = repository
        self.token_file = Path(token_file) if token_file else None
        self.issue_number = issue_number if issue_number and issue_number > 0 else None

    def _token(self) -> str | None:
        if not self.token_file or not self.issue_number:
            return None
        try:
            if self.token_file.is_symlink():
                raise ControlError("STATUS_TOKEN_FILE_UNSAFE")
            info = self.token_file.stat()
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
                raise ControlError("STATUS_TOKEN_FILE_UNSAFE")
            token = self.token_file.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return None
        if not token or len(token) > 4096 or any(ch.isspace() for ch in token):
            raise ControlError("STATUS_TOKEN_INVALID")
        return token

    def publish(self, report: dict[str, Any]) -> str:
        token = self._token()
        if token is None:
            return "read_only"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "kmj-github-control/1",
        }
        safe = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if len(safe.encode("utf-8")) > 30000:
            raise ControlError("STATUS_REPORT_TOO_LARGE")
        owner, name = self.repository.split("/", 1)
        base = f"https://api.github.com/repos/{owner}/{name}"
        try:
            with httpx.Client(timeout=20, headers=headers, follow_redirects=False) as client:
                repo = client.get(base)
                repo.raise_for_status()
                if repo.json().get("full_name") != self.repository:
                    raise ControlError("STATUS_REPOSITORY_MISMATCH")
                issue = client.get(f"{base}/issues/{self.issue_number}")
                issue.raise_for_status()
                issue_payload = issue.json()
                if issue_payload.get("pull_request") is not None:
                    raise ControlError("STATUS_TARGET_NOT_ISSUE")
                body = "KMJ GitHub control status\n\n" + safe
                response = client.post(
                    f"{base}/issues/{self.issue_number}/comments",
                    json={"body": body},
                )
                response.raise_for_status()
        except ControlError:
            raise
        except (httpx.HTTPError, ValueError, KeyError):
            raise ControlError("STATUS_WRITE_FAILED") from None
        return "write_verified"


def build_report(
    queue: TaskQueue,
    *,
    repository: str,
    ref: str,
    source_sha: str | None,
    connectivity: str,
    stale: bool,
    writeback: str,
) -> dict[str, Any]:
    snapshot = queue.sanitized_status(limit=50)
    return {
        "schema_version": 1,
        "repository": repository,
        "ref": ref,
        "source_sha": source_sha,
        "connectivity": connectivity,
        "stale": bool(stale),
        "paused": snapshot["paused"],
        "last_validated_source_sha": snapshot["last_source_sha"],
        "last_applied_epoch": snapshot["last_applied_epoch"],
        "last_error_code": snapshot["last_error_code"],
        "writeback": writeback,
        "tasks": snapshot["tasks"],
        "product_complete": False,
    }


class GitHubControlBridge:
    def __init__(
        self,
        queue: TaskQueue,
        source: GitMirrorSource,
        status_path: Path,
        *,
        repository: str,
        ref: str,
        allowed_projects: set[str],
        writer: GitHubStatusWriter | None = None,
    ):
        self.queue = queue
        self.source = source
        self.status_path = Path(status_path)
        self.repository = repository
        self.ref = ref
        self.allowed_projects = set(allowed_projects)
        self.writer = writer or GitHubStatusWriter(repository, None, None)

    def _persist_report(self, report: dict[str, Any]) -> None:
        atomic_json(self.status_path, {**report, "updated_utc_epoch": time.time()})

    def poll_once(self) -> dict[str, Any]:
        previous = self.queue.control_snapshot().get("last_source_sha")
        try:
            source_sha, raw = self.source.fetch(previous)
            commands = normalize_manifest(
                raw,
                repository=self.repository,
                ref=self.ref,
                allowed_projects=self.allowed_projects,
            )
            result = self.queue.apply_control_batch(
                self.repository,
                self.ref,
                source_sha,
                commands,
            )
            wants_status = any(
                command["operation"] == "status" and command["id"] in result["applied_ids"]
                for command in commands
            )
            report = build_report(
                self.queue,
                repository=self.repository,
                ref=self.ref,
                source_sha=source_sha,
                connectivity="online",
                stale=False,
                writeback="not_requested",
            )
            if wants_status:
                try:
                    mode = self.writer.publish(report)
                except ControlError as exc:
                    mode = exc.code
                report["writeback"] = mode
            self._persist_report(report)
            LOG.info(
                "control poll applied=%d duplicate=%d paused=%s source=%s",
                len(result["applied_ids"]),
                len(result["duplicate_ids"]),
                result["paused"],
                source_sha[:12],
            )
            return report
        except ValueError as exc:
            code = str(exc)
            if not code.startswith("CONTROL_"):
                code = "CONTROL_BATCH_REJECTED"
            self.queue.set_control_error(code)
            snapshot = self.queue.control_snapshot()
            report = build_report(
                self.queue,
                repository=self.repository,
                ref=self.ref,
                source_sha=snapshot.get("last_source_sha"),
                connectivity="degraded",
                stale=True,
                writeback="not_attempted",
            )
            report["poll_error_code"] = code
            self._persist_report(report)
            LOG.warning("control batch rejected code=%s", code)
            return report
        except ControlError as exc:
            self.queue.set_control_error(exc.code)
            snapshot = self.queue.control_snapshot()
            report = build_report(
                self.queue,
                repository=self.repository,
                ref=self.ref,
                source_sha=snapshot.get("last_source_sha"),
                connectivity="degraded",
                stale=True,
                writeback="not_attempted",
            )
            report["poll_error_code"] = exc.code
            self._persist_report(report)
            LOG.warning("control poll rejected code=%s", exc.code)
            return report
        except Exception:
            self.queue.set_control_error("CONTROL_INTERNAL_ERROR")
            snapshot = self.queue.control_snapshot()
            report = build_report(
                self.queue,
                repository=self.repository,
                ref=self.ref,
                source_sha=snapshot.get("last_source_sha"),
                connectivity="degraded",
                stale=True,
                writeback="not_attempted",
            )
            report["poll_error_code"] = "CONTROL_INTERNAL_ERROR"
            self._persist_report(report)
            LOG.exception("control poll internal failure")
            return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--mirror", required=True, type=Path)
    parser.add_argument("--repo", default="kmjtechno/kmj-main-platform")
    parser.add_argument("--ref", default="feat/modelfabric-autonomy-20261007")
    parser.add_argument("--manifest", default="ops/github-control/kmj-autonomy.json")
    parser.add_argument("--remote-url", default="https://github.com/kmjtechno/kmj-main-platform.git")
    parser.add_argument("--allowed-project", action="append", default=["kmj-main-platform"])
    parser.add_argument("--poll-seconds", type=float, default=15.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--status-token-file",
        type=Path,
        default=Path(os.environ["KMJ_GITHUB_STATUS_TOKEN_FILE"])
        if os.environ.get("KMJ_GITHUB_STATUS_TOKEN_FILE")
        else None,
    )
    parser.add_argument(
        "--status-issue",
        type=int,
        default=int(os.environ["KMJ_GITHUB_STATUS_ISSUE"])
        if os.environ.get("KMJ_GITHUB_STATUS_ISSUE")
        else None,
    )
    args = parser.parse_args()
    if not 2 <= args.poll_seconds <= 3600:
        parser.error("--poll-seconds must be 2..3600")
    os.umask(0o077)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    queue = TaskQueue(args.db)
    source = GitMirrorSource(args.mirror, args.remote_url, args.ref, args.manifest)
    writer = GitHubStatusWriter(args.repo, args.status_token_file, args.status_issue)
    bridge = GitHubControlBridge(
        queue,
        source,
        args.state_dir / "github-control-status.json",
        repository=args.repo,
        ref=args.ref,
        allowed_projects=set(args.allowed_project),
        writer=writer,
    )
    stopped = False

    def stop(*_args):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while True:
        bridge.poll_once()
        if args.once or stopped:
            break
        deadline = time.monotonic() + args.poll_seconds
        while not stopped and time.monotonic() < deadline:
            time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))
        if stopped:
            break


if __name__ == "__main__":
    main()
