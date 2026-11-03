"""Offline adversarial checks for the root-only, read-only one-pass diagnostics."""
import importlib.util
from pathlib import Path
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "scripts/operations/owner-production-gates-onepass-20261103.py"
spec = importlib.util.spec_from_file_location("onepass_owner_release_audit", SOURCE)
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


class OnepassOwnerAuditTests(unittest.TestCase):
    def test_compiles_without_site_path_or_import_side_effects(self):
        p = subprocess.run(
            [sys.executable, "-I", "-S", "-m", "py_compile", str(SOURCE)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_pointer_parsers_reject_unsafe_aliases(self):
        self.assertEqual(
            audit.classify_pointer("releases/platform-574e443a2c75", "production"),
            "platform-574e443a2c75",
        )
        self.assertEqual(
            audit.classify_pointer("/home/kmjprod/releases/platform-574e443a2c75", "production"),
            "platform-574e443a2c75",
        )
        self.assertEqual(
            audit.classify_pointer("../releases/" + "a" * 40 + "/apps/platform", "staging"),
            "a" * 40,
        )
        for value in (
            "../../releases/platform-574e443a2c75",
            "releases/../releases/platform-574e443a2c75",
            "/home/kmjprod/current",
            "releases/platform-574e443a2c75/.",
            "releases/platform-574e443a2c75\nTOKEN=SECRET",
        ):
            with self.subTest(value=value):
                self.assertEqual(audit.classify_pointer(value, "production"),
                                 "NONCANONICAL_LINK")

    def test_approval_fails_closed_on_missing_wrong_schema_and_false_flags(self):
        self.assertEqual(audit.approval_status(None, "production", "platform-574e443a2c75"),
                         "MISSING_OR_UNTRUSTED")
        baseline = {
            "approvedSha": "a" * 40,
            "expectedCurrentRelease": "platform-8070dad72c55",
            "backupVerified": True,
            "rollbackVerified": True,
        }
        self.assertEqual(audit.approval_status(baseline, "production",
                                               "platform-574e443a2c75"), "STALE_CURRENT")
        baseline["expectedCurrentRelease"] = "platform-574e443a2c75"
        baseline["rollbackVerified"] = False
        self.assertEqual(audit.approval_status(baseline, "production",
                                               "platform-574e443a2c75"),
                         "BACKUP_OR_ROLLBACK_FLAGS_FALSE")
        baseline["rollbackVerified"] = "yes"
        self.assertEqual(audit.approval_status(baseline, "production",
                                               "platform-574e443a2c75"),
                         "SCHEMA_INVALID")
        baseline["rollbackVerified"] = True
        baseline["command"] = "systemctl start anything"
        self.assertEqual(audit.approval_status(baseline, "production",
                                               "platform-574e443a2c75"),
                         "SCHEMA_INVALID")

    def test_staging_approval_must_have_all_signed_provenance(self):
        record = {
            "schema": "kmj.main-platform.staging-approval.v1",
            "approvedSha": "b" * 40, "expectedCurrentSha": "a" * 40,
            "expectedProductionRelease": "platform-574e443a2c75",
            "runnerSha256": "c" * 64, "unitSha256": "d" * 64,
            "backupVerified": True, "rollbackVerified": True,
            "storageVerified": True, "zeroAdditionalCostVerified": True,
        }
        self.assertEqual(audit.approval_status(record, "staging",
                                               "platform-574e443a2c75"), "PASS")
        for key, change in (("backupVerified", False),
                            ("zeroAdditionalCostVerified", False)):
            changed = {**record, key: change}
            self.assertEqual(audit.approval_status(changed, "staging",
                                                   "platform-574e443a2c75"),
                             "OWNER_FLAGS_FALSE")
        forged = {**record, "runnerSha256": "z" * 64}
        self.assertEqual(audit.approval_status(forged, "staging",
                                               "platform-574e443a2c75"),
                         "SCHEMA_INVALID")

    def test_duplicate_protected_json_rejected(self):
        with self.assertRaises(ValueError):
            json.loads('{"a":1,"a":2}', object_pairs_hook=audit.unique_pairs)
        with self.assertRaises(ValueError):
            json.loads('{"state":NaN}', parse_constant=audit.reject_constant)

    def test_runtime_ssh_diagnostics_never_emit_journal_raw_values(self):
        payload = "Access denied! TOKEN=SECRET Permission denied (publickey)"
        self.assertEqual(audit.classify_ssh_failure(payload), "PUBLICKEY_AUTH_DENIED")
        self.assertEqual(audit.classify_ssh_failure("Host key verification failed"),
                         "HOSTKEY_MISMATCH")
        with patch.object(audit, "property", side_effect=lambda _u, key: {
            "ExecMainStatus": "255",
            "Result": "exit-code",
            "InvocationID": "a" * 32,
        }.get(key)), patch.object(audit.subprocess, "run", return_value=type("R", (), {
            "returncode": 0, "stdout": payload.encode(),
        })()):
            self.assertEqual(audit.offsite_status(), ("EXIT_255", "PUBLICKEY_AUTH_DENIED"))

    def test_effective_unit_source_hint_distinguishes_reference_not_identity(self):
        fixtures = [
            ("{ path=/usr/local/libexec/kmj-offsite.sh ; argv[]=/usr/local/libexec/kmj-offsite.sh ; }",
             b"#!/bin/sh\n# /etc/kmj-codebridge/offsite-sftp.conf\n",
             "CONFIG_PATH_REFERENCED_ONLY"),
            ("{ path=/usr/local/libexec/kmj-offsite.sh ; argv[]=/usr/local/libexec/kmj-offsite.sh ; }",
             b"#!/bin/sh\nexec rsync remote:backup\n",
             "PINNED_CONFIG_NOT_REFERENCED"),
            ("{ path=/usr/local/libexec/kmj-offsite.sh ; argv[]=/usr/local/libexec/kmj-offsite.sh ; }",
             None, "EXECUTABLE_NOT_ATTESTED"),
        ]
        for raw, content, expected in fixtures:
            with self.subTest(expected=expected), \\
                 patch.object(audit, "property", return_value=raw), \\
                 patch.object(audit, "protected_bytes", return_value=content) as reader:
                self.assertEqual(audit.offsite_unit_source_hint(), expected)
                reader.assert_called_once_with(
                    Path("/usr/local/libexec/kmj-offsite.sh"), 1 << 20
                )

    def test_effective_unit_source_rejects_ambiguous_or_traversal(self):
        for bad in (
            None,
            "foo",
            "{ path=/usr/bin/bash ; path=/usr/bin/env ; }",
            "{ path=/usr/bin/../tmp/malicious.sh ; }",
            "{ path=/tmp/a\\nLEAK=SECRET ; }",
        ):
            with self.subTest(raw=bad), \\
                 patch.object(audit, "property", return_value=bad), \\
                 patch.object(audit, "protected_bytes",
                              side_effect=AssertionError("must not read arbitrary path")):
                self.assertEqual(audit.offsite_unit_source_hint(),
                                 "EXECSTART_NOT_PROVEN")
        self.assertNotIn("SSH_AUTHENTICATED", audit.offsite_unit_source_hint.__doc__ or "")
        self.assertIn("OFFSITE_EFFECTIVE_SSH_IDENTITY", SOURCE.read_text())
        self.assertIn('"NOT_PROVEN"', SOURCE.read_text())

    def test_onepass_does_not_perform_mutations_or_claim_restore(self):
        source = SOURCE.read_text()
        self.assertIn("BACKUP_RESTORE", source)
        self.assertIn("NOT_ATTESTED_BY_READONLY_AUDIT", source)
        self.assertIn("PRODUCTION_MUTATION", source)
        self.assertIn("NONE", source)
        for forbidden in ("subprocess.Popen", "systemctl start", "systemctl restart",
                          "systemctl enable", "systemctl daemon-reload", "os.unlink(",
                          "os.rename(", "os.replace(", "os.chmod(", "os.chown(",
                          "os.symlink(", "os.mkdir(", "write_text(", "write_bytes(",
                          "open(path, \"w", "rm -rf", "sudo "):
            self.assertNotIn(forbidden, source)

    def test_host_and_root_fail_closed_before_inspection(self):
        with patch.object(audit.os, "geteuid", return_value=1000), \
             patch.object(audit.socket, "gethostname", return_value="kmj-elite"), \
             patch.object(audit, "report", side_effect=AssertionError("must not inspect")):
            self.assertEqual(audit.main(["script"]), 2)
        with patch.object(audit.os, "geteuid", return_value=0), \
             patch.object(audit.socket, "gethostname", return_value="wrong-host"), \
             patch.object(audit, "report", side_effect=AssertionError("must not inspect")):
            self.assertEqual(audit.main(["script"]), 2)


if __name__ == "__main__":
    unittest.main()
