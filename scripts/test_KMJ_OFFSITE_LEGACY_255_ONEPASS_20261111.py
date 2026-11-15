"""Offline/isolated tests. No SSH, backups, systemd or paid resources."""
from __future__ import annotations
import contextlib
import importlib.util
import io
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

MODULE_PATH = Path(__file__).with_name('KMJ_OFFSITE_LEGACY_255_ONEPASS_20261111.py')
spec = importlib.util.spec_from_file_location('offsite_onepass',MODULE_PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class OnePassTests(unittest.TestCase):
    def test_strict_sftp_ssh_options_exact_host_no_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            argv=m.sftp_args(Path(d)/'known',Path(d)/'batch')
        self.assertEqual(argv[:3], ['/usr/bin/sftp','-F','/dev/null'])
        self.assertEqual(argv[-2:], ['--','info@34.63.5.14'])
        options=[argv[i+1] for i in range(len(argv)-1) if argv[i]=='-o']
        for required in (
            'BatchMode=yes','IdentitiesOnly=yes','IdentityAgent=none',
            'PasswordAuthentication=no','KbdInteractiveAuthentication=no',
            'StrictHostKeyChecking=yes','UpdateHostKeys=no',
            'HostKeyAlgorithms=ssh-ed25519','GSSAPIAuthentication=no',
            'KbdInteractiveAuthentication=no','ProxyCommand=none',
            'PreferredAuthentications=publickey','GlobalKnownHostsFile=/dev/null'):
            self.assertIn(required,options)
        self.assertTrue(any(v.startswith('UserKnownHostsFile=') for v in options))

    def test_pinned_config_mismatch_denies_before_any_remote_action(self):
        with patch.object(m,'safe_file',return_value=b'not the pinned config'), patch.object(m,'run') as call:
            with self.assertRaisesRegex(m.Blocked,'PINNED_CONFIG_NOT_EXACT'):
                m.pin_preflight()
            call.assert_not_called()

    def test_unit_exit_255_is_only_historical_not_service_resolved(self):
        vals={
            'LoadState':'loaded','User':'root','ExecStart':'{ path=/usr/local/sbin/kmj-elite-offsite-backup ; argv[]=/usr/local/sbin/kmj-elite-offsite-backup }',
            'DropInPaths':'','ExecMainStatus':'255','Result':'exit-code','InvocationID':'a'*32,
        }
        out=io.StringIO()
        with patch.object(m,'shown',side_effect=lambda k: vals[k]), \
             patch.object(m,'safe_file',return_value=b'unreviewed legacy body'), \
             patch.object(m,'classified_journal',return_value='PUBLICKEY_AUTH_DENIED'), \
             contextlib.redirect_stdout(out):
            self.assertFalse(m.unit_audit())
        value=out.getvalue()
        self.assertIn('LEGACY_LAST_EXIT=EXIT_255',value)
        self.assertIn('LEGACY_FAILURE_CLASS=PUBLICKEY_AUTH_DENIED',value)
        self.assertIn('LEGACY_EXEC_SHA=NOT_VERIFIED',value)
        self.assertNotIn('/usr/local/sbin/',value)

    def test_wrong_host_blocks_main_with_no_systemd_call(self):
        out=io.StringIO()
        with patch.object(m.os,'geteuid',return_value=0), \
             patch.object(m.socket,'gethostname',return_value='other-machine'), \
             patch.object(m.sys,'argv',['fixed.py']), \
             patch.object(m,'shown') as shown,contextlib.redirect_stdout(out):
            self.assertEqual(m.main(),2)
        shown.assert_not_called()
        self.assertIn('ONEPASS=BLOCKED_ROOT_HOST_OR_ARGUMENTS',out.getvalue())

    def _simulate_transfer(self,*, corrupt=False):
        original=tempfile.TemporaryDirectory
        remote={}
        commands=[]
        def stage(**kwargs): return original(prefix=kwargs.get('prefix'),dir=None)
        def fake_run(argv,seconds=15):
            self.assertEqual(argv[0],'/usr/bin/age')
            destination=Path(argv[argv.index('-o')+1]);src=Path(argv[-1])
            destination.write_bytes(b'AGE_ENCRYPTED_CANARY_'+src.read_bytes())
            return subprocess.CompletedProcess(argv,0,b'',b'')
        def fake_sftp(known,batch,body,timeout=40):
            commands.append(body)
            for line in body.splitlines():
                parts=line.split()
                if not parts or parts[0] not in ('put','get','rm'):continue
                if parts[0]=='put':remote[parts[-1]]=Path(parts[-2]).read_bytes()
                if parts[0]=='get':Path(parts[-1]).write_bytes(remote[parts[1]]+(b'bad' if corrupt else b''))
                if parts[0]=='rm':remote.pop(parts[1],None)
        out=io.StringIO()
        with patch.object(m.tempfile,'TemporaryDirectory',side_effect=stage), \
             patch.object(m,'run',side_effect=fake_run), \
             patch.object(m,'checked_sftp',side_effect=fake_sftp), \
             contextlib.redirect_stdout(out):
            if corrupt:
                with self.assertRaisesRegex(m.Blocked,'SFTP_SHA256_MISMATCH'):
                    m.sftp_probe('host ssh-ed25519 ABCD\n')
            else:m.sftp_probe('host ssh-ed25519 ABCD\n')
        self.assertEqual(remote,{})
        self.assertTrue(any('put -p ' in cmd and 'chmod 600 ' in cmd for cmd in commands))
        self.assertTrue(any('\nrm ' in cmd for cmd in commands))
        return out.getvalue()

    def test_encrypted_transfer_sha_readback_and_cleanup(self):
        out=self._simulate_transfer()
        for label in ('SSH_OPTIONS=STRICT_PINNED_ONLY','SSH_AUTH=PASS','OFFSITE_TRANSFER=PASS','SHA256_READBACK=PASS','REMOTE_TEST_CLEANUP=PASS'):
            self.assertIn(label,out)

    def test_readback_mismatch_rejects_but_still_cleans(self):
        out=self._simulate_transfer(corrupt=True)
        self.assertIn('REMOTE_TEST_CLEANUP=PASS',out)
        self.assertNotIn('SHA256_READBACK=PASS',out)

if __name__=='__main__':unittest.main()
