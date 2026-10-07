"""Vetted non-JSON code candidate executor with external declarative assertions.

The first supported executor is Python CLI v1. Candidate code runs only inside
Bubblewrap. Trusted assertions are evaluated by this parent process, never by
candidate-imported unittest/pytest code, so printing a success marker cannot
forge acceptance.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import time
import uuid

from controller.patch_sandbox import ENV, _git, _run_bounded
from controller.persistent_worker import validate_patch

MAX_CASES = 32
MAX_ARG_BYTES = 8192
MAX_STDIN_BYTES = 65536
MAX_EXPECTED_BYTES = 65536
ALLOWED_SUFFIXES = {".py"}


def _safe_relpath(value: str, code: str) -> str:
    if not isinstance(value, str) or not value or value.startswith("/"):
        raise ValueError(code)
    path = Path(value)
    if ".." in path.parts or any(part in {"", ".", ".git"} for part in path.parts):
        raise ValueError(code)
    if any(part.startswith(".") for part in path.parts):
        raise ValueError(code)
    return value


def _validation_cases(
    trusted_tests: Path,
    *,
    allowed_paths: set[str],
    expected_sha256: str | None,
) -> tuple[dict, str]:
    if not trusted_tests.is_dir() or any(p.is_symlink() for p in trusted_tests.rglob("*")):
        raise ValueError("UNSAFE_VALIDATION_TREE")
    entries = list(trusted_tests.iterdir())
    if {p.name for p in entries} != {"cases.json"} or not entries[0].is_file():
        raise ValueError("VALIDATION_TREE_MUST_ONLY_CONTAIN_CASES_JSON")
    raw = (trusted_tests / "cases.json").read_bytes()
    if len(raw) > 262144:
        raise ValueError("VALIDATION_TOO_LARGE")
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("VALIDATION_DIGEST_MISMATCH")
    try:
        spec = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("VALIDATION_JSON_INVALID") from exc
    if not isinstance(spec, dict) or set(spec) != {"schema_version", "executor", "entrypoint", "cases"}:
        raise ValueError("VALIDATION_SCHEMA_INVALID")
    if spec["schema_version"] != 1 or spec["executor"] != "python-cli-v1":
        raise ValueError("VALIDATION_EXECUTOR_UNSUPPORTED")
    entrypoint = _safe_relpath(spec["entrypoint"], "ENTRYPOINT_INVALID")
    if entrypoint not in allowed_paths or Path(entrypoint).suffix not in ALLOWED_SUFFIXES:
        raise ValueError("ENTRYPOINT_NOT_ALLOWED")
    cases = spec["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise ValueError("VALIDATION_CASE_COUNT_INVALID")
    normalized = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or set(case) != {"args", "stdin", "exit_code", "stdout"}:
            raise ValueError("VALIDATION_CASE_INVALID")
        args = case["args"]
        if (not isinstance(args, list) or len(args) > 32
                or any(not isinstance(arg, str) or "\x00" in arg for arg in args)
                or sum(len(arg.encode("utf-8")) for arg in args) > MAX_ARG_BYTES):
            raise ValueError("VALIDATION_ARGS_INVALID")
        stdin = case["stdin"]
        stdout = case["stdout"]
        exit_code = case["exit_code"]
        if not isinstance(stdin, str) or stdin != "":
            raise ValueError("VALIDATION_STDIN_UNSUPPORTED")
        if (not isinstance(stdout, str)
                or len(stdout.encode("utf-8")) > MAX_EXPECTED_BYTES):
            raise ValueError("VALIDATION_STDOUT_INVALID")
        if type(exit_code) is not int or not 0 <= exit_code <= 255:
            raise ValueError("VALIDATION_EXIT_INVALID")
        normalized.append({
            "index": index,
            "args": args,
            "stdin": stdin,
            "exit_code": exit_code,
            "stdout": stdout,
        })
    return {"entrypoint": entrypoint, "cases": normalized}, digest


def execute_code_candidate(
    repo: Path | str,
    base_sha: str,
    diff: str,
    candidates_dir: Path | str,
    *,
    trusted_tests: Path | str,
    allowed_paths: list[str],
    expected_validation_sha256: str | None = None,
    timeout_per_case: float = 15,
    output_limit: int = 65536,
) -> dict:
    """Apply an exact-scope patch and evaluate external Python CLI assertions."""
    if not isinstance(base_sha, str) or not re.fullmatch("[0-9a-f]{40}", base_sha):
        raise ValueError("EXACT_BASE_SHA_REQUIRED")
    if not isinstance(timeout_per_case, (int, float)) or not math.isfinite(timeout_per_case):
        raise ValueError("INVALID_TIMEOUT")
    if not 0 < timeout_per_case <= 30:
        raise ValueError("INVALID_TIMEOUT")
    if type(output_limit) is not int or not 1024 <= output_limit <= 262144:
        raise ValueError("INVALID_OUTPUT_LIMIT")
    if not isinstance(diff, str) or "\x00" in diff:
        raise ValueError("PATCH_INVALID")
    if (not isinstance(allowed_paths, list) or not 1 <= len(allowed_paths) <= 4
            or len(set(allowed_paths)) != len(allowed_paths)):
        raise ValueError("ALLOWED_PATHS_INVALID")
    allowed = {_safe_relpath(path, "ALLOWED_PATH_INVALID") for path in allowed_paths}
    if any(Path(path).suffix not in ALLOWED_SUFFIXES for path in allowed):
        raise ValueError("ALLOWED_SUFFIX_DENIED")
    paths = set(validate_patch(diff))
    if paths != allowed:
        raise ValueError("PATCH_SCOPE_MISMATCH")

    repo = Path(repo).resolve(strict=True)
    root = Path(candidates_dir).resolve()
    tests = Path(trusted_tests).resolve(strict=True)
    if (root.is_relative_to(repo) or repo.is_relative_to(root)
            or tests.is_relative_to(repo) or tests.is_relative_to(root)
            or root.is_relative_to(tests)):
        raise ValueError("CANDIDATE_AND_VALIDATION_MUST_BE_EXTERNAL")
    validation, validation_digest = _validation_cases(
        tests,
        allowed_paths=allowed,
        expected_sha256=expected_validation_sha256,
    )
    bwrap = shutil.which("bwrap", path="/usr/bin:/bin")
    if not bwrap:
        raise ValueError("SANDBOX_UNAVAILABLE")

    common = Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    lock_fd = os.open(
        common / "kmj-code-sandbox.lock",
        os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
        0o600,
    )
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("PROJECT_BUSY") from exc
        if _git(repo, "rev-parse", "HEAD") != base_sha:
            raise ValueError("BASE_MOVED")
        candidate = root / ("candidate-" + uuid.uuid4().hex)
        _git(repo, "worktree", "add", "--detach", str(candidate), base_sha)
        for path in allowed:
            current = candidate
            for part in Path(path).parts:
                current = current / part
                if current.is_symlink():
                    raise ValueError("SYMLINK_PATCH_PATH")
        _git(candidate, "apply", "--check", "-", data=diff)
        _git(candidate, "apply", "-", data=diff)

        content_digests = {}
        for path in sorted(allowed):
            target = candidate / path
            if not target.is_file() or target.is_symlink():
                raise ValueError("CODE_FILE_MUST_EXIST")
            raw = target.read_bytes()
            if len(raw) > 262144 or b"\x00" in raw:
                raise ValueError("CODE_FILE_TOO_LARGE_OR_BINARY")
            content_digests[path] = hashlib.sha256(raw).hexdigest()

        entrypoint = validation["entrypoint"]
        results = []
        all_passed = True
        for case in validation["cases"]:
            command = [
                bwrap,
                "--unshare-all", "--die-with-parent", "--new-session",
                "--cap-drop", "ALL",
                "--clearenv", "--setenv", "PATH", "/usr/bin:/bin",
                "--setenv", "HOME", "/tmp", "--setenv", "LANG", "C.UTF-8",
                "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib",
                "--ro-bind", "/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev",
                "--tmpfs", "/tmp", "--ro-bind", str(candidate), "/workspace",
                "--ro-bind", "/dev/null", "/workspace/.git", "--chdir", "/workspace",
                "--", "/usr/bin/python3", "-I", "-B", f"/workspace/{entrypoint}",
                *case["args"],
            ]
            code, output, termination = _run_bounded(
                command,
                timeout_per_case,
                output_limit,
            )
            passed = (
                termination is None
                and code == case["exit_code"]
                and output == case["stdout"]
            )
            all_passed = all_passed and passed
            results.append({
                "index": case["index"],
                "passed": passed,
                "exit_code": code,
                "termination_reason": termination,
                "stdout_sha256": hashlib.sha256(output.encode()).hexdigest(),
            })

        base_still_current = _git(repo, "rev-parse", "HEAD") == base_sha
        final_digests = {
            path: hashlib.sha256((candidate / path).read_bytes()).hexdigest()
            for path in sorted(allowed)
        }
        candidate_unchanged = final_digests == content_digests
        passed = all_passed and base_still_current and candidate_unchanged
        report = {
            "stage": "code_candidate_tested" if passed else "tests_failed",
            "execution_scope": "python_cli_v1",
            "base_sha": base_sha,
            "base_still_current": base_still_current,
            "paths": sorted(allowed),
            "entrypoint": entrypoint,
            "diff_sha256": hashlib.sha256(diff.encode()).hexdigest(),
            "validation_sha256": validation_digest,
            "content_sha256": final_digests,
            "candidate_unchanged_during_validation": candidate_unchanged,
            "tests_run": len(results),
            "tests_passed": sum(1 for result in results if result["passed"]),
            "case_results": results,
            "candidate": str(candidate),
            "product_complete": False,
            "deployed": False,
            "created_utc_epoch": time.time(),
        }
        report_path = root / (candidate.name + "-report.json")
        with os.fdopen(
            os.open(report_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
            "w",
        ) as stream:
            json.dump(report, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return report
    finally:
        os.close(lock_fd)
