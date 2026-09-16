from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import httpx


REPO = os.getenv("GITHUB_REPOSITORY", "kmjtechno/kmj-main-platform")
API = os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip("/")
DEFAULT_OUTPUT = Path(os.getenv("KMJ_DELIVERY_STATUS_PATH", "/var/tmp/kmj-delivery-control/status.json"))
STAGING_STATUS_URL = os.getenv("KMJ_STAGING_STATUS_URL", "https://staging.kmjtechno.com/info/status")


class Api(Protocol):
    def get(self, path: str) -> Any: ...


class GitHubApi:
    def __init__(self, token: str) -> None:
        if not token:
            raise RuntimeError("GITHUB_TOKEN_NOT_CONFIGURED")
        self.client = httpx.Client(
            timeout=15,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    def get(self, path: str) -> Any:
        response = self.client.get(f"{API}/repos/{REPO}{path}")
        response.raise_for_status()
        return response.json()


def _issue(items: Any) -> dict[str, Any] | None:
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and "pull_request" not in item:
            return item
    return None


def _phase(jobs: Any) -> str | None:
    if not isinstance(jobs, dict):
        return None
    for job in jobs.get("jobs", []):
        if not isinstance(job, dict):
            continue
        for step in job.get("steps", []):
            if isinstance(step, dict) and step.get("status") == "in_progress":
                return str(step.get("name") or "running")
    return None


def _runner_rows(runner_count: int, busy_runner_count: int) -> list[dict[str, Any]]:
    count = max(0, runner_count)
    busy = max(0, min(busy_runner_count, count))
    return [
        {
            "name": f"kmj-vps-runner-{index + 1}",
            "status": "online",
            "busy": index < busy,
        }
        for index in range(count)
    ]


def _ci(checks: Any) -> dict[str, Any]:
    runs = checks.get("check_runs", []) if isinstance(checks, dict) else []
    failed = [
        str(run.get("name") or "unknown")
        for run in runs
        if isinstance(run, dict) and run.get("status") == "completed"
        and run.get("conclusion") not in {"success", "neutral", "skipped"}
    ]
    if failed:
        status = "failure"
    elif any(isinstance(run, dict) and run.get("status") != "completed" for run in runs):
        status = "in_progress"
    elif runs:
        status = "success"
    else:
        status = "unknown"
    return {"status": status, "run_id": None, "failed_checks": failed[:8]}


def build_snapshot(
    api: Api,
    *,
    runner_count: int,
    busy_runner_count: int,
    monitor_payload: dict[str, Any] | None = None,
    captured_at: datetime | None = None,
) -> dict[str, Any]:
    captured_at = captured_at or datetime.now(timezone.utc)
    runs_payload = api.get("/actions/workflows/autonomous-worker.yml/runs?per_page=10")
    runs = runs_payload.get("workflow_runs", []) if isinstance(runs_payload, dict) else []
    latest = runs[0] if runs and isinstance(runs[0], dict) else None

    jobs: dict[str, Any] = {"jobs": []}
    if latest and latest.get("id"):
        jobs = api.get(f"/actions/runs/{int(latest['id'])}/jobs?per_page=20")

    running_issue = _issue(api.get("/issues?state=open&labels=autonomous-running&per_page=10"))
    blocked_issue = _issue(api.get("/issues?state=open&labels=autonomous-blocked&per_page=10"))

    pulls = api.get("/pulls?state=open&per_page=50")
    agent_pr = None
    if isinstance(pulls, list):
        for pull in pulls:
            if not isinstance(pull, dict):
                continue
            ref = str(pull.get("head", {}).get("ref", ""))
            if ref.startswith("agent/auto-"):
                agent_pr = pull
                break

    ci = {"status": "unknown", "run_id": None, "failed_checks": []}
    if agent_pr:
        head_sha = str(agent_pr.get("head", {}).get("sha", ""))
        if head_sha:
            ci = _ci(api.get(f"/commits/{head_sha}/check-runs?per_page=100"))

    main_ref = api.get("/git/ref/heads/main")
    staging_ref = api.get("/git/ref/heads/staging-approved")
    main_sha = str(main_ref.get("object", {}).get("sha", "")) if isinstance(main_ref, dict) else ""
    approved_sha = str(staging_ref.get("object", {}).get("sha", "")) if isinstance(staging_ref, dict) else ""
    deployed_sha = ""
    if isinstance(monitor_payload, dict):
        deployment = monitor_payload.get("deployment", {})
        if isinstance(deployment, dict):
            deployed_sha = str(deployment.get("deployed_sha") or "")

    worker_status = str(latest.get("status") or "unknown") if latest else "unknown"
    worker = {
        "status": worker_status,
        "run_id": int(latest["id"]) if latest and latest.get("id") else None,
        "run_number": int(latest["run_number"]) if latest and latest.get("run_number") else None,
        "phase": _phase(jobs),
        "retry_count": max(0, int(latest.get("run_attempt") or 1) - 1) if latest else 0,
        "started_at": latest.get("run_started_at") if latest else None,
    }

    task = None
    if running_issue:
        task = {
            "issue_number": int(running_issue["number"]),
            "title": str(running_issue.get("title") or "Autonomous task"),
            "state": "running",
        }

    pr = None
    if agent_pr:
        pr = {
            "number": int(agent_pr["number"]),
            "title": str(agent_pr.get("title") or "Autonomous PR"),
            "state": str(agent_pr.get("state") or "open"),
            "head_sha": str(agent_pr.get("head", {}).get("sha") or ""),
        }

    blocker = {
        "code": "AUTONOMOUS_BLOCKED" if blocked_issue else None,
        "message": str(blocked_issue.get("title")) if blocked_issue else None,
        "recoverable": False,
    }

    active = worker_status in {"queued", "in_progress"} or task is not None or pr is not None
    status = "blocked" if blocked_issue and not active else ("active" if active else "idle")

    pipeline = [
        {"key": "task", "label": "Task", "status": "active" if task else "idle"},
        {"key": "worker", "label": "AI worker", "status": worker_status},
        {"key": "pr", "label": "Pull request", "status": "active" if pr else "idle"},
        {"key": "ci", "label": "CI", "status": ci["status"]},
        {"key": "promotion", "label": "Staging promotion", "status": "success" if main_sha and approved_sha == main_sha else "pending"},
        {"key": "staging", "label": "Staging deploy", "status": "success" if approved_sha and deployed_sha == approved_sha else "pending"},
    ]

    recent = []
    for run in runs[:10]:
        if not isinstance(run, dict):
            continue
        recent.append({
            "run_number": run.get("run_number"),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
        })

    return {
        "version": 1,
        "status": status,
        "captured_at": captured_at.astimezone(timezone.utc).isoformat(),
        "current_worker": worker,
        "current_task": task,
        "runners": _runner_rows(runner_count, busy_runner_count),
        "pull_request": pr,
        "ci": ci,
        "staging": {
            "approved_sha": approved_sha or None,
            "deployed_sha": deployed_sha or None,
            "status": "online" if deployed_sha else "unknown",
        },
        "pipeline": pipeline,
        "blocker": blocker,
        "recent_worker_runs": recent,
    }


def publish_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent == DEFAULT_OUTPUT.parent:
        os.chmod(path.parent, 0o777)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(snapshot, handle, ensure_ascii=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, 0o644)
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def _process_counts() -> tuple[int, int]:
    completed = subprocess.run(
        ["ps", "-eo", "args="], text=True, capture_output=True, check=False, timeout=10,
    )
    lines = completed.stdout.splitlines() if completed.returncode == 0 else []
    listeners = sum("Runner.Listener" in line for line in lines)
    workers = sum("Runner.Worker" in line for line in lines)
    return listeners, min(workers, listeners)


def _monitor_payload() -> dict[str, Any]:
    try:
        response = httpx.get(STAGING_STATUS_URL, timeout=5, follow_redirects=True)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except (httpx.HTTPError, ValueError):
        return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    api = GitHubApi(os.getenv("GITHUB_TOKEN", ""))
    runner_count, busy_count = _process_counts()
    snapshot = build_snapshot(
        api,
        runner_count=runner_count,
        busy_runner_count=busy_count,
        monitor_payload=_monitor_payload(),
    )
    publish_snapshot(args.output, snapshot)
    print(
        "KMJ delivery evidence published: "
        f"status={snapshot['status']} runners={len(snapshot['runners'])} "
        f"worker={snapshot['current_worker'].get('status')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
