"""Offline mock-only regression of the guarded legacy offsite service repair."""
from __future__ import annotations
import contextlib
import io
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
    def recipe(self, ssh='SSH_OPTIONS="ssh -i /tmp/old-key"',
               rsync='rsync -e "$SSH_OPTIONS" /vault/ oldhost:/legacy/',
               after='echo "backup upload complete"'):
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

    def test_tail_shape_only_reports_classes_not_source_data(self):
        # Synthetic counterpart of reviewed source, no credentials/paths emitted.
        first = self.recipe()
        expected = module.tail_shape_report(first)
        self.assertEqual(expected["TAIL_SOURCE_SHA"], "PASS")
        self.assertEqual(expected["TAIL_LAST_TWO_ACTIVE"], "30_31")
        self.assertEqual(expected["TAIL_LINE29_SHAPE"], "VARIABLE_ASSIGNMENT")
        self.assertEqual(expected["TAIL_LINE30_SHAPE"], "DIRECT_RSYNC")
        self.assertEqual(expected["TAIL_AFTER_LINE30_ACTIVE_COUNT"], "1")
        self.assertEqual(expected["TAIL_AUTOMATIC_REPAIR_ALLOWED"], "NO")
        self.assertNotIn("old-key", str(expected))
        self.assertNotIn("/vault/", str(expected))

    def test_trailing_comments_and_commands_are_distinguished_without_leak(self):
        trailing_comments = self.recipe(after="\n# audit-only comment\n \n")
        info = module.tail_shape_report(trailing_comments)
        self.assertEqual(info["TAIL_LINE29_SHAPE"], "VARIABLE_ASSIGNMENT")
        self.assertEqual(info["TAIL_LINE30_SHAPE"], "DIRECT_RSYNC")
        self.assertEqual(info["TAIL_AFTER_LINE30_ACTIVE_COUNT"], "1")
        self.assertEqual(info["TAIL_AFTER_LINE30_COMMENT_COUNT"], "1")
        extra = self.recipe(after="echo DO_NOT_DISCLOSE_SECRETS\n")
        info = module.tail_shape_report(extra)
        self.assertEqual(info["TAIL_AFTER_LINE30_ACTIVE_COUNT"], "1")
        self.assertEqual(info["TAIL_LAST_ACTIVE_LINE"], "31")
        self.assertNotIn("DO_NOT_DISCLOSE_SECRETS", str(info))

    def test_embedded_or_indirect_remote_commands_remain_untrusted(self):
        indirect = self.recipe(ssh='REMOTE="ssh -i /root/private"', rsync='if rsync -a /vault /remote; then')
        info = module.tail_shape_report(indirect)
        self.assertEqual(info["TAIL_LINE29_SHAPE"], "VARIABLE_ASSIGNMENT")
        self.assertEqual(info["TAIL_LINE30_SHAPE"], "SHELL_CONTROL")
        self.assertEqual(info["TAIL_AUTOMATIC_REPAIR_ALLOWED"], "NO")
        with self.assertRaises(module.Block):
            module.fixed_prefix(indirect)

    def test_tail_readonly_does_not_install_or_transfer(self):
        with patch.object(module, "check_legacy", return_value=self.recipe()), \
             patch.object(module, "setup_install") as install, \
             patch.object(module, "transfer") as transfer:
            module.tail_review()
            install.assert_not_called()
            transfer.assert_not_called()

    def test_tail31_status_class_and_no_argument_exposure(self):
        raw = self.recipe(
            ssh='SSH_FLAGS="ssh -i /root/SECRET"',
            rsync='rsync -e "$SSH_FLAGS" /vault/ restricted:/path/',
            after='echo "upload complete"'
        )
        r = module.tail_shape_report(raw)
        self.assertEqual(r["TAIL_29_VARIABLE_CLASS"], "SSH_NAMED")
        self.assertEqual(r["TAIL_30_USES_VARIABLE_29"], "YES")
        self.assertEqual(r["TAIL_30_HAS_RSH_FLAG"], "YES")
        self.assertEqual(r["TAIL_31_COMMAND_CLASS"], "PRINT_STATUS")
        self.assertEqual(r["TAIL_31_SAFE_TO_DROP"], "NOT_APPROVED")
        self.assertNotIn("SECRET", str(r))
        self.assertNotIn("restricted:/path/", str(r))

    def test_tail31_cleanup_and_substitution_never_auto_approved(self):
        raw = self.recipe(
            ssh='SSH_FLAGS="ssh -i /root/SECRET"',
            rsync='rsync -e "$SSH_FLAGS" /vault/ restricted:/path/',
            after='rm -f /vault/important.age'
        )
        r = module.tail_shape_report(raw)
        self.assertEqual(r["TAIL_31_COMMAND_CLASS"], "LOCAL_CLEANUP")
        self.assertEqual(r["TAIL_31_SAFE_TO_DROP"], "NOT_APPROVED")
        self.assertNotIn("/vault/important", str(r))
        raw = self.recipe(
            ssh='SSH_FLAGS="ssh $(touch /tmp/side-effect)"',
            rsync='rsync -e "$SSH_FLAGS" /vault/ restricted:/path/',
            after='echo "$(touch /tmp/side-effect)"'
        )
        r = module.tail_shape_report(raw)
        self.assertEqual(r["TAIL_29_COMMAND_SUBSTITUTION"], "YES")
        self.assertEqual(r["TAIL_31_SUBSTITUTION"], "YES")
        self.assertEqual(r["TAIL_31_SAFE_TO_DROP"], "NOT_APPROVED")

    def test_valid_exact_tail_excludes_ssh_and_rsync(self):
        prefix = module.fixed_prefix(self.recipe())
        self.assertEqual(len(prefix.splitlines()), 28)
        self.assertNotIn(b'ssh -i', prefix)
        self.assertNotIn(b'rsync -a', prefix)
        self.assertEqual(module.call(['/bin/bash', '-n'], input_data=prefix, timeout=10).returncode, 0)

    def test_wrong_tail_and_extra_operation_denied(self):
        cases = [
            self.recipe(ssh='false'), self.recipe(rsync='sftp -b /tmp/batch'),
            self.recipe(after='rm -f /vault/archive.age\n'),
        ]
        for content in cases:
            with self.subTest(tail=content[-35:]):
                with self.assertRaises(module.Block):
                    module.fixed_prefix(content)

    def test_exact_ssh_variable_and_rsync_link_is_required(self):
        cases = [
            self.recipe(ssh='REMOTE="ssh -i /tmp/key"'),
            self.recipe(ssh='SSH_OPTIONS="ssh -i /tmp/key"', rsync='rsync -a /vault/ oldhost:/legacy/'),
            self.recipe(ssh='SSH_OPTIONS="ssh -i /tmp/key"', rsync='rsync -e "$UNRELATED" /vault/ oldhost:/legacy/'),
            self.recipe(ssh='SSH_OPTIONS="ssh -i /tmp/key"', rsync='rsync -e "$SSH_OPTIONS" --delete /vault/ oldhost:/legacy/'),
            self.recipe(ssh='SSH_OPTIONS="ssh -i /tmp/key"', rsync='rsync -e "$SSH_OPTIONS" /vault/ oldhost:/legacy/ || true'),
        ]
        for source in cases:
            with self.subTest(source=source[-100:]):
                with self.assertRaises(module.Block):
                    module.fixed_prefix(source)

    def test_shell_injection_and_status_side_effects_fail_closed(self):
        cases = [
            self.recipe(ssh='SSH_OPTIONS="ssh $(touch /tmp/injected)"'),
            self.recipe(ssh='SSH_OPTIONS="ssh -i /tmp/key; echo unsafe"'),
            self.recipe(after='echo "backup complete" && touch /tmp/injected'),
            self.recipe(after='echo "$(touch /tmp/injected)"'),
            self.recipe(after='echo $?'),
            self.recipe(after='rm -f /vault/new.age'),
            self.recipe(after='echo "backup complete"\necho "extra"'),
        ]
        for source in cases:
            with self.subTest(source=source[-90:]):
                with self.assertRaises(module.Block):
                    module.fixed_prefix(source)

    def test_only_trusted_local_prefix_is_accepted(self):
        raw = self.recipe()
        kept = module.fixed_prefix(raw)
        self.assertEqual(kept, b''.join(raw.splitlines(keepends=True)[:28]))
        for value in (b'SSH_OPTIONS=', b'rsync -e', b'backup upload complete'):
            self.assertNotIn(value, kept)

    def test_source_with_prior_ssh_or_continuation_denied(self):
        with self.assertRaisesRegex(module.Block, 'LEGACY_PREFIX_UNEXPECTED_CONTROL'):
            module.fixed_prefix(self.recipe().replace(b'true\n', b'ssh previous-host\n', 1))
        lines = self.recipe().splitlines(keepends=True)
        lines[27] = b'true \\\n'
        with self.assertRaisesRegex(module.Block, 'LEGACY_PREFIX_CONTINUED_INTO_SSH'):
            module.fixed_prefix(b''.join(lines))

    def test_receiver_auth_preflight_uses_pinned_sftp_without_archive_transfer(self):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as td:
            with patch.object(module.tempfile, "TemporaryDirectory",
                              return_value=contextlib.nullcontext(td)), \
                 patch.object(module, "sftp") as remote, \
                 contextlib.redirect_stdout(out):
                module.receiver_preflight("34.63.5.14 ssh-ed25519 TESTPUBLICKEY\n")
            remote.assert_called_once()
            args = remote.call_args.args
            self.assertEqual(args[2], "pwd\ncd /home/info/kmj-recovery-scratch\n")
            self.assertEqual(remote.call_args.kwargs["timeout"], 45)
        self.assertIn("RECEIVER_PINNED_SFTP_AUTH_PRE_ARCHIVE=PASS", out.getvalue())

    def test_receiver_preflight_failure_blocks_before_local_backup_execution(self):
        observations = []
        with patch.object(module, "check_legacy", side_effect=lambda:
                          observations.append("legacy") or b"PINNED"), \
             patch.object(module, "fixed_prefix", side_effect=lambda raw:
                          observations.append("prefix") or b"true\n"), \
             patch.object(module, "pinned_conf", side_effect=lambda:
                          observations.append("pin")), \
             patch.object(module, "host_key", side_effect=lambda:
                          observations.append("hostkey") or "test hostkey\n"), \
             patch.object(module, "receiver_preflight",
                          side_effect=module.Block("PINNED_PUBLICKEY_DENIED")), \
             patch.object(module, "vault_list") as vault, \
             patch.object(module.subprocess, "run") as shell:
            with self.assertRaisesRegex(module.Block, "PINNED_PUBLICKEY_DENIED"):
                module.run_job()
            vault.assert_not_called()
            shell.assert_not_called()
        self.assertEqual(observations, ["legacy", "prefix", "pin", "hostkey"])

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

    def test_readonly_inspect_reports_fail_closed_source_enum(self):
        output = io.StringIO()
        with patch.object(module.os, 'geteuid', return_value=0), \
             patch.object(module.socket, 'gethostname', return_value='KMJ-elite'), \
             patch.object(module.sys, 'argv', ['repair.py', '--inspect']), \
             patch.object(module, 'check_mode', side_effect=module.Block('UNIT_TYPE_NOT_ONESHOT')), \
             patch.object(module, 'setup_install') as install, \
             contextlib.redirect_stdout(output):
            self.assertEqual(module.main(), 3)
            install.assert_not_called()
        self.assertIn('PRECHECK_BLOCKER=UNIT_TYPE_NOT_ONESHOT', output.getvalue())
        self.assertIn('LEGACY_SFTP_REPAIR=BLOCKED_OR_UNVERIFIED', output.getvalue())

    def test_readonly_inspect_sanitizes_unexpected_exception_text(self):
        output = io.StringIO()
        with patch.object(module.os, 'geteuid', return_value=0), \
             patch.object(module.socket, 'gethostname', return_value='KMJ-elite'), \
             patch.object(module.sys, 'argv', ['repair.py', '--inspect']), \
             patch.object(module, 'check_mode', side_effect=module.Block('private /root/secret-key')), \
             patch.object(module, 'setup_install') as install, \
             contextlib.redirect_stdout(output):
            self.assertEqual(module.main(), 3)
            install.assert_not_called()
        self.assertIn('PRECHECK_BLOCKER=UNCLASSIFIED_GATE', output.getvalue())
        self.assertNotIn('/root/', output.getvalue())

    def test_inspect_stage_receipts_never_start_service(self):
        output = io.StringIO()
        with patch.object(module, 'check_legacy', return_value=b'known-source'), \
             patch.object(module, 'fixed_prefix', return_value=b'local-prefix'), \
             patch.object(module, 'prop', return_value='oneshot'), \
             patch.object(module, 'unit_preflight'), \
             patch.object(module, 'pinned_conf'), \
             patch.object(module, 'setup_install') as installer, \
             patch.object(module, 'transfer') as transfer, \
             contextlib.redirect_stdout(output):
            module.check_mode()
        installer.assert_not_called()
        transfer.assert_not_called()
        self.assertIn('PREFLIGHT_LEGACY_SOURCE=PASS', output.getvalue())
        self.assertIn('PREFLIGHT_PREFIX_SYNTAX=PASS', output.getvalue())
        self.assertIn('PREFLIGHT_UNIT_TYPE=ONESHOT', output.getvalue())
        self.assertIn('PREFLIGHT_PINNED_CONFIG=PASS', output.getvalue())
        self.assertIn('SERVICE_EXECUTION=NOT_RUN', output.getvalue())

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

    def test_service_start_failure_removes_only_new_helper_and_dropin(self):
        code = b"#!/usr/bin/python3\npass\n"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repair = root / 'repair.py'
            dropin_dir = root / 'service.d'
            dropin = dropin_dir / '90-exact.conf'
            local = root / 'source.py'
            local.write_bytes(code)
            calls = []
            def systemd(cmd, **kwargs):
                calls.append(tuple(cmd))
                if cmd[:2] == ['/usr/bin/systemctl', 'start']:
                    return subprocess.CompletedProcess(cmd, 1, b'', b'')
                return subprocess.CompletedProcess(cmd, 0, b'', b'')
            def read(path, _limit, mode=0o022):
                return Path(path).read_bytes()
            with patch.object(module, 'check_legacy', return_value=b'legacy'), \
                 patch.object(module, 'fixed_prefix', return_value=b'true\n'), \
                 patch.object(module, 'unit_preflight'), \
                 patch.object(module, 'pinned_conf'), \
                 patch.object(module, 'protected_chain'), \
                 patch.object(module, 'REPAIR_FILE', repair), \
                 patch.object(module, 'DROPIN_DIR', dropin_dir), \
                 patch.object(module, 'DROPIN', dropin), \
                 patch.object(module, '__file__', str(local)), \
                 patch.object(module, 'read_private', side_effect=read), \
                 patch.object(module, 'call', side_effect=systemd):
                with self.assertRaisesRegex(module.Block, 'SERVICE_EXECUTION_FAILED'):
                    module.setup_install()
                self.assertFalse(repair.exists())
                self.assertFalse(dropin.exists())
                self.assertEqual(sum(1 for x in calls if x[:2] ==
                                     ('/usr/bin/systemctl', 'daemon-reload')), 2)
                # No stale helper may poison the next guarded attempt.
                with self.assertRaisesRegex(module.Block, 'SERVICE_EXECUTION_FAILED'):
                    module.setup_install()
                self.assertFalse(repair.exists())
                self.assertFalse(dropin.exists())

    def test_explicit_rollback_removes_only_exact_matching_helper(self):
        code = b"#!/usr/bin/python3\npass\n"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            helper = root / 'helper.py'
            dropin = root / '90-exact.conf'
            local = root / 'source.py'
            local.write_bytes(code)
            helper.write_bytes(code)
            dropin.write_bytes(module.DROPIN_TEXT.encode('ascii'))
            with patch.object(module, 'REPAIR_FILE', helper), \
                 patch.object(module, 'DROPIN', dropin), \
                 patch.object(module, '__file__', str(local)), \
                 patch.object(module, 'prop', return_value='inactive'), \
                 patch.object(module, 'protected_chain'), \
                 patch.object(module, 'call', return_value=subprocess.CompletedProcess([], 0, b'', b'')):
                module.rollback_installed()
                self.assertFalse(helper.exists())
                self.assertFalse(dropin.exists())
                # Foreign content is preserved, and even our dropin cannot
                # authorize removal of an unrelated modified helper.
                helper.write_bytes(b'NOT_THE_OWNED_HELPER\n')
                dropin.write_bytes(module.DROPIN_TEXT.encode('ascii'))
                with self.assertRaisesRegex(module.Block, 'ROLLBACK_HELPER_NOT_OURS'):
                    module.rollback_installed()
                self.assertTrue(helper.exists())
                self.assertTrue(dropin.exists())

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
