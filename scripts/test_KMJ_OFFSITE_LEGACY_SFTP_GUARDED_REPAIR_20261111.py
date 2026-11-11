"""Offline mock-only regression of the guarded legacy offsite service repair."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'KMJ_OFFSITE_LEGACY_SFTP_GUARDED_REPAIR_20261111.py'
spec = importlib.util.spec_from_file_location('kmj_pinned_sftp_repair', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GuardedRepairTests(unittest.TestCase):
    def recipe(self, ssh='ssh -i /tmp/old-key oldhost "mkdir -p /legacy"',
               rsync='rsync -a /vault/ oldhost:/legacy/', after=''):
        lines = ['#!/bin/bash\n', 'set -Eeuo pipefail\n']
        lines.extend('# old fixed reviewed setup\n' for _ in range(2, 15))
        lines.extend([
            'find /some/source -type f\n',
            'age -r RECIPIENT -o /vault/new.age /tmp/archive\n',
            'tar czf /tmp/archive /source\n',
            'age -r RECIPIENT -o /vault/new.age /tmp/archive\n',
            'true\n', 'true\n', 'true\n', 'true\n',
            'mv /tmp/new.age /vault/new.age\n',
            'true\n', 'sha256sum /vault/new.age\n',
        ])
        while len(lines) < 28:
            lines.append('true\n')
        assert len(lines) == 28
        return (''.join(lines) + ssh + '\n' + rsync + '\n' + after).encode()

    def test_valid_exact_tail_excludes_ssh_and_rsync(self):
        prefix = module.fixed_prefix(self.recipe())
        self.assertEqual(len(prefix.splitlines()), 28)
        self.assertNotIn(b'ssh -i', prefix)
        self.assertNotIn(b'rsync -a', prefix)
        self.assertEqual(module.call(['/bin/bash', '-n'], input_data=prefix, timeout=10).returncode, 0)

    def test_wrong_tail_and_extra_operation_denied(self):
        cases = [
            self.recipe(ssh='false'), self.recipe(rsync='sftp -b /tmp/batch'),
            self.recipe(after='echo unreviewed-operation\n'),
        ]
        for content in cases:
            with self.subTest(tail=content[-35:]):
                with self.assertRaises(module.Block):
                    module.fixed_prefix(content)

    def test_source_with_prior_ssh_or_continuation_denied(self):
        with self.assertRaisesRegex(module.Block, 'LEGACY_PREFIX_UNEXPECTED_CONTROL'):
            module.fixed_prefix(self.recipe().replace(b'true\n', b'ssh previous-host\n', 1))
        lines = self.recipe().splitlines(keepends=True)
        lines[27] = b'true \\\n'
        with self.assertRaisesRegex(module.Block, 'LEGACY_PREFIX_CONTINUED_INTO_SSH'):
            module.fixed_prefix(b''.join(lines))

    def test_options_forbid_password_agent_or_insecure_hostkey(self):
        options = module.sftp_argv(Path('/tmp/pinned'), Path('/tmp/batch'))
        self.assertEqual(options[:3], ['/usr/bin/sftp', '-F', '/dev/null'])
        self.assertEqual(options[-2:], ['--', 'info@34.63.5.14'])
        values = [options[i + 1] for i in range(len(options) - 1) if options[i] == '-o']
        for expected in (
            'BatchMode=yes', 'IdentitiesOnly=yes', 'IdentityAgent=none',
            'PreferredAuthentications=publickey', 'PasswordAuthentication=no',
            'KbdInteractiveAuthentication=no', 'StrictHostKeyChecking=yes',
            'ProxyCommand=none', 'GlobalKnownHostsFile=/dev/null',
            'HostKeyAlgorithms=ssh-ed25519',
        ):
            self.assertIn(expected, values)
        self.assertNotIn('StrictHostKeyChecking=no', values)

    def test_wrong_host_rejects_service_apply_without_mutation(self):
        with patch.object(module.os, 'geteuid', return_value=0), \
             patch.object(module.socket, 'gethostname', return_value='other-host'), \
             patch.object(module.sys, 'argv', ['worker.py', '--apply']), \
             patch.object(module, 'setup_install') as installer:
            self.assertEqual(module.main(), 2)
            installer.assert_not_called()

    def test_installer_denies_failed_write_before_service_start(self):
        with tempfile.TemporaryDirectory() as root:
            fake = Path(root) / 'rootcopy.py'
            fake.write_bytes(b'#!/usr/bin/python3\npass\n')
            recorded = []
            def write(path, content, mode):
                recorded.append((path, mode))
                if path == module.DROPIN:
                    raise module.Block('TEST_DROPIN_FAILURE')
            with patch.object(module, 'check_legacy', return_value=self.recipe()), \
                 patch.object(module, 'fixed_prefix', return_value=b'true\n'), \
                 patch.object(module, 'unit_preflight'), \
                 patch.object(module, 'pinned_conf'), \
                 patch.object(module.os, 'makedirs'), \
                 patch.object(module, '_protected_write', side_effect=write), \
                 patch.object(module, 'read_private', return_value=b'#!/usr/bin/python3\npass\n'), \
                 patch.object(module, 'prop', return_value='failed'), \
                 patch.object(module, 'call', return_value=subprocess.CompletedProcess([], 0, b'', b'')), \
                 patch.object(module, 'REPAIR_FILE', Path(root) / 'missing.py'), \
                 patch.object(module, 'DROPIN', Path(root) / 'absent.conf'), \
                 patch.object(module, 'DROPIN_DIR', Path(root)), \
                 patch.object(module, '__file__', str(fake)):
                with self.assertRaisesRegex(module.Block, 'TEST_DROPIN_FAILURE'):
                    module.setup_install()
            self.assertEqual([mode for _, mode in recorded], [0o500, 0o644])

    def test_service_pass_requires_exact_invocation_backup_receipts(self):
        required = (b"HOSTKEY_PIN=PASS\nSSH_AUTH=PASS\n"
                    b"LOCAL_AGE_ENCRYPTED_ARCHIVE=PASS\n"
                    b"OFFSITE_TRANSFER=PASS\nSHA256_READBACK=PASS\n"
                    b"BACKUP_OFFSITE=PASS\n")
        with patch.object(module, 'prop', return_value='a' * 32), \
             patch.object(module, 'call', return_value=subprocess.CompletedProcess([], 0, required, b'')) as journal:
            module.verify_exact_service_receipt()
            self.assertIn('_SYSTEMD_INVOCATION_ID=' + 'a' * 32,
                          journal.call_args.args[0])
        with patch.object(module, 'prop', return_value='a' * 32), \
             patch.object(module, 'call', return_value=subprocess.CompletedProcess(
                 [], 0, b'SSH_AUTH=PASS\nHOSTKEY_PIN=PASS\n', b'')):
            with self.assertRaisesRegex(module.Block, 'SERVICE_INDEPENDENT_RECEIPT_MISSING'):
                module.verify_exact_service_receipt()

    def test_missing_invocation_denies_service_success_claim(self):
        for invalid in ('', 'bad-id', 'a' * 31):
            with patch.object(module, 'prop', return_value=invalid), \
                 patch.object(module, 'call') as journal:
                with self.assertRaisesRegex(module.Block, 'SERVICE_INVOCATION_UNAVAILABLE'):
                    module.verify_exact_service_receipt()
                journal.assert_not_called()

    def test_remote_publication_uses_hardlink_not_overwriting_rename(self):
        with tempfile.TemporaryDirectory() as td:
            ciphertext = Path(td) / 'ciphertext.age'
            ciphertext.write_bytes(b'age-encryption.org/v1\n' + b'X' * 100)
            batches = []
            def read_batch(_known, _batch, instructions, timeout=100):
                batches.append(instructions)
            with patch.object(module, 'VAULT', Path(td)), \
                 patch.object(module, 'sftp', side_effect=read_batch), \
                 patch.object(module, 'digest_regular_download', return_value='a' * 64):
                module.transfer(ciphertext, 'a' * 64, '34.63.5.14 ssh-ed25519 AAAABBBB\n')
            batch = '\n'.join(batches)
            self.assertIn('ln .probe-', batch)
            self.assertIn('ln kmj-legacy-', batch)
            self.assertIn('chmod 600 kmj-legacy-', batch)
            self.assertIn('get -p kmj-legacy-', batch)
            self.assertNotIn('\nrename ', batch)

    def test_rollback_refuses_foreign_dropin_and_never_starts_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            dropin = Path(td) / 'only-our-dropin.conf'
            dropin.write_text('not our configuration\n')
            with patch.object(module, 'DROPIN', dropin), \
                 patch.object(module, 'prop', return_value='inactive'), \
                 patch.object(module, 'read_private', return_value=b'foreign'), \
                 patch.object(module, 'call') as systemd:
                with self.assertRaisesRegex(module.Block, 'ROLLBACK_DROPIN_NOT_OURS'):
                    module.rollback_installed()
                self.assertTrue(dropin.exists())
                systemd.assert_not_called()

            dropin.write_bytes(module.DROPIN_TEXT.encode('ascii'))
            with patch.object(module, 'DROPIN', dropin), \
                 patch.object(module, 'prop', return_value='inactive'), \
                 patch.object(module, 'read_private', return_value=module.DROPIN_TEXT.encode('ascii')), \
                 patch.object(module, 'call', return_value=subprocess.CompletedProcess([], 0, b'', b'')) as systemd:
                module.rollback_installed()
                self.assertFalse(dropin.exists())
                self.assertEqual(systemd.call_args.args[0],
                                 ['/usr/bin/systemctl', 'daemon-reload'])

    def test_inspect_never_uploads_or_modifies_service(self):
        with patch.object(module, 'check_legacy', return_value=b'fixed'), \
             patch.object(module, 'fixed_prefix', return_value=b'true\n'), \
             patch.object(module, 'unit_preflight'), \
             patch.object(module, 'pinned_conf'), \
             patch.object(module, 'transfer') as transfer, \
             patch.object(module, '_protected_write') as writer:
            module.check_mode()
            transfer.assert_not_called()
            writer.assert_not_called()

    def test_plaintext_cannot_pass_age_ciphertext_preflight(self):
        with tempfile.TemporaryDirectory() as root:
            fake = Path(root) / 'notencrypted.age'
            fake.write_bytes(b'NOT_AGE_ENCRYPTED' + b'X' * 100)
            with patch.object(module, 'protected_chain'):
                with self.assertRaises(module.Block):
                    module.digest_cipher(fake)


if __name__ == '__main__':
    unittest.main()
