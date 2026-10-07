import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from unittest.mock import patch
from controller.task_queue import TaskQueue
from controller.json_contract_workflow import JSONContractWorkflow


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        (self.repo / 'README.md').write_text('fixture')
        self.git('init', '-q')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture')
        self.tests = self.root / 'validation'
        self.tests.mkdir()
        (self.tests / 'test_schema.py').write_text('import unittest\nclass Check(unittest.TestCase):\n    def test_valid(self): self.assertTrue(True)\n')
        self.spec = {'workflow_id': 'wf', 'project': 'KMJ-test', 'repo': str(self.repo),
                     'base_sha': self.git('rev-parse', 'HEAD').strip(), 'target_path': 'contracts/task.json',
                     'trusted_tests': str(self.tests), 'prompt': 'Create JSON with a version field', 'max_iterations': 3}
        self.queue = TaskQueue(self.root / 'queue.db')
        self.state_dir = self.root / 'state'

    def tearDown(self): self.temp.cleanup()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True)

    def workflow(self):
        return JSONContractWorkflow(self.spec, self.state_dir, self.queue)

    def finish(self, content):
        task = self.queue.claim('test')
        self.assertIsNotNone(task)
        artifact = self.root / (task['id'].replace(':', '-') + '.json')
        artifact.write_text(json.dumps({'task_id': task['id'], 'kind': 'text', 'stage': 'artifact_ready', 'content': content, 'project': self.spec['project'], 'data_classification': self.spec.get('classification', 'confidential')}))
        self.queue.complete(task['id'], task['token'], {'stage': 'artifact_ready', 'artifact': str(artifact)})

    def test_restart_and_enqueue_are_idempotent_and_private(self):
        first = self.workflow().step()
        second = self.workflow().step()
        self.assertEqual(first['task_id'], second['task_id'])
        task = self.queue.get('wf:attempt1')
        self.assertEqual(task['payload']['data_classification'], 'confidential')
        self.assertEqual(task['attempts'], 0)
        state_files = list(self.state_dir.rglob('state.json'))
        self.assertEqual(len(state_files), 1)
        self.assertEqual(state_files[0].stat().st_mode & 0o777, 0o600)

    def test_invalid_json_feedback_preserves_classification(self):
        self.workflow().step()
        self.finish('not json')
        result = self.workflow().step()
        self.assertEqual(result['attempt'], 2)
        task = self.queue.get('wf:attempt2')
        self.assertEqual(task['payload']['data_classification'], 'confidential')
        self.assertIn('INVALID_JSON', task['payload']['prompt'])

    def test_three_invalid_candidates_stop_without_fourth_task(self):
        self.workflow().step()
        for _ in range(3):
            self.finish('not json')
            result = self.workflow().step()
        self.assertEqual(result['phase'], 'failed')
        self.assertIsNone(self.queue.get('wf:attempt4'))

    def sandbox_report(self, repo, base, diff, directory, success=True, **kwargs):
        candidate = directory / 'candidate-fixture'
        (candidate / 'contracts').mkdir(parents=True, exist_ok=True)
        raw = ''.join(line[1:] for line in diff.splitlines(keepends=True)
                      if line.startswith('+') and not line.startswith('+++')).encode()
        (candidate / 'contracts/task.json').write_bytes(raw)
        return {'stage': 'json_candidate_tested' if success else 'tests_failed',
                'candidate': str(candidate), 'base_sha': base,
                'diff_sha256': hashlib.sha256(diff.encode()).hexdigest(),
                'content_sha256': {'contracts/task.json': hashlib.sha256(raw).hexdigest()},
                'execution_scope': 'declarative_json_only', 'test_exit_code': 0 if success else 1,
                'tests_run': 1, 'termination_reason': None, 'base_still_current': True,
                'candidate_unchanged_during_validation': True,
                'output': '' if success else 'AssertionError: expected version 2'}

    def test_success_references_tested_content_and_never_repeats_execution(self):
        self.workflow().step()
        self.finish('```json\n{"version": 2}\n```')
        with patch('controller.json_contract_workflow.execute_candidate', side_effect=self.sandbox_report) as execute:
            result = self.workflow().step()
            self.assertEqual(result['phase'], 'json_candidate_tested')
            target = Path(result['report']['candidate']) / 'contracts/task.json'
            self.assertEqual(result['report']['content_sha256']['contracts/task.json'], hashlib.sha256(target.read_bytes()).hexdigest())
            self.assertFalse(result['product_complete'])
            self.workflow().step()
            self.assertEqual(execute.call_count, 1)
            diff = execute.call_args.args[2]
            self.assertIn('--- /dev/null', diff)
            self.assertIn('+++ b/contracts/task.json', diff)

    def test_test_failure_automatically_enqueues_bounded_repair(self):
        self.spec['classification'] = 'public'
        self.workflow().step()
        self.finish('{"version": 1}')
        def fail(*args, **kwargs): return self.sandbox_report(*args, **kwargs, success=False)
        with patch('controller.json_contract_workflow.execute_candidate', side_effect=fail):
            result = self.workflow().step()
        task = self.queue.get(result['task_id'])
        self.assertEqual(task['payload']['data_classification'], 'public')
        self.assertIn('expected version 2', task['payload']['prompt'])
        self.assertIn('"version": 1', task['payload']['prompt'])

    def test_changed_spec_or_validation_refused(self):
        self.workflow().step()
        self.spec['prompt'] = 'different'
        with self.assertRaises(ValueError): self.workflow().step()
        self.spec['prompt'] = 'Create JSON with a version field'
        (self.tests / 'test_schema.py').write_text('modified')
        with self.assertRaises(ValueError): self.workflow().step()

    def test_moved_base_refused(self):
        self.workflow().step()
        (self.repo / 'changed').write_text('changed')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'changed')
        with self.assertRaisesRegex(ValueError, 'BASE_MOVED'): self.workflow().step()

    def test_crash_between_state_save_and_enqueue_replays_same_task(self):
        with patch.object(self.queue, 'enqueue', side_effect=RuntimeError('simulated crash')):
            with self.assertRaises(RuntimeError): self.workflow().step()
        result = self.workflow().step()
        self.assertEqual(result['task_id'], 'wf:attempt1')
        self.assertIsNotNone(self.queue.get('wf:attempt1'))
        self.assertIsNone(self.queue.get('wf:attempt2'))

    def test_restart_reuses_bound_envelope_after_interrupted_state_save(self):
        self.workflow().step()
        self.finish('{"version": 2}')
        workflow = self.workflow()
        save = workflow._save
        def crash_on_success(state):
            if state.get('phase') == 'json_candidate_tested':
                raise RuntimeError('crash after bound envelope')
            return save(state)
        with patch('controller.json_contract_workflow.execute_candidate', side_effect=self.sandbox_report), patch.object(workflow, '_save', side_effect=crash_on_success):
            with self.assertRaises(RuntimeError): workflow.step()
        with patch('controller.json_contract_workflow.execute_candidate') as execute:
            result = self.workflow().step()
            self.assertEqual(result['phase'], 'json_candidate_tested')
            execute.assert_not_called()

    def test_forged_cache_with_changed_validation_or_content_is_not_reused(self):
        self.workflow().step()
        self.finish('{"version": 2}')
        workflow = self.workflow()
        with patch('controller.json_contract_workflow.execute_candidate', side_effect=RuntimeError('crash before sandbox')):
            with self.assertRaises(RuntimeError): workflow.step()
        state = json.loads(workflow.state_path.read_text())
        directory = workflow.directory / 'candidates-attempt1'
        report = self.sandbox_report(self.repo, self.spec['base_sha'], state['diff'], directory)
        envelope = {'validation_sha256': 'wrong', 'spec_sha256': workflow.fingerprint, 'report': report}
        (directory / 'validated-report.json').write_text(json.dumps(envelope))
        self.assertIsNone(workflow._existing_report(directory, state['diff'], state['candidate_json']))
        envelope['validation_sha256'] = workflow.test_digest
        report['content_sha256']['contracts/task.json'] = 'forged'
        (directory / 'validated-report.json').write_text(json.dumps(envelope))
        self.assertIsNone(workflow._existing_report(directory, state['diff'], state['candidate_json']))
        report['content_sha256']['contracts/task.json'] = hashlib.sha256(state['candidate_json'].encode()).hexdigest()
        report['tests_run'] = 0
        (directory / 'validated-report.json').write_text(json.dumps(envelope))
        self.assertIsNone(workflow._existing_report(directory, state['diff'], state['candidate_json']))
        with patch('controller.json_contract_workflow.execute_candidate', side_effect=self.sandbox_report) as execute:
            self.assertEqual(workflow.step()['phase'], 'json_candidate_tested')
            self.assertEqual(execute.call_count, 1)

    def test_artifact_project_and_classification_must_match(self):
        self.workflow().step()
        self.finish('{"version": 2}')
        path = self.root / 'wf-attempt1.json'
        artifact = json.loads(path.read_text())
        for field, value in (('project', 'other'), ('data_classification', 'public')):
            wrong = dict(artifact, **{field: value})
            path.write_text(json.dumps(wrong))
            with self.assertRaisesRegex(ValueError, 'ARTIFACT_IDENTITY_MISMATCH'):
                self.workflow().step()

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap required')
    def test_unicode_separators_round_trip_through_real_git_apply(self):
        value = {'text': 'a' + chr(0x2028) + chr(0x2029) + chr(0x85) + 'b'}
        self.workflow().step()
        self.finish(json.dumps(value, ensure_ascii=False))
        result = self.workflow().step()
        self.assertEqual(result['phase'], 'json_candidate_tested')
        actual = json.loads((Path(result['report']['candidate']) / 'contracts/task.json').read_text())
        self.assertEqual(actual, value)

    def test_strict_json_rejects_duplicates_and_nonfinite_before_sandbox(self):
        self.workflow().step()
        for content in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}'):
            self.finish(content)
            with patch('controller.json_contract_workflow.execute_candidate') as execute:
                self.workflow().step()
                execute.assert_not_called()

    def test_python_target_refused(self):
        self.spec['target_path'] = 'contracts/evil.py'
        with self.assertRaises(ValueError): self.workflow()


if __name__ == '__main__': unittest.main()
