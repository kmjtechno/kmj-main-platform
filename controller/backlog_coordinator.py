"""Curated GitHub backlog -> durable autonomy queue with CodeBridge health gating."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any

from controller.task_queue import TaskQueue

EXPECTED_REPOSITORY = "kmjtechno/kmj-main-platform"
EXPECTED_DEVICE = "main-platform-kmjtechnonetgmailcom"
EXPECTED_PROJECT = "kmj-main-platform"
EXPECTED_CODEBRIDGE_BRANCH = "main"
ALLOWED_KINDS = {"plan", "review", "text", "patch"}
ALLOWED_CLASSIFICATIONS = {"confidential", "public"}
SHA = re.compile(r"^[0-9a-f]{40}$")
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class BacklogError(RuntimeError):
    pass


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_backlog(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 262144:
        raise BacklogError("BACKLOG_FILE_UNSAFE")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BacklogError("BACKLOG_INVALID_JSON") from exc
    if not isinstance(data, dict) or set(data) != {
        "schema_version", "repository", "codebridge", "tasks"
    }:
        raise BacklogError("BACKLOG_SCHEMA_INVALID")
    if data["schema_version"] != 1 or data["repository"] != EXPECTED_REPOSITORY:
        raise BacklogError("BACKLOG_REPOSITORY_MISMATCH")
    identity = data["codebridge"]
    if not isinstance(identity, dict) or set(identity) != {"device", "project", "branch"}:
        raise BacklogError("BACKLOG_CODEBRIDGE_SCHEMA_INVALID")
    if identity != {
        "device": EXPECTED_DEVICE,
        "project": EXPECTED_PROJECT,
        "branch": EXPECTED_CODEBRIDGE_BRANCH,
    }:
        raise BacklogError("BACKLOG_CODEBRIDGE_IDENTITY_MISMATCH")
    tasks = data["tasks"]
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 64:
        raise BacklogError("BACKLOG_TASK_COUNT_INVALID")
    seen = set()
    for task in tasks:
        if not isinstance(task, dict) or set(task) != {
            "id", "project", "kind", "prompt", "data_classification",
            "max_attempts", "auto_enqueue",
        }:
            raise BacklogError("BACKLOG_TASK_SCHEMA_INVALID")
        task_id = task["id"]
        if not isinstance(task_id, str) or not ID.fullmatch(task_id) or task_id in seen:
            raise BacklogError("BACKLOG_TASK_ID_INVALID")
        seen.add(task_id)
        if task["project"] != EXPECTED_PROJECT:
            raise BacklogError("BACKLOG_TASK_PROJECT_MISMATCH")
        if task["kind"] not in ALLOWED_KINDS:
            raise BacklogError("BACKLOG_TASK_KIND_DENIED")
        prompt = task["prompt"]
        if (not isinstance(prompt, str) or not prompt.strip()
                or len(prompt.encode("utf-8")) > 65536):
            raise BacklogError("BACKLOG_PROMPT_INVALID")
        if task["data_classification"] not in ALLOWED_CLASSIFICATIONS:
            raise BacklogError("BACKLOG_CLASSIFICATION_INVALID")
        if type(task["max_attempts"]) is not int or not 1 <= task["max_attempts"] <= 3:
            raise BacklogError("BACKLOG_MAX_ATTEMPTS_INVALID")
        if type(task["auto_enqueue"]) is not bool:
            raise BacklogError("BACKLOG_AUTO_ENQUEUE_INVALID")
    return data


def load_codebridge_status(
    path: Path | str,
    *,
    now: float | None = None,
    max_age_seconds: float = 900,
) -> dict[str, Any]:
    now = time.time() if now is None else now
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise BacklogError("CODEBRIDGE_STATUS_UNAVAILABLE")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BacklogError("CODEBRIDGE_STATUS_INVALID") from exc
    expected = {
        "schema_version", "repository", "device", "project", "branch",
        "connection", "version", "writable", "gates", "checkout_sha",
        "observed_utc_epoch", "source",
    }
    if not isinstance(data, dict) or set(data) != expected:
        raise BacklogError("CODEBRIDGE_STATUS_SCHEMA_INVALID")
    if data["schema_version"] != 1 or data["repository"] != EXPECTED_REPOSITORY:
        raise BacklogError("CODEBRIDGE_REPOSITORY_MISMATCH")
    if (data["device"], data["project"], data["branch"]) != (
        EXPECTED_DEVICE, EXPECTED_PROJECT, EXPECTED_CODEBRIDGE_BRANCH
    ):
        raise BacklogError("CODEBRIDGE_IDENTITY_MISMATCH")
    if data["connection"] != "connected" or data["writable"] is not True:
        raise BacklogError("CODEBRIDGE_NOT_READY")
    if (not isinstance(data["version"], str) or not data["version"]
            or not isinstance(data["source"], str) or not data["source"]):
        raise BacklogError("CODEBRIDGE_STATUS_INVALID")
    if not isinstance(data["gates"], list) or sorted(data["gates"]) != ["fast", "full", "platform"]:
        raise BacklogError("CODEBRIDGE_GATES_MISMATCH")
    if not isinstance(data["checkout_sha"], str) or not SHA.fullmatch(data["checkout_sha"]):
        raise BacklogError("CODEBRIDGE_CHECKOUT_SHA_INVALID")
    observed = data["observed_utc_epoch"]
    if not isinstance(observed, (int, float)) or observed > now + 60:
        raise BacklogError("CODEBRIDGE_STATUS_TIME_INVALID")
    if now - observed > max_age_seconds:
        raise BacklogError("CODEBRIDGE_STATUS_STALE")
    return data


def _safe_evidence(path: Path, state_root: Path, task_id: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise BacklogError("EVIDENCE_FILE_UNSAFE")
    resolved = path.resolve()
    root = state_root.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise BacklogError("EVIDENCE_OUTSIDE_STATE_ROOT")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BacklogError("EVIDENCE_INVALID") from exc
    if not isinstance(data, dict) or data.get("task_id") != task_id:
        raise BacklogError("EVIDENCE_TASK_MISMATCH")
    if data.get("product_complete") is not False:
        raise BacklogError("EVIDENCE_PRODUCT_COMPLETION_FORBIDDEN")
    stage = data.get("stage")
    if stage == "candidate_tested":
        required = {"task_id", "stage", "validation_sha256", "base_sha", "product_complete"}
        if set(data) != required:
            raise BacklogError("CANDIDATE_EVIDENCE_SCHEMA_INVALID")
        if (not isinstance(data["validation_sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", data["validation_sha256"])
                or not isinstance(data["base_sha"], str) or not SHA.fullmatch(data["base_sha"])):
            raise BacklogError("CANDIDATE_EVIDENCE_INVALID")
    elif stage == "release":
        required = {
            "task_id", "stage", "release_sha", "deployed",
            "health_verified", "product_complete",
        }
        if set(data) != required or data["deployed"] is not True or data["health_verified"] is not True:
            raise BacklogError("RELEASE_EVIDENCE_INVALID")
        if not isinstance(data["release_sha"], str) or not SHA.fullmatch(data["release_sha"]):
            raise BacklogError("RELEASE_EVIDENCE_INVALID")
    else:
        raise BacklogError("EVIDENCE_STAGE_INVALID")
    return data


class BacklogCoordinator:
    def __init__(
        self,
        *,
        backlog_path: Path | str,
        codebridge_status_path: Path | str,
        queue_db: Path | str,
        state_root: Path | str,
        status_path: Path | str,
        max_codebridge_age: float = 900,
    ):
        self.backlog_path = Path(backlog_path)
        self.codebridge_status_path = Path(codebridge_status_path)
        self.queue = TaskQueue(queue_db)
        self.state_root = Path(state_root)
        self.status_path = Path(status_path)
        self.max_codebridge_age = max_codebridge_age

    def sync_once(self, *, now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        backlog = load_backlog(self.backlog_path)
        codebridge = load_codebridge_status(
            self.codebridge_status_path,
            now=now,
            max_age_seconds=self.max_codebridge_age,
        )
        statuses = []
        for item in backlog["tasks"]:
            task_id = "backlog:" + item["id"]
            payload = {
                "kind": item["kind"],
                "prompt": item["prompt"],
                "data_classification": item["data_classification"],
                "backlog_id": item["id"],
                "repository": EXPECTED_REPOSITORY,
                "codebridge_project": EXPECTED_PROJECT,
            }
            if item["auto_enqueue"]:
                self.queue.enqueue(
                    task_id,
                    item["project"],
                    payload,
                    max_attempts=item["max_attempts"],
                )
            queued = self.queue.get(task_id)
            stage = "ready"
            attempts = 0
            failure_code = None
            if queued is not None:
                attempts = queued["attempts"]
                raw_error = queued["error"]
                if (isinstance(raw_error, str) and 1 <= len(raw_error) <= 64
                        and all(ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for ch in raw_error)):
                    failure_code = raw_error
                elif raw_error:
                    failure_code = "INTERNAL_ERROR"
                if queued["state"] == "completed":
                    stage = "artifact_ready"
                else:
                    stage = queued["state"]
            evidence_path = self.state_root / "backlog-evidence" / (item["id"] + ".json")
            evidence = _safe_evidence(evidence_path, self.state_root, item["id"])
            if evidence is not None:
                stage = evidence["stage"]
            statuses.append({
                "id": item["id"],
                "stage": stage,
                "attempts": attempts,
                "failure_code": failure_code,
                "tests_executed": evidence is not None and stage in {"candidate_tested", "release"},
                "product_complete": False,
            })
        report = {
            "schema_version": 1,
            "repository": EXPECTED_REPOSITORY,
            "codebridge": {
                "device": codebridge["device"],
                "project": codebridge["project"],
                "branch": codebridge["branch"],
                "connection": codebridge["connection"],
                "version": codebridge["version"],
                "checkout_sha": codebridge["checkout_sha"],
                "observed_utc_epoch": codebridge["observed_utc_epoch"],
            },
            "backlog_sha256": hashlib.sha256(self.backlog_path.read_bytes()).hexdigest(),
            "tasks": statuses,
            "product_complete": False,
            "updated_utc_epoch": now,
        }
        _atomic_json(self.status_path, report)
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backlog", required=True, type=Path)
    parser.add_argument("--codebridge-status", required=True, type=Path)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--status", required=True, type=Path)
    parser.add_argument("--max-codebridge-age", type=float, default=900)
    args = parser.parse_args()
    os.umask(0o077)
    coordinator = BacklogCoordinator(
        backlog_path=args.backlog,
        codebridge_status_path=args.codebridge_status,
        queue_db=args.db,
        state_root=args.state_root,
        status_path=args.status,
        max_codebridge_age=args.max_codebridge_age,
    )
    try:
        report = coordinator.sync_once()
    except BacklogError as exc:
        _atomic_json(args.status, {
            "schema_version": 1,
            "repository": EXPECTED_REPOSITORY,
            "healthy": False,
            "error_code": str(exc),
            "product_complete": False,
            "updated_utc_epoch": time.time(),
        })
        raise SystemExit(2) from None
    print(json.dumps({
        "repository": report["repository"],
        "codebridge_project": report["codebridge"]["project"],
        "tasks": [{"id": item["id"], "stage": item["stage"]} for item in report["tasks"]],
        "product_complete": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
