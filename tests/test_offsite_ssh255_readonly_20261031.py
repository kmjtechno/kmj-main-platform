"""Host-free, no-credential regression/negative contracts for A2 offsite SSH255 doctor."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/operations/inspect-offsite-ssh255-20261031.py'
spec = importlib.util.spec_from_file_location('kmj_offsite_a2', SOURCE)
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class A2DoctorTests(unittest.TestCase):
    def test_classification_matches_only_allowlisted_labels(self):
        cases = {
            'Permission denied (publickey). username:secret': 'SSH_AUTH_KEY_REJECTED',
            'Host key verification failed for secret.example': 'SSH_HOSTKEY',
            'Could not resolve host secret.example': 'NETWORK_OR_REMOTE_DOWN',
            'No space left on device': 'DISK_OR_REMOTE_QUOTA',
            'No such file or directory': 'MISSING_FILE_OR_TOOL',
            'Permission denied to remote': 'LOCAL_OR_REMOTE_PERMISSION',
            'PRIVATE_KEY=never_print_this': 'UNCLASSIFIED',
        }
        for raw, expected in cases.items():
            with self.subTest(expected=expected):
                self.assertEqual(m.classify(raw), expected)

    def test_real_invocation_only_and_no_raw_secrets(self):
        calls = []
        def show(k):
            return {'LoadState': 'loaded', 'Result': 'exit-code', 'ExecMainStatus': '255',
                    'InvocationID': 'a' * 32,
                    'ExecStart': 'argv[]=/bin/sh SECRETPASSWORD --offsite',
                    'User': 'root'}.get(k)
        def journal(invocation):
            calls.append(invocation)
            return 'Permission denied (publickey) key-path:/root/private/id_rsa'
        vals = m.inspect(show, journal, lambda: ('PRIVATE_VALID','PRIVATE','PIN_FORMAT_VALID'))
        self.assertEqual(vals['journal_scope'], 'EXACT_INVOCATION')
        self.assertEqual(vals['journal_failure_class'], 'SSH_AUTH_KEY_REJECTED')
        self.assertEqual(vals['sftp_identity'], 'PRIVATE')
        self.assertEqual(vals['execstart_hash_attested'], 'NO')
        self.assertEqual(vals['backup_created'], 'NOT_VERIFIED')
        self.assertEqual(vals['restore_verified'], 'NO')
        self.assertEqual(calls, ['a' * 32])
        rendered = '\n'.join(f'{k}={v}' for k, v in vals.items())
        for secret in ('SECRETPASSWORD','/root/private','id_rsa','key-path'):
            self.assertNotIn(secret, rendered)

    def test_no_cross_invocation_journal_and_no_exit_assumptions(self):
        for prop in ('0', '254', '255'):
            for invocation in ('', 'a' * 31, 'not_a_uuid'):
                calls = []
                values = {'LoadState': 'loaded', 'Result': 'exit-code', 'ExecMainStatus': prop,
                          'InvocationID': invocation, 'ExecStart': None, 'User': 'service'}
                out = m.inspect(lambda k: values[k], lambda _: calls.append('CALLED'),
                                lambda: ('MISSING','UNKNOWN','UNKNOWN'))
                self.assertEqual(out['journal_scope'], 'UNAVAILABLE')
                self.assertEqual(calls, [])
                self.assertEqual(out['systemd_user'], 'NONROOT_OR_UNKNOWN')
                self.assertEqual(out['exit_255'], 'YES' if prop == '255' else 'NOT_PROVEN')

    def test_systemctl_calls_fixed_unit_and_no_shell(self):
        result = subprocess.CompletedProcess(args=[], returncode=0, stdout='255\n', stderr='')
        with mock.patch.object(m.subprocess, 'run', return_value=result) as run:
            self.assertEqual(m.show_property('ExecMainStatus'), '255')
        args, kw = run.call_args
        self.assertEqual(args[0], ['/usr/bin/systemctl','show', m.UNIT,
                                  '--property=ExecMainStatus','--value','--no-pager'])
        self.assertEqual(kw['env'], m.ENV)
        self.assertFalse(kw['check'])
        with self.assertRaises(ValueError):
            m.show_property('Environment')

    def test_journal_bounded_exact_and_never_prints_stdout(self):
        with mock.patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess(
                [], 0, 'Permission denied (publickey)\n', '')) as run:
            out = m.journal_for_invocation('b' * 32)
            self.assertEqual(m.classify(out), 'SSH_AUTH_KEY_REJECTED')
            self.assertEqual(run.call_args.args[0][-1], '_SYSTEMD_INVOCATION_ID=' + 'b' * 32)
            self.assertNotIn('Environment=', str(run.call_args.args[0]))
        self.assertIsNone(m.journal_for_invocation('evil; rm -rf /'))
        with mock.patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'x'*70000,'')):
            self.assertIsNone(m.journal_for_invocation('a'*32))

    def test_strict_config_no_shell_or_duplicate_keys(self):
        good = ('HOST=offsite.example.test\nPORT=22\nUSER=info\nREMOTE_DIR=/safe/backups'
                '\nIDENTITY_FILE=/root/private/id_ed25519\nHOSTKEY_SHA256=SHA256:' + 'A'*43 + '\n')
        self.assertEqual(len(m.parse_config(good)), 6)
        for bad in (good+'HOST=evil\n', good+'EVIL=1\n',good.replace('PORT=22','PORT=0'),
                    good.replace('REMOTE_DIR=/safe/backups','REMOTE_DIR=/safe/../secret'),
                    good.replace('IDENTITY_FILE=/root/private/id_ed25519', 'IDENTITY_FILE=relative'),
                    good.replace('HOST=offsite.example.test','HOST=bad host'),
                    good.replace('HOSTKEY_SHA256=SHA256:'+'A'*43, 'HOSTKEY_SHA256=bad'),
                    good.replace('USER=info','USER=$(whoami)'), 'HOST=X\n'):
            with self.subTest(bad=bad[:60]):
                self.assertIsNone(m.parse_config(bad))

    def test_real_private_config_and_identity_without_disclosing_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            uid = os.getuid()
            (base/'identity').write_text('SECRET_PRIVATE_KEY')
            os.chmod(base/'identity',0o600)
            config = ('HOST=secret.example\nPORT=22\nUSER=info\nREMOTE_DIR=/backups'
                      f'\nIDENTITY_FILE={base}/identity\nHOSTKEY_SHA256=SHA256:'+'B'*43+'\n')
            (base/'sftp.conf').write_text(config)
            os.chmod(base/'sftp.conf',0o600)
            good = m.config_checks(file=base/'sftp.conf',owner_uid=uid,stop=base)
            self.assertEqual(good,('PRIVATE_VALID','PRIVATE','PIN_FORMAT_VALID'))
            self.assertNotIn('SECRET_',str(good))
            os.chmod(base/'identity',0o644)
            self.assertEqual(m.config_checks(file=base/'sftp.conf',owner_uid=uid,stop=base)[1], 'UNSAFE_FILE')
            os.chmod(base/'identity',0o600)
            os.chmod(base/'sftp.conf',0o666)
            self.assertEqual(m.config_checks(file=base/'sftp.conf',owner_uid=uid,stop=base)[0], 'UNSAFE_FILE')

    def test_symlink_hardlink_and_writable_parent_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp); uid=os.getuid()
            secret=base/'secret'; secret.write_text('key')
            os.chmod(secret,0o600)
            config=base/'config'; os.symlink(secret,config)
            self.assertEqual(m.private_regular(config,owner_uid=uid,stop=base),'UNSAFE_FILE')
            config.unlink(); os.link(secret,config)
            self.assertEqual(m.private_regular(config,owner_uid=uid,stop=base),'UNSAFE_FILE')
            config.unlink(); config.write_text('safe')
            os.chmod(config,0o600)
            os.chmod(base,0o777)
            self.assertEqual(m.private_regular(config,owner_uid=uid,stop=base),'UNSAFE_PARENT')

    def test_fail_closed_if_no_host_and_no_arguments(self):
        with mock.patch.object(m.sys,'argv',['inspect.py','--arbitrary']):
            self.assertEqual(m.main(),2)
        raw=SOURCE.read_text()
        self.assertNotIn('shell=True',raw)
        self.assertNotIn('systemctl start',raw)
        self.assertNotIn('systemctl restart',raw)
        self.assertNotIn('ssh-keyscan ',raw)
        self.assertNotIn('os.chmod(',raw)
        self.assertNotIn('os.chown(',raw)
        self.assertNotIn('write_text(',raw)


if __name__ == '__main__':
    unittest.main()
