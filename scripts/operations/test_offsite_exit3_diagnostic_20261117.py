import importlib.util
import json
from pathlib import Path
import types
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('kmj_exit3', HERE / 'offsite_exit3_diagnostic_20261117.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
ID = 'a' * 32

def sample(status='3', result='exit-code', invocation=ID):
    values = dict(LoadState='loaded', ActiveState='failed', SubState='failed', Result=result,
                  ExecMainStatus=status, InvocationID=invocation)
    return ''.join(f'{p}={values[p]}\n' for p in m.PROPERTIES)

class Runner:
    def __init__(self, first=None, log='', last=None, journal_rc=0, fail_show=False):
        self.first = sample() if first is None else first
        self.last = self.first if last is None else last
        self.log = log
        self.journal_rc = journal_rc
        self.fail_show = fail_show
        self.calls = []
        self.show_count = 0
    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        assert kwargs.get('capture_output') is True
        assert kwargs.get('check') is False
        if argv[0] == m.SYSTEMCTL:
            self.show_count += 1
            return types.SimpleNamespace(returncode=1 if self.fail_show else 0,
                        stdout=self.first if self.show_count == 1 else self.last)
        if argv[0] == m.JOURNALCTL:
            assert argv[-1] == f'_SYSTEMD_INVOCATION_ID={ID}'
            return types.SimpleNamespace(returncode=self.journal_rc, stdout=self.log)
        raise AssertionError('Unexpected subprocess')

class TestExit3(unittest.TestCase):
    def test_exact_invocation_guard_rejection(self):
        r = Runner(log='KMJ_OFFSITE=BLOCKED_SOURCE_UNAVAILABLE\n')
        result = m.diagnose(r, lambda: 0)
        self.assertEqual(result['failure_class'], 'GUARDED_PREFLIGHT_REJECTED')
        self.assertEqual(result['journal_scope'], 'EXACT_INVOCATION')
        self.assertEqual(result['exit_status'], '3')
        self.assertEqual(result['mutations'], 'NONE')
        self.assertFalse(result['raw_journal_exposed'])
        self.assertEqual(len(r.calls), 3)
    def test_classification_cases(self):
        cases = [
            ('No space left on device', 'STORAGE_CAPACITY'),
            ('Permission denied (publickey)', 'REMOTE_SSH_TRUST_OR_AUTH'),
            ('Host key verification failed', 'REMOTE_SSH_TRUST_OR_AUTH'),
            ('Connection refused', 'REMOTE_CONNECTIVITY'),
            ('pg_dump: error', 'DATABASE_DUMP_OR_INTEGRITY'),
            ('age: error', 'ENCRYPTION_OR_CIPHER'),
            ('File exists', 'OUTPUT_COLLISION'),
            ('ModuleNotFoundError', 'MISSING_SOURCE_OR_TOOL'),
            ('Read-only file system', 'LOCAL_PERMISSION_OR_FILESYSTEM'),
            ('Unrecognized secret token: ABCDEF', 'UNKNOWN_EXIT3_CAUSE'),
        ]
        for log, label in cases:
            with self.subTest(label=label):
                self.assertEqual(m.diagnose(Runner(log=log), lambda: 0)['failure_class'], label)
    def test_never_diagnose_non_exit3(self):
        for code, result in [('0', 'success'), ('255', 'exit-code'), ('1', 'exit-code'), ('unknown', 'exit-code')]:
            with self.subTest(code=code):
                r = Runner(first=sample(status=code, result=result), log='Permission denied (publickey)')
                self.assertEqual(m.diagnose(r, lambda: 0)['failure_class'], 'NOT_EXIT3_INVOCATION')
                self.assertEqual(len(r.calls), 1)
    def test_reject_invalid_or_missing_invocation(self):
        for ident in ['', '0'*32, 'bad-id', 'b'*31]:
            with self.subTest(ident=ident):
                r = Runner(first=sample(invocation=ident))
                self.assertEqual(m.diagnose(r, lambda: 0)['journal_scope'], 'UNAVAILABLE')
                self.assertEqual(len(r.calls), 1)
    def test_fail_closed_on_changed_invocation(self):
        r = Runner(log='Host key verification failed', last=sample(invocation='b'*32))
        self.assertEqual(m.diagnose(r, lambda:0)['failure_class'], 'INVOCATION_CHANGED')
        self.assertEqual(m.diagnose(Runner(log='Host key verification failed', last=sample(status='0')), lambda:0)['failure_class'], 'INVOCATION_CHANGED')
    def test_fail_closed_on_unavailable_journal(self):
        r = Runner(log='Permission denied (publickey)',journal_rc=1)
        self.assertEqual(m.diagnose(r, lambda:0)['journal_scope'], 'UNAVAILABLE')
        self.assertEqual(len(r.calls),2)
    def test_fail_closed_on_bad_metadata(self):
        for data in ['ExecMainStatus=3\n', sample()+'ExecMainStatus=3\n', sample().replace('Result=exit-code','Result=unsafe text')]:
            self.assertEqual(m.diagnose(Runner(first=data),lambda:0)['failure_class'],'UNIT_METADATA_UNAVAILABLE')
    def test_root_required_no_command(self):
        r = Runner(log='Permission denied (publickey)')
        self.assertEqual(m.diagnose(r, lambda:1000)['failure_class'], 'ROOT_DIAGNOSTIC_REQUIRED')
        self.assertEqual(r.calls, [])
    def test_journal_has_no_secret_output(self):
        secret='PRIVATE KEY LOCATION /root/secret/oauth/key'
        result = m.diagnose(Runner(log=secret),lambda:0)
        self.assertNotIn(secret, json.dumps(result))
        self.assertNotIn('/root/', json.dumps(result))
    def test_oversize_journal_fail_closed(self):
        r=Runner(log='x'*65537)
        self.assertEqual(m.diagnose(r,lambda:0)['journal_scope'],'UNAVAILABLE')
    def test_exact_fixed_commands(self):
        r=Runner(log='')
        m.diagnose(r,lambda:0)
        self.assertEqual(r.calls[0][:4],[m.SYSTEMCTL,'show',m.UNIT,'--no-pager'])
        self.assertEqual(r.calls[1][:5],[m.JOURNALCTL,'--no-pager','-o','cat','-n'])
        self.assertEqual(r.calls[1][-1],f'_SYSTEMD_INVOCATION_ID={ID}')

if __name__ == '__main__':
    unittest.main()
