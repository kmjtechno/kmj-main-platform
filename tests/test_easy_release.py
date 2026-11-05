import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).parents[1] / 'scripts/kmj_release.py'

class ReleaseTests(unittest.TestCase):
    def module(self):
        self.assertTrue(SOURCE.exists(), 'release launcher is not implemented')
        spec = importlib.util.spec_from_file_location('release', SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def report(self, **changes):
        values = dict(TARGET_SHA='cd9580701d3cea19d7d4e4c96ebe70c0553fbf37',
                      CURRENT_RELEASE='platform-574e443a2c75',
                      CANDIDATE='PASS', CANDIDATE_UI_BUNDLE='PASS',
                      CANDIDATE_RUNTIME_ENV='PRESENT', CANDIDATE_NGINX_ACCESS='PASS',
                      BACKUP_WITNESS='PASS', APPROVAL='PASS', RELEASE_UNIT='INSTALLED',
                      RELEASE_READINESS='READY_TO_ACTIVATE', PRODUCTION_CHANGED='NO')
        values.update(changes)
        return '\n'.join(f'{k}={v}' for k,v in values.items())

    def test_valid_readiness_allows_request(self):
        m = self.module()
        self.assertTrue(m.ready(self.report(), 0))

    def test_stale_approval_blocks_request(self):
        m = self.module()
        self.assertFalse(m.ready(self.report(APPROVAL='APPROVES_OTHER_SHA'), 0))

    def test_missing_gate_blocks_request(self):
        m = self.module()
        self.assertFalse(m.ready(self.report().replace('BACKUP_WITNESS=PASS\n', ''), 0))

    def test_duplicate_verdict_blocks_request(self):
        m = self.module()
        self.assertFalse(m.ready(self.report()+'\nRELEASE_READINESS=BLOCKED', 0))

    def test_nonzero_exit_blocks_even_with_ready_text(self):
        m = self.module()
        self.assertFalse(m.ready(self.report(), 1))

    def test_wrong_candidate_blocks_request(self):
        m = self.module()
        self.assertFalse(m.ready(self.report(TARGET_SHA='a'*40), 0))

    def test_explicit_blocker_blocks_even_with_ready_text(self):
        m = self.module()
        self.assertFalse(m.ready(self.report()+'\nBLOCKER=ANY', 0))

    def test_untrusted_bytes_never_execute(self):
        m = self.module()
        with self.assertRaises(ValueError):
            m.verify_source(b'print("untrusted")')

    def test_blocked_check_never_starts_unit(self):
        m = self.module()
        with patch.object(m.os, 'geteuid', return_value=0), patch.object(m.socket, 'gethostname', return_value='KMJ-elite'), patch.object(m, 'check', return_value=False), patch.object(m.subprocess, 'run') as run:
            self.assertEqual(m.main(['deploy']), 2)
            run.assert_not_called()

    def test_check_never_starts_unit(self):
        m = self.module()
        with patch.object(m.os, 'geteuid', return_value=0), patch.object(m.socket, 'gethostname', return_value='KMJ-elite'), patch.object(m, 'check', return_value=True), patch.object(m.subprocess, 'run') as run:
            self.assertEqual(m.main(['check']), 0)
            run.assert_not_called()

    def test_nonroot_cannot_request_unit(self):
        m = self.module()
        with patch.object(m.os, 'geteuid', return_value=1000), patch.object(m, 'check') as check, patch.object(m.subprocess, 'run') as run:
            self.assertEqual(m.main(['deploy']), 2)
            check.assert_not_called()
            run.assert_not_called()

    def test_unit_timeout_is_unknown_not_success(self):
        m = self.module()
        with patch.object(m.os, 'geteuid', return_value=0), patch.object(m.socket, 'gethostname', return_value='KMJ-elite'), patch.object(m, 'check', return_value=True), patch.object(m.subprocess, 'run', side_effect=m.subprocess.TimeoutExpired('systemctl', 600)):
            self.assertEqual(m.main(['deploy']), 3)

if __name__ == '__main__':
    unittest.main()
