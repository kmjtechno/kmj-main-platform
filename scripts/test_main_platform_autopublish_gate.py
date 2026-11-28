#!/usr/bin/env python3
"""Safety regression tests: unattended publication must be gated per SHA."""
import copy
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).parent / "operations" / "main_platform_autopublish_gate.py"
spec = importlib.util.spec_from_file_location("kmj_auto_gate", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
SHA = "a" * 40
OLD = "platform-" + "b" * 12
BASE_APPROVAL = {
    "approvedSha": SHA, "expectedCurrentRelease": OLD,
    "backupVerified": True, "rollbackVerified": True,
}
BASE_EVIDENCE = {
    "schema": "kmj.autopublish.release-admission.v1",
    "approvedSha": SHA, "expectedCurrentRelease": OLD, "stagingSha": SHA,
    "standingOwnerAuthorization": True,
    **{k: True for k in mod.ACCEPTANCE_KEYS},
}
ELITE_EVIDENCE = {
    "schema": "kmj.autopublish.release-admission.elite-local.v2",
    "approvedSha": SHA, "expectedCurrentRelease": OLD, "stagingSha": SHA,
    "standingOwnerAuthorization": True,
    **{k: True for k in mod.ELITE_LOCAL_ACCEPTANCE_KEYS},
}

def verdict(approval=None, evidence=None, live=OLD, remote=SHA, candidate=SHA):
    return mod.decision(
        BASE_APPROVAL if approval is None else approval,
        BASE_EVIDENCE if evidence is None else evidence,
        live, remote, candidate,
    )

class AutoPublishSafetyTest(unittest.TestCase):
    def test_all_independent_gates_exact_sha(self):
        self.assertEqual(verdict(), "READY_APPROVED_RELEASE")

    def test_elite_only_v2_requires_explicit_owner_authorized_local_restore(self):
        # Elite-local promotion can be admitted only after independently
        # witnessed exact candidate PG/uploads restore and backup SHA.
        self.assertEqual(verdict(evidence=ELITE_EVIDENCE),
                         "READY_APPROVED_RELEASE")
        self.assertEqual(verdict(evidence=ELITE_EVIDENCE,
                                 live="platform-" + SHA[:12]), "ALREADY_LIVE")
        for key in mod.ELITE_LOCAL_ACCEPTANCE_KEYS:
            with self.subTest(key=key):
                candidate = dict(ELITE_EVIDENCE, **{key: False})
                self.assertEqual(verdict(evidence=candidate),
                                 "BLOCKED_ACCEPTANCE_EVIDENCE")
                candidate[key] = "true"
                self.assertEqual(verdict(evidence=candidate),
                                 "BLOCKED_ACCEPTANCE_EVIDENCE")
                candidate[key] = None
                self.assertEqual(verdict(evidence=candidate),
                                 "BLOCKED_ACCEPTANCE_EVIDENCE")

    def test_elite_only_v2_never_infers_local_recovery_from_legacy_offsite(self):
        # Do not rename legacy evidence, admit mixed contracts, or manufacture
        # backup/rollback/owner attestations when switching deployment policy.
        old = dict(BASE_EVIDENCE, schema=ELITE_EVIDENCE["schema"])
        new = dict(ELITE_EVIDENCE, schema=BASE_EVIDENCE["schema"])
        self.assertEqual(verdict(evidence=old), "BLOCKED_ACCEPTANCE_SCHEMA")
        self.assertEqual(verdict(evidence=new), "BLOCKED_ACCEPTANCE_SCHEMA")
        for key in ("eliteDisposablePgUploadsRestorePass", "eliteBackupWitnessShaPass"):
            modified = dict(ELITE_EVIDENCE)
            modified.pop(key)
            self.assertEqual(verdict(evidence=modified),
                             "BLOCKED_ACCEPTANCE_SCHEMA")
        modified = dict(ELITE_EVIDENCE, independentOffsiteRestorePass=True)
        self.assertEqual(verdict(evidence=modified), "BLOCKED_ACCEPTANCE_SCHEMA")
        modified = dict(ELITE_EVIDENCE, standingOwnerAuthorization=False)
        self.assertEqual(verdict(evidence=modified), "BLOCKED_OWNER_AUTHORIZATION")
        modified = dict(ELITE_EVIDENCE, extra=True)
        self.assertEqual(verdict(evidence=modified), "BLOCKED_ACCEPTANCE_SCHEMA")
        self.assertEqual(verdict(evidence=ELITE_EVIDENCE,
                                 live="platform-" + "c" * 12),
                         "BLOCKED_CURRENT_RELEASE_DRIFT")
        self.assertEqual(verdict(evidence=ELITE_EVIDENCE,
                                 remote="c" * 40),
                         "BLOCKED_STAGING_APPROVAL_DRIFT")
        self.assertEqual(verdict(evidence=ELITE_EVIDENCE,
                                 candidate="c" * 40),
                         "BLOCKED_CANDIDATE_IDENTITY")
        approval = dict(BASE_APPROVAL, rollbackVerified=False)
        self.assertEqual(verdict(approval=approval, evidence=ELITE_EVIDENCE),
                         "BLOCKED_PROTECTED_APPROVAL")

    def test_noop_when_already_live(self):
        self.assertEqual(verdict(live="platform-" + SHA[:12]), "ALREADY_LIVE")

    def test_already_live_requires_real_owner_evidence(self):
        live = "platform-" + SHA[:12]
        self.assertEqual(verdict(live=live), "ALREADY_LIVE")
        self.assertEqual(verdict(approval={}, live=live),
                         "BLOCKED_APPROVAL_SCHEMA")
        self.assertEqual(verdict(approval=dict(BASE_APPROVAL, backupVerified=False),
                                 live=live), "BLOCKED_PROTECTED_APPROVAL")
        self.assertEqual(verdict(evidence={}, live=live),
                         "BLOCKED_ACCEPTANCE_SCHEMA")
        self.assertEqual(verdict(evidence=dict(BASE_EVIDENCE,
                                             ownerAuthenticatedQaPass=False),
                                 live=live), "BLOCKED_ACCEPTANCE_EVIDENCE")
        self.assertEqual(verdict(evidence=dict(BASE_EVIDENCE,
                                             standingOwnerAuthorization=False),
                                 live=live), "BLOCKED_OWNER_AUTHORIZATION")
        self.assertEqual(verdict(remote="c" * 40, live=live),
                         "BLOCKED_STAGING_APPROVAL_DRIFT")
        self.assertEqual(verdict(candidate="c" * 40, live=live),
                         "BLOCKED_CANDIDATE_IDENTITY")

    def test_already_live_requires_fresh_exact_public_https(self):
        source = SOURCE.read_text()
        self.assertIn("if result == \"ALREADY_LIVE\":", source)
        self.assertIn("exact_https_sha_ok(public_https_response(), target)",
                      source)
        self.assertIn("KMJ_AUTOPUBLISH=BLOCKED_ALREADY_LIVE_HEALTH", source)
        self.assertIn("KMJ_AUTOPUBLISH=ALREADY_LIVE_SHA_VERIFIED", source)
        from unittest.mock import patch
        good = ("HTTP/2 200\r\nx-kmj-deploy-sha: " + SHA +
                "\r\n\r\nKMJ_HTTP_STATUS=200")
        with patch.object(mod, "fixed_run", return_value=good) as fixed:
            self.assertEqual(mod.public_https_response(), good)
        argv = fixed.call_args.args[0]
        self.assertIn("--max-redirs", argv)
        self.assertIn("0", argv)
        self.assertIn("--proto", argv)
        self.assertIn("=https", argv)
        self.assertEqual(argv[-1], mod.URL)
        self.assertTrue(mod.exact_https_sha_ok(good, SHA))
        self.assertFalse(mod.exact_https_sha_ok(good.replace(SHA, "c" * 40), SHA))

    def test_never_publish_without_approval(self):
        self.assertEqual(verdict(approval={}), "BLOCKED_APPROVAL_SCHEMA")
        for key in ("backupVerified", "rollbackVerified"):
            copy_ = dict(BASE_APPROVAL, **{key: "true"})
            self.assertEqual(verdict(approval=copy_), "BLOCKED_PROTECTED_APPROVAL")

    def test_approval_schema_extras_rejected(self):
        copy_ = dict(BASE_APPROVAL, unexpected=True)
        self.assertEqual(verdict(approval=copy_), "BLOCKED_APPROVAL_SCHEMA")

    def test_current_release_race_blocks(self):
        self.assertEqual(verdict(live="platform-" + "c" * 12),
                         "BLOCKED_CURRENT_RELEASE_DRIFT")

    def test_promotion_drift_and_wrong_candidate(self):
        self.assertEqual(verdict(remote="c" * 40),
                         "BLOCKED_STAGING_APPROVAL_DRIFT")
        self.assertEqual(verdict(candidate="c" * 40),
                         "BLOCKED_CANDIDATE_IDENTITY")

    def test_explicit_owner_policy_required(self):
        copy_ = dict(BASE_EVIDENCE, standingOwnerAuthorization=False)
        self.assertEqual(verdict(evidence=copy_), "BLOCKED_OWNER_AUTHORIZATION")
        copy_["standingOwnerAuthorization"] = "true"
        self.assertEqual(verdict(evidence=copy_), "BLOCKED_OWNER_AUTHORIZATION")

    def test_every_acceptance_gate_required(self):
        for gate in mod.ACCEPTANCE_KEYS:
            copy_ = dict(BASE_EVIDENCE, **{gate: False})
            self.assertEqual(verdict(evidence=copy_), "BLOCKED_ACCEPTANCE_EVIDENCE", gate)

    def test_stale_or_spoofed_acceptance_rejected(self):
        for key, bad in (
            ("approvedSha", "c" * 40),
            ("expectedCurrentRelease", "platform-" + "c" * 12),
            ("stagingSha", "c" * 40),
            ("schema", "wrong"),
        ):
            copy_ = dict(BASE_EVIDENCE, **{key: bad})
            self.assertEqual(verdict(evidence=copy_), "BLOCKED_ACCEPTANCE_IDENTITY")
        copy_ = dict(BASE_EVIDENCE, extra="true")
        self.assertEqual(verdict(evidence=copy_), "BLOCKED_ACCEPTANCE_SCHEMA")

    def test_candidate_tracked_drift_blocks_even_with_matching_head(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / ("platform-" + SHA[:12])
            folder.mkdir()
            with patch.object(mod, "RELEASES", Path(temp)), patch.object(
                    mod, "fixed_run", side_effect=[SHA, True, False]) as runner:
                self.assertEqual(mod.candidate_sha(SHA), "")
                self.assertEqual(runner.call_count, 3)
                args = runner.call_args.args[0]
                self.assertIn("diff", args)
                self.assertIn("--no-ext-diff", args)
                self.assertIn("--quiet", args)
                self.assertIn("HEAD", args)
                self.assertNotIn(":(literal,exclude)apps/platform/storage", args)
                self.assertTrue(runner.call_args.kwargs["return_success"])
            with patch.object(mod, "RELEASES", Path(temp)), patch.object(
                    mod, "fixed_run", side_effect=[SHA, True, True, SHA]):
                self.assertEqual(mod.candidate_sha(SHA), SHA)
            with patch.object(mod, "RELEASES", Path(temp)), patch.object(
                    mod, "fixed_run", return_value="c" * 40) as runner:
                self.assertEqual(mod.candidate_sha(SHA), "")
                runner.assert_called_once()

    def test_shared_storage_requires_exact_link_and_clean_index(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            releases = root / "releases"
            folder = releases / ("platform-" + SHA[:12])
            app = folder / "apps/platform"
            app.mkdir(parents=True)
            shared = root / "shared/storage"
            shared.mkdir(parents=True)
            storage = app / "storage"
            storage.symlink_to(shared, target_is_directory=True)
            with patch.object(mod, "RELEASES", releases):
                with patch.object(mod, "fixed_run", side_effect=[SHA, True, True, SHA]) as runner:
                    self.assertEqual(mod.candidate_sha(SHA), SHA)
                    self.assertIn("--cached", runner.call_args_list[1].args[0])
                    self.assertIn(":(literal,exclude)apps/platform/storage",
                                  runner.call_args_list[2].args[0])
                with patch.object(mod, "fixed_run", side_effect=[SHA, False]) as runner:
                    self.assertEqual(mod.candidate_sha(SHA), "")
                    self.assertEqual(runner.call_count, 2)
                with patch.object(mod, "fixed_run", side_effect=[SHA, True, False]):
                    self.assertEqual(mod.candidate_sha(SHA), "")
                with patch.object(mod, "fixed_run", side_effect=[SHA, True, True, "c" * 40]):
                    self.assertEqual(mod.candidate_sha(SHA), "")
                storage.unlink()
                storage.symlink_to(app, target_is_directory=True)
                with patch.object(mod, "fixed_run", side_effect=[SHA, True]):
                    self.assertEqual(mod.candidate_sha(SHA), "")

    def test_real_git_shared_storage_exception_does_not_hide_source_or_index(self):
        import subprocess
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            releases = root / "releases"
            releases.mkdir()
            folder = releases / "fixture"
            app = folder / "apps/platform"
            storage = app / "storage"
            storage.mkdir(parents=True)
            shared = root / "shared/storage"
            shared.mkdir(parents=True)
            (storage / ".gitignore").write_text("*\\n!.gitignore\\n")
            (app / "source.php").write_text("original\\n")

            def git(*args):
                return subprocess.run(["git", "-C", str(folder), *args],
                                      capture_output=True, check=True).stdout

            git("init", "-q")
            git("add", ".")
            git("-c", "user.name=CI", "-c", "user.email=ci@example.invalid",
                "commit", "-qm", "fixture")
            sha = git("rev-parse", "HEAD").decode().strip()
            pinned = releases / ("platform-" + sha[:12])
            folder.rename(pinned)
            folder = pinned
            app = folder / "apps/platform"
            storage = app / "storage"
            (storage / ".gitignore").unlink()
            storage.rmdir()
            storage.symlink_to(shared, target_is_directory=True)

            def runner(argv, timeout=15, return_success=False):
                p = subprocess.run(argv[4:], capture_output=True, check=False)
                return (p.returncode == 0 if return_success else
                        p.stdout.decode().strip() if p.returncode == 0 else "")

            with patch.object(mod, "RELEASES", releases), patch.object(mod, "fixed_run", side_effect=runner):
                self.assertEqual(mod.candidate_sha(sha), sha)
                (app / "source.php").write_text("tampered\\n")
                self.assertEqual(mod.candidate_sha(sha), "")
                (app / "source.php").write_text("original\\n")
                git("add", "-A", "apps/platform/storage")
                self.assertEqual(mod.candidate_sha(sha), "")

    def test_git_diff_command_detects_real_tracked_mutations(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def git(*args):
                return subprocess.run(
                    ["git", "-C", str(root), *args],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    check=False,
                )
            self.assertEqual(git("init", "-q").returncode, 0)
            self.assertEqual(git("-c", "user.name=KMJ CI",
                                 "-c", "user.email=ci@example.invalid",
                                 "commit", "--allow-empty", "-qm", "baseline").returncode, 0)
            tracked = root / "tracked.txt"
            tracked.write_text("safe\\n")
            self.assertEqual(git("add", "tracked.txt").returncode, 0)
            self.assertEqual(git("-c", "user.name=KMJ CI",
                                 "-c", "user.email=ci@example.invalid",
                                 "commit", "-qm", "tracked").returncode, 0)
            diff = ("diff", "--no-ext-diff", "--quiet", "HEAD", "--")
            self.assertEqual(git(*diff).returncode, 0)
            tracked.write_text("modified\\n")
            self.assertNotEqual(git(*diff).returncode, 0)
            self.assertEqual(git("add", "tracked.txt").returncode, 0)
            self.assertNotEqual(git(*diff).returncode, 0)

    def test_postactivation_requires_exact_https_deploy_sha(self):
        good = "HTTP/2 200\r\nx-kmj-deploy-sha: " + SHA + (
            "\r\ncontent-type: text/html\r\n\r\nKMJ_HTTP_STATUS=200")
        self.assertTrue(mod.exact_https_sha_ok(good, SHA))
        for bad in (
            good.replace(SHA, "c" * 40),
            good.replace("HTTP/2 200", "HTTP/2 302"),
            good.replace("KMJ_HTTP_STATUS=200", "KMJ_HTTP_STATUS=404"),
            good.replace("x-kmj-deploy-sha:", "x-other-header:"),
            good.replace("content-type:", "x-kmj-deploy-sha: " + SHA + "\r\ncontent-type:"),
            "HTTP/1.1 200\r\n\r\n" + good,
            "",
        ):
            self.assertFalse(mod.exact_https_sha_ok(bad, SHA))

    def test_protected_release_json_rejects_duplicate_keys_and_nonfinite(self):
        import json
        self.assertEqual(mod.parse_protected_json(json.dumps(BASE_APPROVAL)),
                         BASE_APPROVAL)
        for payload in (
            '{"approvedSha":"a","approvedSha":"b"}',
            '{"nested":{"ownerAuthenticatedQaPass":true,'
            '"ownerAuthenticatedQaPass":false}}',
            '{"backupVerified":NaN}',
            '{"backupVerified":Infinity}',
            '{"backupVerified":-Infinity}',
            '{"backupVerified":1e999}',
            '{"backupVerified":-1e999}',
            '{"nested":{"overflow":1e999}}',
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    mod.parse_protected_json(payload)

    def test_protected_manifest_parent_and_same_fd_required(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "approval.json"
            path.write_text("{}")
            # Explicitly insecure parent regardless of the test runner UID.
            path.parent.chmod(0o777)
            with patch.object(mod.os, "open", side_effect=AssertionError(
                    "untrusted parent must be rejected before opening")):
                self.assertIsNone(mod.protected_json(path))
        source = SOURCE.read_text()
        self.assertIn("os.O_NOFOLLOW", source)
        self.assertIn("os.fstat(fd)", source)
        self.assertIn("os.read(fd, 4097)", source)
        self.assertNotIn("path.read_bytes()", source)

    def test_hardened_systemd_only_translates_fixed_nonroot_git(self):
        from unittest.mock import patch
        git = ["/usr/sbin/runuser", "-u", "kmjprod", "--", "/usr/bin/git",
               "--no-optional-locks", "-C", "/home/kmjprod/releases/platform-" + SHA[:12],
               "rev-parse", "--verify", "HEAD"]
        with patch.dict(mod.os.environ, {}, clear=True):
            self.assertEqual(mod.candidate_git_execution_argv(git), git)
        with patch.dict(mod.os.environ, {"INVOCATION_ID": "fixture"}, clear=True):
            args = mod.candidate_git_execution_argv(git)
            self.assertEqual(args[0], "/usr/bin/systemd-run")
            for option in (
                "--uid=kmjprod", "--gid=kmjprod", "--wait", "--pipe", "--collect",
                "--property=ProtectSystem=strict", "--property=ProtectHome=read-only",
                "--property=NoNewPrivileges=true", "--property=RestrictSUIDSGID=true",
                "--property=CapabilityBoundingSet=", "--property=RuntimeMaxSec=12s",
            ):
                self.assertIn(option, args)
            self.assertEqual(args[args.index("--") + 1:], git[4:])
            for other in (
                ["/usr/bin/git", "ls-remote", mod.REMOTE],
                ["/usr/bin/systemctl", "start", mod.UNIT],
                ["/usr/sbin/runuser", "-u", "kmjprod", "--", "/bin/sh"],
            ):
                self.assertEqual(mod.candidate_git_execution_argv(other), other)

    def test_transient_git_failure_never_retries_or_passes(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        git = ["/usr/sbin/runuser", "-u", "kmjprod", "--", "/usr/bin/git",
               "rev-parse", "--verify", "HEAD"]
        with patch.dict(mod.os.environ, {"INVOCATION_ID": "fixture"}, clear=True):
            with patch.object(mod.subprocess, "run", return_value=SimpleNamespace(
                    returncode=1, stdout=SHA)) as run:
                self.assertEqual(mod.fixed_run(git), "")
                run.assert_called_once()
                self.assertEqual(run.call_args.args[0][0], "/usr/bin/systemd-run")
            with patch.object(mod.subprocess, "run", side_effect=OSError) as run:
                self.assertFalse(mod.fixed_run(git, return_success=True))
                run.assert_called_once()

    def test_systemctl_exit_code_cannot_be_ignored(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        with patch.object(mod.subprocess, "run", return_value=SimpleNamespace(
                returncode=1, stdout="")):
            self.assertFalse(mod.fixed_run(["/usr/bin/systemctl", "start",
                                            mod.UNIT], return_success=True))
        with patch.object(mod.subprocess, "run", return_value=SimpleNamespace(
                returncode=0, stdout="")):
            self.assertTrue(mod.fixed_run(["/usr/bin/systemctl", "start",
                                           mod.UNIT], return_success=True))

    def test_fixed_unit_no_arbitrary_commands_or_bypass(self):
        source = SOURCE.read_text()
        self.assertIn("kmj-main-platform-production-release.service", source)
        self.assertIn("https://kmjtechno.com/login", source)
        self.assertIn('"--activate"', source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.system(", source)
        self.assertNotIn("os.symlink(", source)
        self.assertNotIn("os.replace(", source)
        self.assertNotIn("write_text(", source)

if __name__ == "__main__":
    unittest.main()
