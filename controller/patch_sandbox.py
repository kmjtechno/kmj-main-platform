"""Apply declarative contracts/*.json patches and run external trusted data checks.

No commit, push, production promotion, original checkout reset or shell commands.
The operator supplies an immutable base and external read-only validation suite.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import selectors
import shutil
import signal
import subprocess
import time
import uuid

from controller.persistent_worker import validate_patch

ENV = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LANG': 'C.UTF-8',
       'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
       'GIT_TERMINAL_PROMPT': '0'}
CHECK_SCRIPT = '''import sys, unittest
suite = unittest.defaultTestLoader.discover('/validation')
count = suite.countTestCases()
if count == 0:
    print('KMJ_VALIDATION_ZERO_TESTS', flush=True)
    raise SystemExit(2)
result = unittest.TextTestRunner(verbosity=2).run(suite)
print('KMJ_VALIDATION_FINISHED:' + str(result.testsRun), flush=True)
raise SystemExit(0 if result.wasSuccessful() and result.testsRun > 0 else 1)
'''


def _reject_constant(value: str):
    raise ValueError('NONFINITE_JSON_NUMBER')


def _unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def _git(repo: Path, *args: str, data: str | None = None) -> str:
    result = subprocess.run(['/usr/bin/git', '-c', 'core.hooksPath=/dev/null',
        '-c', 'core.fsmonitor=false', '-C', str(repo), *args], input=data,
        text=True, capture_output=True, timeout=30, env=ENV)
    if result.returncode:
        raise ValueError('GIT_OPERATION_FAILED:' + args[0])
    return result.stdout.strip()


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    resource.setrlimit(resource.RLIMIT_NPROC, (128, 128))


def _run_bounded(command: list[str], timeout: float, output_limit: int) -> tuple[int, str, str | None]:
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               env=ENV, start_new_session=True, preexec_fn=_limits)
    output = bytearray()
    reason = None
    deadline = time.monotonic() + timeout
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        while selector.get_map():
            if time.monotonic() >= deadline:
                reason = 'timeout'
                break
            for key, _ in selector.select(min(.1, max(0, deadline - time.monotonic()))):
                chunk = os.read(key.fd, 4096)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                remaining = output_limit - len(output)
                output.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    reason = 'output_limit'
                    break
            if reason:
                break
        if reason:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=2)
    finally:
        selector.close()
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)
        process.stdout.close()
    return process.returncode, output.decode('utf-8', errors='replace'), reason


def execute_candidate(repo: Path | str, base_sha: str, diff: str,
                      candidates_dir: Path | str, *, trusted_tests: Path | str,
                      check: str = 'json-contract-unittest', timeout: float = 60,
                      output_limit: int = 65536) -> dict:
    """Return json_candidate_tested/tests_failed; retain candidates on failure.

    Requires bubblewrap user namespaces; fails closed if sandbox cannot start.
    Both writable candidate root and operator test tree must be outside repo.
    The fixed command is Python unittest discovery, never model-supplied shell.
    """
    if check != 'json-contract-unittest':
        raise ValueError('CHECK_NOT_ALLOWLISTED')
    if not isinstance(base_sha, str) or not re.fullmatch('[0-9a-f]{40}', base_sha):
        raise ValueError('EXACT_BASE_SHA_REQUIRED')
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise ValueError('INVALID_TIMEOUT')
    if not isinstance(output_limit, int) or not 1024 <= output_limit <= 1024 * 1024:
        raise ValueError('INVALID_OUTPUT_LIMIT')
    if not isinstance(diff, str) or '\x00' in diff or any(line.startswith('Binary files ') for line in diff.splitlines()):
        raise ValueError('BINARY_PATCH_FORBIDDEN')
    paths = validate_patch(diff)
    if any(len(Path(path).parts) != 2 or Path(path).parts[0] != 'contracts'
           or Path(path).suffix != '.json' for path in paths):
        raise ValueError('ONLY_DECLARATIVE_JSON_CONTRACTS_SUPPORTED')
    repo = Path(repo).resolve(strict=True)
    root = Path(candidates_dir).resolve()
    tests = Path(trusted_tests).resolve(strict=True)
    if root.is_relative_to(repo) or repo.is_relative_to(root) or tests.is_relative_to(repo) or tests.is_relative_to(root) or root.is_relative_to(tests):
        raise ValueError('CANDIDATE_AND_VALIDATION_MUST_BE_EXTERNAL')
    if not tests.is_dir() or any(p.is_symlink() for p in tests.rglob('*')):
        raise ValueError('UNSAFE_VALIDATION_TREE')
    bwrap = shutil.which('bwrap', path='/usr/bin:/bin')
    if not bwrap:
        raise ValueError('SANDBOX_UNAVAILABLE')
    common = Path(_git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    lock_fd = os.open(common / 'kmj-patch-sandbox.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('PROJECT_BUSY') from exc
        if _git(repo, 'rev-parse', 'HEAD') != base_sha:
            raise ValueError('BASE_MOVED')
        candidate = root / ('candidate-' + uuid.uuid4().hex)
        _git(repo, 'worktree', 'add', '--detach', str(candidate), base_sha)
        for path in paths:
            current = candidate
            for part in Path(path).parts:
                current = current / part
                if current.is_symlink():
                    raise ValueError('SYMLINK_PATCH_PATH')
            if current.exists() and not current.is_file():
                raise ValueError('NONREGULAR_PATCH_PATH')
        _git(candidate, 'apply', '--check', '-', data=diff)
        _git(candidate, 'apply', '-', data=diff)
        content_digests = {}
        for path in paths:
            target = candidate / path
            if not target.is_file() or target.is_symlink():
                raise ValueError('JSON_CONTRACT_MUST_EXIST')
            raw = target.read_bytes()
            if len(raw) > 262144:
                raise ValueError('JSON_CONTRACT_TOO_LARGE')
            try:
                json.loads(raw, parse_constant=_reject_constant, object_pairs_hook=_unique_object)
            except (ValueError, UnicodeError) as exc:
                raise ValueError('INVALID_JSON_CONTRACT') from exc
            content_digests[path] = hashlib.sha256(raw).hexdigest()
        command = [bwrap, '--unshare-all', '--die-with-parent', '--new-session',
                   '--cap-drop', 'ALL',
                   '--clearenv', '--setenv', 'PATH', '/usr/bin:/bin',
                   '--setenv', 'HOME', '/tmp', '--setenv', 'LANG', 'C.UTF-8',
                   '--ro-bind', '/usr', '/usr', '--ro-bind', '/lib', '/lib',
                   '--ro-bind', '/lib64', '/lib64', '--proc', '/proc', '--dev', '/dev',
                   '--tmpfs', '/tmp', '--ro-bind', str(candidate), '/workspace',
                   '--ro-bind', '/dev/null', '/workspace/.git',
                   '--ro-bind', str(tests), '/validation', '--chdir', '/workspace',
                   '--', '/usr/bin/python3', '-I', '-B', '-c', CHECK_SCRIPT]
        code, output, termination = _run_bounded(command, timeout, output_limit)
        base_still_current = _git(repo, 'rev-parse', 'HEAD') == base_sha
        final_digests = {path: hashlib.sha256((candidate / path).read_bytes()).hexdigest() for path in paths}
        candidate_unchanged = final_digests == content_digests
        finished = re.search(r'^KMJ_VALIDATION_FINISHED:([1-9][0-9]*)$', output, re.M)
        passed = code == 0 and finished is not None and termination is None and base_still_current and candidate_unchanged
        report = {'stage': 'json_candidate_tested' if passed else 'tests_failed',
                  'execution_scope': 'declarative_json_only',
                  'content_sha256': final_digests,
                  'candidate_unchanged_during_validation': candidate_unchanged,
                  'product_complete': False, 'deployed': False, 'candidate': str(candidate),
                  'base_sha': base_sha, 'base_still_current': base_still_current,
                  'diff_sha256': hashlib.sha256(diff.encode()).hexdigest(),
                  'paths': paths, 'check': check, 'test_exit_code': code,
                  'tests_run': int(finished.group(1)) if finished else 0,
                  'termination_reason': termination, 'output': output,
                  'created_utc_epoch': time.time()}
        report_path = root / (candidate.name + '-report.json')
        with os.fdopen(os.open(report_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
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
