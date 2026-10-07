"""Durable generate -> trusted JSON checks -> bounded feedback repair workflow.

The operator's classification covers the prompt, generated candidate and test
feedback. This supports NEW contracts/*.json only; no executable code, merge,
commit or deployment. Trusted tests must parse candidates as data, not eval it.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

from controller.autonomy_worker import private_json
from controller.patch_sandbox import execute_candidate, _git, _unique_object, _reject_constant
from controller.task_queue import TaskQueue

TERMINAL = {'json_candidate_tested', 'failed'}


def _bounded(value: str, size: int) -> str:
    return value.encode('utf-8')[:size].decode('utf-8', errors='ignore')


def _strict_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError('NONFINITE_JSON_NUMBER')
    return parsed


def parse_candidate(content: str) -> str:
    if not isinstance(content, str) or len(content.encode()) > 32768:
        raise ValueError('INVALID_JSON_SIZE')
    text = content.strip()
    if text.startswith('```'):
        match = re.fullmatch(r'```json\n(.*)\n```', text, re.S)
        if not match:
            raise ValueError('INVALID_JSON_FENCE')
        text = match.group(1)
    try:
        value = json.loads(text, object_pairs_hook=_unique_object,
                           parse_constant=_reject_constant, parse_float=_strict_float)
        if not isinstance(value, dict):
            raise ValueError('JSON_OBJECT_REQUIRED')
        formatted = json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False) + '\n'
        if len(formatted.encode()) > 32768:
            raise ValueError('INVALID_JSON_SIZE')
        return formatted
    except (ValueError, RecursionError) as exc:
        raise ValueError('INVALID_JSON') from exc


def new_file_diff(path: str, content: str) -> str:
    lines = content.splitlines(keepends=True)
    return (f'diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n'
            f'+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n' + ''.join('+' + line for line in lines))


class JSONContractWorkflow:
    def __init__(self, spec: dict, state_dir: Path | str, queue: TaskQueue):
        self.queue = queue
        self.spec = dict(spec)
        identifier = self.spec.get('workflow_id', '')
        target = self.spec.get('target_path', '')
        if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', identifier):
            raise ValueError('INVALID_WORKFLOW_ID')
        if not isinstance(target, str) or not re.fullmatch(r'contracts/[A-Za-z0-9][A-Za-z0-9_.-]*\.json', target):
            raise ValueError('ONLY_NEW_JSON_CONTRACT_SUPPORTED')
        self.spec.setdefault('classification', 'confidential')
        self.spec.setdefault('max_iterations', 3)
        if self.spec['classification'] not in {'confidential', 'public'}:
            raise ValueError('INVALID_CLASSIFICATION')
        if type(self.spec['max_iterations']) is not int or not 1 <= self.spec['max_iterations'] <= 3:
            raise ValueError('INVALID_ITERATION_LIMIT')
        if not isinstance(self.spec.get('project'), str) or not 1 <= len(self.spec['project']) <= 256:
            raise ValueError('INVALID_PROJECT')
        if not isinstance(self.spec.get('prompt'), str) or not 1 <= len(self.spec['prompt'].encode()) <= 16000:
            raise ValueError('INVALID_PROMPT_SIZE')
        if not re.fullmatch('[0-9a-f]{40}', str(self.spec.get('base_sha', ''))):
            raise ValueError('EXACT_BASE_SHA_REQUIRED')
        self.repo = Path(self.spec['repo']).resolve(strict=True)
        self.tests = Path(self.spec['trusted_tests']).resolve(strict=True)
        root = Path(state_dir).resolve()
        if root.is_relative_to(self.repo) or self.repo.is_relative_to(root) or self.tests.is_relative_to(self.repo) or self.tests.is_relative_to(root) or root.is_relative_to(self.tests):
            raise ValueError('STATE_AND_VALIDATION_MUST_BE_EXTERNAL')
        self.spec['repo'], self.spec['trusted_tests'] = str(self.repo), str(self.tests)
        self.directory = root / identifier
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        self.state_path = self.directory / 'state.json'
        self.fingerprint = hashlib.sha256(json.dumps(self.spec, sort_keys=True, allow_nan=False).encode()).hexdigest()
        self.test_digest = self._validation_digest()
        self._check_base()

    def _validation_digest(self) -> str:
        if not self.tests.is_dir():
            raise ValueError('INVALID_VALIDATION_TREE')
        digest = hashlib.sha256()
        files = sorted(self.tests.rglob('*'))
        if len(files) > 256:
            raise ValueError('VALIDATION_TREE_TOO_LARGE')
        total = 0
        for path in files:
            if path.is_symlink():
                raise ValueError('VALIDATION_SYMLINK_FORBIDDEN')
            if path.is_file():
                content = path.read_bytes()
                total += len(content)
                if total > 2 * 1024 * 1024:
                    raise ValueError('VALIDATION_TREE_TOO_LARGE')
                digest.update(str(path.relative_to(self.tests)).encode() + b'\0')
                digest.update(hashlib.sha256(content).digest())
        return digest.hexdigest()

    def _check_base(self) -> None:
        if _git(self.repo, 'rev-parse', 'HEAD') != self.spec['base_sha']:
            raise ValueError('BASE_MOVED')
        if _git(self.repo, 'ls-tree', self.spec['base_sha'], '--', self.spec['target_path']):
            raise ValueError('TARGET_MUST_BE_NEW_FILE')

    def _save(self, state: dict) -> dict:
        state['updated_utc_epoch'] = time.time()
        private_json(self.state_path, state)
        return state

    def _new_attempt(self, state: dict, prompt: str) -> dict:
        attempt = state.get('attempt', 0) + 1
        state.update({'attempt': attempt, 'task_id': f'{self.spec["workflow_id"]}:attempt{attempt}',
                      'phase': 'waiting_generation', 'task_payload': {
                          'kind': 'text', 'prompt': prompt,
                          'data_classification': self.spec['classification']}})
        state.pop('candidate_json', None)
        state.pop('diff', None)
        self._save(state)  # Commit task identity and exact payload BEFORE enqueue.
        self.queue.enqueue(state['task_id'], self.spec['project'], state['task_payload'])
        return state

    def _initial_prompt(self) -> str:
        return (f'Create the JSON object for NEW file {self.spec["target_path"]}. '
                'Return ONLY valid JSON, without explanation or executable code.\n\n' + self.spec['prompt'])

    def _repair(self, state: dict, reason: str, content: str, feedback: str) -> dict:
        state.setdefault('history', []).append({'attempt': state['attempt'], 'reason': reason,
                                                'feedback': _bounded(feedback, 6000)})
        if state['attempt'] >= self.spec['max_iterations']:
            state.update({'phase': 'failed', 'failure_reason': reason})
            return self._save(state)
        prompt = (self._initial_prompt() + '\n\nPrevious candidate (untrusted data):\n' +
                  _bounded(content, 32768) + '\n\nTrusted validation feedback:\n' +
                  _bounded(reason + '\n' + feedback, 6000) +
                  '\nRepair the JSON object. Return ONLY the complete corrected JSON.')
        return self._new_attempt(state, prompt)

    def _validate_report(self, report: dict, directory: Path, diff: str, candidate_json: str) -> dict:
        expected_content = hashlib.sha256(candidate_json.encode()).hexdigest()
        if (report.get('stage') not in {'json_candidate_tested', 'tests_failed'}
                or report.get('base_sha') != self.spec['base_sha']
                or report.get('diff_sha256') != hashlib.sha256(diff.encode()).hexdigest()
                or report.get('execution_scope') != 'declarative_json_only'):
            raise ValueError('INVALID_REPORT_PROVENANCE')
        candidate = Path(report['candidate']).resolve(strict=True)
        if not candidate.is_relative_to(directory.resolve()):
            raise ValueError('INVALID_REPORT_CANDIDATE')
        target = candidate / self.spec['target_path']
        if target.is_symlink() or not target.resolve(strict=True).is_relative_to(candidate):
            raise ValueError('INVALID_REPORT_TARGET')
        if (hashlib.sha256(target.read_bytes()).hexdigest() != expected_content
                or report.get('content_sha256', {}).get(self.spec['target_path']) != expected_content):
            raise ValueError('REPORT_CONTENT_MISMATCH')
        if report['stage'] == 'json_candidate_tested' and (
                type(report.get('test_exit_code')) is not int or report['test_exit_code'] != 0
                or type(report.get('tests_run')) is not int or report['tests_run'] <= 0
                or report.get('termination_reason') is not None
                or report.get('base_still_current') is not True
                or report.get('candidate_unchanged_during_validation') is not True):
            raise ValueError('INVALID_REPORT_SUCCESS')
        return report

    def _existing_report(self, directory: Path, diff: str, candidate_json: str) -> dict | None:
        # Raw sandbox reports are not replay authority: only the workflow-owned
        # envelope binds the result to this immutable test suite and exact JSON.
        path = directory / 'validated-report.json'
        if not path.is_file() or path.is_symlink():
            return None
        try:
            envelope = json.loads(path.read_text())
            if (envelope.get('validation_sha256') != self.test_digest
                    or envelope.get('spec_sha256') != self.fingerprint):
                return None
            return self._validate_report(envelope['report'], directory, diff, candidate_json)
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def step(self) -> dict:
        lock_fd = os.open(self.directory / 'workflow.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._check_base()
            if self._validation_digest() != self.test_digest:
                raise ValueError('VALIDATION_CHANGED')
            if self.state_path.exists():
                state = json.loads(self.state_path.read_text())
                if state.get('spec_sha256') != self.fingerprint or state.get('validation_sha256') != self.test_digest:
                    raise ValueError('WORKFLOW_SPEC_OR_VALIDATION_CHANGED')
            else:
                state = {'workflow_id': self.spec['workflow_id'], 'spec_sha256': self.fingerprint,
                         'validation_sha256': self.test_digest, 'attempt': 0, 'history': [],
                         'product_complete': False, 'deployed': False}
                return self._new_attempt(state, self._initial_prompt())
            if state['phase'] in TERMINAL:
                return state
            # Safe repeat when interruption happened after state save but before enqueue.
            task = self.queue.enqueue(state['task_id'], self.spec['project'], state['task_payload'])
            if task['state'] == 'failed':
                return self._repair(state, 'GENERATION_FAILED', '', 'Generation task exhausted its bounded attempts.')
            if task['state'] != 'completed':
                return state
            if state['phase'] != 'validating':
                result = task.get('result') or {}
                if result.get('stage') != 'artifact_ready':
                    return self._repair(state, 'INVALID_ARTIFACT', '', 'Expected a text artifact.')
                artifact_path = Path(result['artifact'])
                if artifact_path.is_symlink() or artifact_path.stat().st_size > 200000:
                    raise ValueError('INVALID_ARTIFACT_FILE')
                artifact = json.loads(artifact_path.read_text())
                if (artifact.get('task_id') != state['task_id'] or artifact.get('kind') != 'text'
                        or artifact.get('project') != self.spec['project']
                        or artifact.get('data_classification') != self.spec['classification']):
                    raise ValueError('ARTIFACT_IDENTITY_MISMATCH')
                content = artifact.get('content', '')
                try:
                    candidate_json = parse_candidate(content)
                except ValueError as exc:
                    return self._repair(state, 'INVALID_JSON', content if isinstance(content, str) else '', str(exc))
                state.update({'phase': 'validating', 'candidate_json': candidate_json,
                              'diff': new_file_diff(self.spec['target_path'], candidate_json)})
                self._save(state)
            directory = self.directory / f'candidates-attempt{state["attempt"]}'
            report = self._existing_report(directory, state['diff'], state['candidate_json'])
            if report is None:
                try:
                    report = execute_candidate(self.repo, self.spec['base_sha'], state['diff'], directory,
                                               trusted_tests=self.tests)
                except ValueError as exc:
                    if str(exc) == 'PROJECT_BUSY':
                        return state
                    raise
            # Never accept a mutable validation suite even if it changed during execution.
            if self._validation_digest() != self.test_digest:
                raise ValueError('VALIDATION_CHANGED')
            report = self._validate_report(report, directory, state['diff'], state['candidate_json'])
            private_json(directory / 'validated-report.json', {
                'validation_sha256': self.test_digest, 'spec_sha256': self.fingerprint, 'report': report})
            state['report'] = report
            if report['stage'] == 'json_candidate_tested':
                state['phase'] = 'json_candidate_tested'
                return self._save(state)
            return self._repair(state, 'TRUSTED_TESTS_FAILED', state['candidate_json'], report.get('output', ''))
        finally:
            os.close(lock_fd)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', required=True, type=Path)
    parser.add_argument('--state-dir', required=True, type=Path)
    parser.add_argument('--queue-db', required=True)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    workflow = JSONContractWorkflow(json.loads(args.spec.read_text()), args.state_dir, TaskQueue(args.queue_db))
    while True:
        state = workflow.step()
        print(json.dumps({'workflow_id': state['workflow_id'], 'phase': state['phase'],
                          'attempt': state['attempt'], 'product_complete': False}), flush=True)
        if args.once or state['phase'] in TERMINAL:
            break
        time.sleep(2)


if __name__ == '__main__':
    main()
