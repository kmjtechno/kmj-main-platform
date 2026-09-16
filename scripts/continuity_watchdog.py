from __future__ import annotations

from typing import Any

from controller.persistent_worker import (
    BLOCKED_LABEL,
    PENDING_LABEL,
    RUNNING_LABEL,
    SAFE_LABEL,
    GitHubClient,
)

RETRYABLE_MARKERS = (
    "Autonomous worker stopped safely: `PATCH_CHECK_FAILED/CORRUPT_DIFF`.",
    "Autonomous worker stopped safely: `PATCH_CHECK_FAILED/CONTEXT_MISMATCH`.",
)


def is_recoverable_block(body: str) -> bool:
    return any(marker in body for marker in RETRYABLE_MARKERS)


def latest_bot_comment(gh: Any, issue_number: int) -> str:
    comments = gh.request(
        "GET",
        f"/issues/{issue_number}/comments?per_page=100",
    )
    for comment in reversed(comments):
        if comment.get("user", {}).get("login") == "github-actions[bot]":
            return str(comment.get("body") or "")
    return ""


def dispatch_worker(gh: Any) -> None:
    gh.request(
        "POST",
        "/actions/workflows/autonomous-worker.yml/dispatches",
        json={"ref": "main"},
    )


def recover_and_restart(gh: Any) -> list[int]:
    issues = gh.request(
        "GET",
        f"/issues?state=open&labels={SAFE_LABEL},{BLOCKED_LABEL}&per_page=50",
    )
    recovered: list[int] = []

    for issue in issues:
        if "pull_request" in issue:
            continue
        number = int(issue["number"])
        if not is_recoverable_block(latest_bot_comment(gh, number)):
            continue
        gh.remove_label(number, BLOCKED_LABEL)
        gh.comment(
            number,
            "Continuity watchdog requeued this safe task after a known transient patch-format failure. Safety gates remain unchanged.",
        )
        recovered.append(number)

    if recovered:
        dispatch_worker(gh)

    return recovered


def ensure_safe_work_progress(gh: Any) -> bool:
    issues = gh.request(
        "GET",
        f"/issues?state=open&labels={SAFE_LABEL}&per_page=50",
    )
    inactive_labels = {RUNNING_LABEL, BLOCKED_LABEL, PENDING_LABEL}

    for issue in issues:
        if "pull_request" in issue:
            continue
        labels = {
            str(label.get("name") or "")
            for label in issue.get("labels", [])
            if isinstance(label, dict)
        }
        if labels & inactive_labels:
            continue
        dispatch_worker(gh)
        return True

    return False


def main() -> int:
    gh = GitHubClient()
    recovered = recover_and_restart(gh)
    dispatched_idle = False if recovered else ensure_safe_work_progress(gh)

    if recovered:
        print("KMJ continuity watchdog requeued: " + ",".join(map(str, recovered)))
    elif dispatched_idle:
        print("KMJ continuity watchdog: dispatched idle autonomous-safe work")
    else:
        print("KMJ continuity watchdog: no recoverable or idle safe tasks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
