import asyncio
import json
import os
import stat
from unittest.mock import patch
import tempfile
import unittest
from pathlib import Path
from controller.task_queue import TaskQueue
from controller.model_router import NoFreeRouteAvailable
from controller.autonomy_worker import AutonomyWorker, private_json


class Router:
    def __init__(self, fail=False, delay=.08):
        self.delay = delay
        self.active = 0
        self.maximum = 0
        self.calls = []
        self.fail = fail

    async def complete(self, messages, **kwargs):
        self.calls.append(kwargs)
        self.active += 1
        self.maximum = max(self.maximum, self.active)
        try:
            await asyncio.sleep(self.delay)
            if self.fail:
                raise RuntimeError('secret must not enter queue errors')
            return {'provider': 'test', 'model': 'test', 'response': {'choices': [{'message': {'content': 'Bounded task result'}}]}}
        finally:
            self.active -= 1


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.queue = TaskQueue(self.root / 'queue.sqlite', max_concurrency=2)

    async def asyncTearDown(self):
        self.temp.cleanup()

    def enqueue(self, task, project, **kwargs):
        self.queue.enqueue(task, project, {'kind': 'plan', 'prompt': 'Create a test plan', **kwargs})

    async def test_atomic_artifact_fsyncs_file_then_rename_then_directory(self):
        events = []
        real_fsync, real_replace = os.fsync, os.replace
        def fsync(fd):
            events.append('directory_sync' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'file_sync')
            real_fsync(fd)
        def replace(source, destination):
            events.append('rename')
            real_replace(source, destination)
        with patch('controller.autonomy_worker.os.fsync', side_effect=fsync), patch('controller.autonomy_worker.os.replace', side_effect=replace):
            private_json(self.root / 'artifact.json', {'ready': True})
        self.assertEqual(events, ['file_sync', 'rename', 'directory_sync'])

    async def test_two_projects_run_parallel_and_output_is_not_product_complete(self):
        self.enqueue('a', 'a')
        self.enqueue('b', 'b')
        router = Router()
        worker = AutonomyWorker(self.queue, self.root / 'artifacts', router=router)
        await worker.run(once=True)
        self.assertEqual(router.maximum, 2)
        files = list((self.root / 'artifacts').glob('[0-9a-f]' * 64 + '.json'))
        self.assertEqual(len(files), 2)
        for file in files:
            result = json.loads(file.read_text())
            self.assertEqual(result['stage'], 'artifact_ready')
            self.assertFalse(result['product_complete'])
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
        self.assertTrue(all(c['data_classification'] == 'confidential' for c in router.calls))

    async def test_same_project_serial_and_all_available_tasks_drain(self):
        self.enqueue('a', 'same')
        self.enqueue('b', 'same')
        router = Router()
        await AutonomyWorker(self.queue, self.root / 'artifacts', router=router).run(once=True)
        self.assertEqual(router.maximum, 1)
        self.assertEqual(len(router.calls), 2)

    async def test_failed_inference_is_retryable_and_does_not_leak_exception(self):
        self.enqueue('a', 'a')
        router = Router(fail=True)
        await AutonomyWorker(self.queue, self.root / 'artifacts', router=router).run(once=True)
        task = self.queue.get('a')
        self.assertNotIn('secret must', json.dumps(task))
        self.assertEqual(task['attempts'], 1)
        self.assertEqual(len(list((self.root / 'artifacts').glob('[0-9a-f]' * 64 + '.json'))), 0)

    async def test_provider_outages_preserve_retry_budget_beyond_three_cycles(self):
        self.enqueue('a', 'a')
        router = Router()
        async def unavailable(*args, **kwargs):
            raise NoFreeRouteAvailable('private provider error must not be stored')
        router.complete = unavailable
        worker = AutonomyWorker(self.queue, self.root / 'artifacts', router=router)
        for cycle in range(5):
            task = self.queue.claim('test', now=10000000000 + cycle * 301)
            self.assertIsNotNone(task)
            await worker._execute(task)
            saved = self.queue.get('a')
            self.assertEqual(saved['state'], 'queued')
            self.assertEqual(saved['attempts'], 0)
            self.assertNotIn('private provider error', json.dumps(saved))

    async def test_invalid_classification_fails_without_inference(self):
        self.enqueue('a', 'a', data_classification='typo')
        router = Router()
        await AutonomyWorker(self.queue, self.root / 'artifacts', router=router).run(once=True)
        self.assertEqual(router.calls, [])

    async def test_invalid_kind_cannot_execute_shell(self):
        self.queue.enqueue('a', 'a', {'kind': 'shell', 'prompt': 'touch /tmp/unsafe'})
        router = Router()
        await AutonomyWorker(self.queue, self.root / 'artifacts', router=router).run(once=True)
        self.assertEqual(router.calls, [])

    async def test_request_timeout_releases_claim_for_retry(self):
        self.enqueue('a', 'a')
        router = Router()
        await AutonomyWorker(self.queue, self.root / 'artifacts', router=router, request_timeout=.01).run(once=True)
        self.assertEqual(self.queue.get('a')['attempts'], 0)
        self.assertEqual(self.queue.get('a')['state'], 'queued')
        self.assertIn('MODEL_TIMEOUT', json.dumps(self.queue.get('a')))
        self.assertEqual(router.active, 0)

    async def test_repeated_model_timeouts_preserve_retry_budget(self):
        self.enqueue('a', 'a')
        router = Router()
        worker = AutonomyWorker(self.queue, self.root / 'artifacts', router=router, request_timeout=.01)
        for cycle in range(5):
            task = self.queue.claim('test', now=10000000000 + cycle * 301)
            self.assertIsNotNone(task)
            await worker._execute(task)
            self.assertEqual(self.queue.get('a')['state'], 'queued')
            self.assertEqual(self.queue.get('a')['attempts'], 0)
        self.assertEqual(router.active, 0)

    async def test_short_leases_are_renewed_during_inference(self):
        self.enqueue('a', 'a')
        worker = AutonomyWorker(self.queue, self.root / 'artifacts', router=Router(delay=1.2), lease_seconds=1)
        await worker.run(once=True)
        self.assertEqual(self.queue.get('a')['state'], 'completed')

    async def test_shutdown_cancels_inference_and_retains_retryable_task(self):
        self.enqueue('a', 'a')
        router = Router()
        worker = AutonomyWorker(self.queue, self.root / 'artifacts', router=router)
        run = asyncio.create_task(worker.run())
        await asyncio.sleep(.02)
        worker.stop.set()
        await asyncio.wait_for(run, 1)
        self.assertEqual(router.active, 0)
        self.assertEqual(self.queue.get('a')['state'], 'queued')
        self.assertEqual(json.loads((self.root / 'artifacts/worker-status.json').read_text())['state'], 'stopped')

    async def test_checkpoint_resumes_generated_result_without_second_inference(self):
        self.enqueue('a', 'a')
        task = self.queue.claim('old')
        artifact = {'kind': 'plan', 'stage': 'artifact_ready', 'product_complete': False, 'content': 'Saved'}
        self.queue.checkpoint('a', task['token'], {'stage': 'generated', 'artifact': artifact})
        self.queue.fail('a', task['token'], 'INTERRUPTED', retry_delay=0)
        router = Router()
        await AutonomyWorker(self.queue, self.root / 'artifacts', router=router).run(once=True)
        self.assertEqual(router.calls, [])
        self.assertEqual(self.queue.get('a')['state'], 'completed')

    async def test_invalid_patch_does_not_become_completed_artifact(self):
        self.queue.enqueue('a', 'a', {'kind': 'patch', 'prompt': 'Make a patch'})
        await AutonomyWorker(self.queue, self.root / 'artifacts', router=Router()).run(once=True)
        self.assertEqual(self.queue.get('a')['state'], 'queued')


if __name__ == '__main__':
    unittest.main()
