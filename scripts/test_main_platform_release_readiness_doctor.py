"""Behavioral + contract tests: exact recovery script and read-only readiness doctor."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOCTOR = REPO / "scripts/operations/main-platform-release-readiness-doctor.py"
RECOVERY = REPO / "scripts/operations/prepare-main-platform-local-recovery-exact.sh"

spec = importlib.util.spec_from_file_location("kmj_release_readiness_doctor", DOCTOR)
doctor = importlib.util.module_from_spec(spec)
sys.modules["kmj_release_readiness_doctor"] = doctor
spec.loader.exec_module(doctor)


def git(cwd: Path, *args: str) -> str:
    env = {"PATH": "/usr/bin:/bin", "HOME": str(cwd), "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True, env=env).stdout.strip()


class ReadinessDoctorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.paths = doctor.Paths(
            root=base / "home",
            approval=base / "etc/approval.json",
            backups=base / "backups",
            controller=base / "libexec/activate.py",
            unit=base / "systemd/release.service",
        )
        releases = self.paths.root / "releases"
        (releases / "platform-aaaaaaaaaaaa").mkdir(parents=True)
        os.symlink("releases/platform-aaaaaaaaaaaa", self.paths.root / "current")
        # Real git candidate with the required built artifacts committed.
        work = base / "work"
        work.mkdir()
        git(work, "init", "-q")
        git(work, "config", "user.email", "t@example.invalid")
        git(work, "config", "user.name", "t")
        for item in doctor.ARTIFACTS:
            file = work / item
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("x")
        (work / ".gitignore").write_text("apps/platform/.env\n")
        git(work, "add", "-A")
        git(work, "commit", "-q", "-m", "c")
        self.sha = git(work, "rev-parse", "HEAD")
        self.candidate = releases / f"platform-{self.sha[:12]}"
        os.rename(work, self.candidate)
        for path in (self.paths.approval, self.paths.controller, self.paths.unit):
            path.parent.mkdir(parents=True, exist_ok=True)
        self.paths.backups.mkdir()
        self.paths.controller.write_text("#")
        self.env = self.candidate / "apps/platform/.env"
        self.paths.unit.write_text("[Unit]")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_backup(self, current="platform-aaaaaaaaaaaa", corrupt=False) -> None:
        archive = self.paths.backups / f"pre-deploy-{self.sha[:12]}.tar.gz"
        archive.write_bytes(b"bundle")
        digest = hashlib.sha256(b"bundle" if not corrupt else b"other").hexdigest()
        (self.paths.backups / f"pre-deploy-{self.sha[:12]}.json").write_text(json.dumps(
            {"approvedSha": self.sha, "currentRelease": current, "backupSha256": digest}))
        for item in self.paths.backups.iterdir():
            item.chmod(0o600)

    def write_approval(self, **overrides) -> None:
        data = {"approvedSha": self.sha, "expectedCurrentRelease": "platform-aaaaaaaaaaaa",
                "backupVerified": True, "rollbackVerified": True, **overrides}
        self.paths.approval.write_text(json.dumps(data))
        self.paths.approval.chmod(0o600)

    def materialize(self) -> None:
        self.env.write_text("APP_KEY=test")
        self.env.chmod(0o600)

    def run_doctor(self):
        return doctor.evaluate(self.sha, self.paths, require_root=False)

    def test_fully_prepared_release_is_ready(self) -> None:
        self.materialize()
        self.write_backup()
        self.write_approval()
        lines, blockers = self.run_doctor()
        self.assertEqual(blockers, [], lines)
        self.assertIn("RELEASE_READINESS=READY_TO_ACTIVATE", lines)
        self.assertIn("PRODUCTION_CHANGED=NO", lines)

    def test_stale_approval_like_live_kmj_elite_is_reported(self) -> None:
        self.materialize()
        self.write_backup()
        self.write_approval(expectedCurrentRelease="platform-bbbbbbbbbbbb")
        _, blockers = self.run_doctor()
        self.assertEqual(blockers, ["APPROVAL_STALE_EXPECTED_CURRENT"])

    def test_missing_owner_artifacts_are_all_listed(self) -> None:
        _, blockers = self.run_doctor()
        self.assertIn("BACKUP_WITNESS_MISSING", blockers)
        self.assertIn("APPROVAL_MISSING", blockers)

    def test_flags_false_and_checksum_mismatch_block(self) -> None:
        self.materialize()
        self.write_backup(corrupt=True)
        self.write_approval(rollbackVerified=False)
        _, blockers = self.run_doctor()
        self.assertIn("BACKUP_CHECKSUM_MISMATCH", blockers)
        self.assertIn("APPROVAL_FLAGS_NOT_TRUE", blockers)

    def test_witness_for_other_current_release_blocks(self) -> None:
        self.materialize()
        self.write_backup(current="platform-cccccccccccc")
        self.write_approval()
        _, blockers = self.run_doctor()
        self.assertEqual(blockers, ["BACKUP_WITNESS_MISMATCH"])

    def test_dirty_candidate_blocks(self) -> None:
        self.materialize()
        self.write_backup()
        self.write_approval()
        (self.candidate / "apps/platform/untracked.txt").write_text("x")
        _, blockers = self.run_doctor()
        self.assertEqual(blockers, ["CANDIDATE_DIRTY"])

    def test_unmaterialized_candidate_blocks_before_health_rollback(self) -> None:
        self.write_backup()
        self.write_approval()
        _, blockers = self.run_doctor()
        self.assertEqual(blockers, ["CANDIDATE_RUNTIME_ENV_MISSING"])

    def test_writable_approval_blocks(self) -> None:
        self.materialize()
        self.write_backup()
        self.write_approval()
        self.paths.approval.chmod(0o666)
        _, blockers = self.run_doctor()
        self.assertEqual(blockers, ["APPROVAL_GROUP_OR_WORLD_WRITABLE"])

    def test_duplicate_protected_backup_witness_fails_closed(self) -> None:
        self.materialize()
        self.write_backup()
        self.write_approval()
        witness = self.paths.backups / f"pre-deploy-{self.sha[:12]}.json"
        data = witness.read_text()
        witness.write_text(data.replace('"approvedSha":', '"approvedSha": "forged", "approvedSha":', 1))
        witness.chmod(0o600)
        lines, blockers = self.run_doctor()
        self.assertIn("BACKUP_WITNESS_MISMATCH", blockers)
        self.assertNotIn("RELEASE_READINESS=READY_TO_ACTIVATE", lines)

    def test_duplicate_or_nonfinite_approval_fails_closed(self) -> None:
        self.materialize()
        self.write_backup()
        self.write_approval()
        valid = self.paths.approval.read_text()
        cases = (
            valid.replace('"backupVerified":', '"backupVerified": false, "backupVerified":', 1),
            valid.replace('"rollbackVerified": true', '"rollbackVerified": NaN'),
            valid.replace('"rollbackVerified": true', '"rollbackVerified": Infinity'),
        )
        for payload in cases:
            with self.subTest(payload=payload):
                self.paths.approval.write_text(payload)
                self.paths.approval.chmod(0o600)
                lines, blockers = self.run_doctor()
                self.assertIn("APPROVAL_SCHEMA_INVALID", blockers)
                self.assertNotIn("RELEASE_READINESS=READY_TO_ACTIVATE", lines)

    def test_protected_json_overflow_exponents_fail_closed(self) -> None:
        self.write_approval()
        for payload in ('{"number":1e999}', '{"number":-1e999}',
                        '{"nested":{"number":1e999}}'):
            with self.subTest(payload=payload):
                self.paths.approval.write_text(payload)
                self.paths.approval.chmod(0o600)
                self.assertIsNone(doctor._load_protected_json(
                    self.paths.approval, False))

    def test_protected_json_symlink_swap_after_precheck_is_denied(self) -> None:
        from unittest.mock import patch

        self.write_approval()
        self.assertIsNone(doctor._protected(self.paths.approval, False))
        replacement = self.paths.approval.with_name("swapped.json")
        original_open = os.open

        def swap_at_open(path, *args, **kwargs):
            if Path(path) == self.paths.approval:
                os.rename(self.paths.approval, replacement)
                os.symlink(replacement, self.paths.approval)
            return original_open(path, *args, **kwargs)

        with patch.object(doctor.os, "open", side_effect=swap_at_open):
            self.assertIsNone(doctor._load_protected_json(self.paths.approval, False))

    def test_protected_json_same_inode_change_after_fd_stat_is_denied(self) -> None:
        from unittest.mock import patch

        self.write_approval()
        original_lstat = os.lstat
        calls = 0

        def mutate_before_final_lstat(path, *args, **kwargs):
            nonlocal calls
            if Path(path) == self.paths.approval:
                calls += 1
                if calls == 2:
                    # The file remains the same inode but changes after
                    # fstat(fd); checking only dev/inode at the path misses it.
                    current = self.paths.approval.read_text()
                    self.assertIn('"rollbackVerified": true', current)
                    self.paths.approval.write_text(
                        current.replace('"rollbackVerified": true',
                                        '"rollbackVerified": false'))
            return original_lstat(path, *args, **kwargs)

        with patch.object(doctor.os, "lstat", side_effect=mutate_before_final_lstat):
            self.assertIsNone(doctor._load_protected_json(self.paths.approval, False))
        self.assertEqual(calls, 2)

    def test_nginx_unreadable_public_blocks_like_live_rollback(self) -> None:
        self.materialize()
        self.write_backup()
        self.write_approval()
        _, blockers = doctor.evaluate(self.sha, self.paths, False, web_read=lambda p: False)
        self.assertEqual(blockers, ["CANDIDATE_NGINX_UNREADABLE"])
        _, blockers = doctor.evaluate(self.sha, self.paths, False, web_read=lambda p: True)
        self.assertEqual(blockers, ["CANDIDATE_NGINX_ENV_EXPOSED"])
        lines, blockers = doctor.evaluate(
            self.sha, self.paths, False, web_read=lambda p: not str(p).endswith(".env"))
        self.assertEqual(blockers, [])
        self.assertIn("CANDIDATE_NGINX_ACCESS=PASS", lines)

    def test_already_live_and_invalid_target(self) -> None:
        os.unlink(self.paths.root / "current")
        os.symlink(f"releases/platform-{self.sha[:12]}", self.paths.root / "current")
        lines, blockers = self.run_doctor()
        self.assertEqual(blockers, [])
        self.assertIn("RELEASE_READINESS=ALREADY_LIVE", lines)
        self.assertEqual(doctor.evaluate("nope", self.paths, False)[1], ["TARGET_SHA_INVALID"])

    def test_doctor_source_never_mutates_production(self) -> None:
        source = DOCTOR.read_text()
        for forbidden in ("os.replace", "os.symlink", "systemctl", ".write_text", "open(\"w",
                          "unlink", "rmtree", "chmod", "chown"):
            self.assertNotIn(forbidden, source, forbidden)


MATERIALIZE = REPO / "scripts/operations/materialize-main-platform-candidate-runtime.sh"


class MaterializeContractTest(unittest.TestCase):
    source = MATERIALIZE.read_text()

    def test_privileged_bootstrap_rejects_inherited_shell_hooks(self) -> None:
        self.assertTrue(self.source.startswith("#!/bin/bash -p\n"))
        self.assertIn("export PATH=/usr/sbin:/usr/bin:/sbin:/bin", self.source)
        self.assertIn("unset BASH_ENV ENV CDPATH", self.source)
        self.assertIn("fail PRIVILEGED_BASH_REQUIRED", self.source)
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "injected"
            hook = Path(tmp) / "hook.sh"
            hook.write_text(f"touch {marker}\n")
            fake_bash = Path(tmp) / "bash"
            fake_bash.write_text(f"#!/bin/sh\ntouch {marker}\nexit 99\n")
            fake_bash.chmod(0o755)
            env = os.environ.copy()
            env.update({"PATH": f"{tmp}:/usr/bin:/bin", "BASH_ENV": str(hook)})
            direct = subprocess.run([str(MATERIALIZE)], env=env,
                                    capture_output=True, text=True)
            self.assertEqual(direct.returncode, 2, direct.stderr)
            self.assertIn("EXACT_SHA_AND_CURRENT_RELEASE_REQUIRED", direct.stdout)
            self.assertFalse(marker.exists(), "privileged shebang must ignore PATH and BASH_ENV")
            plain = subprocess.run(["/bin/bash", str(MATERIALIZE)],
                                   env={"PATH": "/usr/bin:/bin"},
                                   capture_output=True, text=True)
            self.assertEqual(plain.returncode, 2)
            self.assertIn("PRIVILEGED_BASH_REQUIRED", plain.stdout)


    def test_argument_guards_run_before_host_access(self) -> None:
        sha = "8e1a4973204e58050c794eec1ec3b8178b15dd33"
        for args, code in {
            (): "EXACT_SHA_AND_CURRENT_RELEASE_REQUIRED",
            ("x", "platform-8070dad72c55"): "EXACT_SHA_REQUIRED",
            (sha, "live"): "EXPECTED_CURRENT_RELEASE_INVALID",
            (sha, "platform-8e1a4973204e"): "TARGET_ALREADY_CURRENT",
            (sha, "platform-8070dad72c55"): "WRONG_HOST",
        }.items():
            result = subprocess.run(["/bin/bash", "-p", str(MATERIALIZE), *args], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("KMJ_MATERIALIZE=BLOCKED " + code, result.stdout)

    def test_materializer_requires_real_shared_storage_not_copy(self) -> None:
        # The CodeBridge production controller accepts only one persistent
        # storage path OUTSIDE release dirs and byte-identical runtime config.
        required = (
            'readonly SHARED="$ROOT/shared/storage"',
            'fail LIVE_STORAGE_NOT_SHARED',
            'fail CANDIDATE_STORAGE_NOT_SHARED',
            'fail SHARED_STORAGE_MOVING_TARGET',
            'status STORAGE_MODE VERIFIED_SHARED',
            "KMJ_MATERIALIZE_SHARED=PASS",
            "STORAGE_WRITER_QUIESCENCE NOT_ATTESTED",
            'status RUNTIME_ENV BYTE_IDENTICAL',
            'fail ENV_SHA_MISMATCH',
            'fs_op create-env "$LIVE_APP" "$CAND_APP"',
            'setfacl -R -m \'u:www-data:rX\'',
            "NGINX_PRIVATE_ENV_EXPOSED",
            "PRODUCTION_SWITCH NOT_ATTEMPTED",
            "CANDIDATE_DIRTY_AFTER",
            "flock -n 9",
        )
        for token in required:
            self.assertIn(token, self.source, token)
        forbidden = (
            'cp -a --no-clobber',
            'PINNED_IN_CANDIDATE_ONLY',
            '>>"$CAND_APP/.env"',
            'STORAGE_PARITY_MISMATCH',
            'SOURCE_STORAGE_CHANGED_DURING_COPY',
            "artisan migrate",
            "systemctl",
            "mv ",
            "rm -",
            "ln -sfn",
            '>>"$LIVE_APP',
            'main-platform-production-release.json',
            "backupVerified",
            "psql",
            "pg_dump",
            "sed -i",
        )
        for token in forbidden:
            self.assertNotIn(token, self.source, token)

    def test_no_upload_copy_and_explicit_preflight_before_sandbox(self) -> None:
        self.assertLess(self.source.index('fail LIVE_STORAGE_NOT_SHARED'),
                        self.source.index('systemd-run --quiet'))
        self.assertLess(self.source.index('fail CANDIDATE_STORAGE_NOT_SHARED'),
                        self.source.index('systemd-run --quiet'))
        self.assertNotIn('cp -a --no-clobber', self.source)
        self.assertIn(":(exclude)apps/platform/storage", self.source)


class ExactRecoveryContractTest(unittest.TestCase):
    source = RECOVERY.read_text()

    def run_script(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(RECOVERY), *args], capture_output=True, text=True)

    def test_requires_exact_owner_inputs_before_any_host_action(self) -> None:
        sha = "8e1a4973204e58050c794eec1ec3b8178b15dd33"
        cases = {
            (): "EXACT_SHA_AND_CURRENT_RELEASE_REQUIRED",
            ("main", "platform-8070dad72c55"): "EXACT_SHA_REQUIRED",
            (sha, "current"): "EXPECTED_CURRENT_RELEASE_INVALID",
            (sha, "platform-8e1a4973204e"): "TARGET_ALREADY_CURRENT",
        }
        for args, code in cases.items():
            result = self.run_script(*args)
            self.assertEqual(result.returncode, 2)
            self.assertIn("KMJ_LOCAL_RECOVERY=BLOCKED " + code, result.stdout)

    def test_no_hardcoded_release_and_same_safety_contract(self) -> None:
        for stale in ("8070dad72c55", "54142f844c0b"):
            self.assertNotIn(stale, self.source)
        for token in ('[[ "$OLD_NAME" == "$EXPECTED_CURRENT" ]]', "--auth-host=reject",
                      "listen_addresses=''", "--exit-on-error", "O_EXCL", "O_NOFOLLOW",
                      "OFFSITE_INDEPENDENT_RESTORE NOT_VERIFIED", "ROLLBACK_DRILL NOT_VERIFIED",
                      "PRODUCTION_SWITCH NOT_ATTEMPTED", "APPROVAL_UPDATED NO"):
            self.assertIn(token, self.source)
        for forbidden in ("systemctl restart", "systemctl reload", "artisan migrate", "ln -s",
                          "git reset", "backupVerified", "rollbackVerified",
                          "/etc/kmj-codebridge/main-platform-production-release.json"):
            self.assertNotIn(forbidden, self.source)
        self.assertLess(self.source.index("LOCAL_DISPOSABLE_POSTGRES_RESTORE PASS"),
                        self.source.index("os.O_WRONLY | os.O_CREAT | os.O_EXCL"))



STORAGE_VERIFIER = REPO / "scripts/operations/verify-main-platform-storage-manifest.py"
storage_spec = importlib.util.spec_from_file_location("kmj_storage_manifest", STORAGE_VERIFIER)
storage_manifest = importlib.util.module_from_spec(storage_spec)
sys.modules["kmj_storage_manifest"] = storage_manifest
storage_spec.loader.exec_module(storage_manifest)


class StorageContentParityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.source = root / "source"
        self.copy = root / "copy"
        self.source.mkdir()
        (self.source / "artwork.bin").write_bytes(b"ABCD")
        (self.source / "sub").mkdir()
        (self.source / "sub/data.txt").write_bytes(b"one")
        (self.source / ".gitignore").write_text("old placeholder")
        os.symlink("../artwork.bin", self.source / "sub/artwork-link")
        shutil.copytree(self.source, self.copy, symlinks=True, copy_function=shutil.copy2)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def manifests(self):
        return storage_manifest.inventory(self.source), storage_manifest.inventory(self.copy)

    def test_identical_file_bytes_metadata_and_raw_symlinks_match(self) -> None:
        left, right = self.manifests()
        self.assertEqual(left, right)
        self.assertEqual(left["regular"], 2)
        self.assertEqual(left["symlinks"], 1)
        self.assertEqual(len(left["sha256"]), 64)

    def test_equal_size_different_content_is_rejected(self) -> None:
        (self.copy / "artwork.bin").write_bytes(b"WXYZ")
        left, right = self.manifests()
        self.assertNotEqual(left["sha256"], right["sha256"])

    def test_raw_symlink_retarget_is_rejected_without_following_it(self) -> None:
        link = self.copy / "sub/artwork-link"
        link.unlink()
        os.symlink("/etc/passwd", link)
        left, right = self.manifests()
        self.assertNotEqual(left["sha256"], right["sha256"])

    def test_metadata_drift_is_rejected(self) -> None:
        (self.copy / "artwork.bin").chmod(0o600)
        self.assertNotEqual(*self.manifests())

    def test_regular_gitignore_placeholder_is_excluded(self) -> None:
        (self.copy / ".gitignore").write_text("new placeholder")
        self.assertEqual(*self.manifests())

    def test_special_files_and_symlinked_roots_fail_closed(self) -> None:
        os.mkfifo(self.source / "unexpected.pipe")
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_STORAGE_ENTRY"):
            storage_manifest.inventory(self.source)
        with self.assertRaisesRegex(ValueError, "STORAGE_ROOT_NOT_REAL_DIRECTORY"):
            storage_manifest.inventory(self.copy / "sub/artwork-link")

    def test_materialize_uses_stable_shared_storage_with_no_quiescence_claim(self) -> None:
        source = MATERIALIZE.read_text()
        for token in ("source_before=", "source_after=",
                      "SHARED_STORAGE_MOVING_TARGET",
                      "STORAGE_MODE VERIFIED_SHARED",
                      "STORAGE_WRITER_QUIESCENCE NOT_ATTESTED"):
            self.assertIn(token, source)
        self.assertNotIn("candidate_after=", source)
        self.assertNotIn("STORAGE_PARITY_MISMATCH", source)
        self.assertNotIn("cp -a --no-clobber", source)
        self.assertNotIn("find . -type f ! -name .gitignore", source)



class TrustedMaterializeVerifierTest(unittest.TestCase):
    def test_root_verifier_ignores_candidate_and_python_path_code(self):
        source = MATERIALIZE.read_text()
        self.assertNotIn('"$STORAGE_VERIFIER"', source)
        self.assertIn('/usr/bin/python3 -I -S - "$1"', source)
        begin = source.index("storage_manifest() {")
        marker = "KMJ_STORAGE_MANIFEST_PY\n}"
        end = source.index(marker, begin) + len(marker)
        function = source[begin:end]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "data/payload").write_bytes(b"actual bytes")
            (root / "hashlib.py").write_text("raise RuntimeError('UNTRUSTED_IMPORT')")
            (root / "sitecustomize.py").write_text("raise RuntimeError('UNTRUSTED_SITE')")
            run = subprocess.run(
                ["/bin/bash", "-c", function + '\n storage_manifest "$1"', "test", str(root / "data")],
                cwd=root, env={**os.environ, "PYTHONPATH": directory},
                capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["regular"], 1)


class MaterializeWriteBoundaryTest(unittest.TestCase):
    def test_runtime_writes_require_nonroot_private_mount_namespace(self):
        source = MATERIALIZE.read_text()
        boundary = source.index("KMJ_UNPRIVILEGED_MATERIALIZE'")
        self.assertLess(source.index("flock -n 9"), boundary)
        for token in ("-p User=kmjprod", "-p ProtectSystem=strict",
                      '-p "ReadWritePaths=$CAND"', '-p "ReadOnlyPaths=$LIVE_APP"',
                      "-p NoNewPrivileges=yes", "-p PrivateTmp=yes",
                      "SANDBOX_USER_MISMATCH", "export GIT_OPTIONAL_LOCKS=0"):
            self.assertIn(token, source)
        self.assertGreater(source.index('fs_op create-env "$LIVE_APP"'), boundary)
        self.assertNotIn("install -o kmjprod", source)
        # Runtime upload copying is forbidden; only byte-identical .env copy and
        # ACL preparation remain inside the nonroot sandbox.
        self.assertNotIn('cp -a --no-clobber', source)
        self.assertGreater(source.index('status STORAGE_MODE VERIFIED_SHARED'), boundary)
        self.assertLess(source.index("KMJ_UNPRIVILEGED_MATERIALIZE\n"), source.index("runuser -u www-data -- test"))
        self.assertNotIn("--system", source)
        self.assertNotIn("sudo", source)


class MaterializeRollbackTest(unittest.TestCase):
    """Candidate-only, inode-attested creation and rollback of .env + public link."""
    source = MATERIALIZE.read_text()

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.live = root / "live"
        self.cand = root / "cand"
        for d in (self.live, self.cand / "public"):
            d.mkdir(parents=True)
        (self.live / ".env").write_bytes(b"APP_KEY=base64:abc\nDB=x\n")
        (self.live / ".env").chmod(0o640)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def harness(self, tail: str, source_override: str | None = None) -> subprocess.CompletedProcess:
        source = self.source if source_override is None else source_override
        begin = source.index("# Descriptor-anchored")
        end = source.index("trap on_exit EXIT") + len("trap on_exit EXIT")
        script = (
            "set -Eeuo pipefail\n"
            "status() { printf '%s=%s\\n' \"$1\" \"$2\"; }\n"
            "fail() { echo \"BLOCKED $1\"; exit 2; }\n"
            f"CAND_APP={self.cand}; LIVE_APP={self.live}; MODE=materialize\n"
            "ROLLBACK_ENV_ID=''; ROLLBACK_LINK_ID=''\n"
            + source[begin:end] + "\n" + tail
        )
        return subprocess.run(["/bin/bash", "-c", script], capture_output=True, text=True,
                              env={"PATH": "/usr/bin:/bin"}, timeout=30)

    CREATE = (
        'env_id="$(fs_op create-env "$LIVE_APP" "$CAND_APP")" '
        '|| { receipt_uncertain=1; fail ENV_CREATE_FAILED; }\n'
        'link_id="$(fs_op create-link "$CAND_APP/public")" '
        '|| { receipt_uncertain=1; fail LINK_CREATE_FAILED; }\n'
    )

    def test_forced_failure_after_creation_removes_only_candidate_artifacts(self) -> None:
        run = self.harness(self.CREATE + "fail FORCED_LATE_FAILURE\n")
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertIn("CANDIDATE_ROLLBACK=DONE", run.stdout)
        self.assertFalse((self.cand / ".env").exists())
        self.assertFalse((self.cand / "public/storage").is_symlink())
        self.assertEqual((self.live / ".env").read_bytes(), b"APP_KEY=base64:abc\nDB=x\n")

    def test_retry_after_rollback_is_not_blocked(self) -> None:
        self.harness(self.CREATE + "fail FORCED_LATE_FAILURE\n")
        run = self.harness(self.CREATE + "committed=1\n")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        env = self.cand / ".env"
        self.assertEqual(env.read_bytes(), (self.live / ".env").read_bytes())
        self.assertEqual(env.stat().st_mode & 0o777, 0o600)
        self.assertEqual(os.readlink(self.cand / "public/storage"), "../storage/app/public")

    def test_committed_success_keeps_artifacts(self) -> None:
        run = self.harness(self.CREATE + "committed=1\n")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertTrue((self.cand / ".env").is_file())
        self.assertNotIn("CANDIDATE_ROLLBACK", run.stdout)

    def test_replaced_artifact_is_left_for_review_not_deleted(self) -> None:
        swap = (
            'rm_env="$CAND_APP/.env"\n'
            "python3 -c \"import os,sys; p=sys.argv[1]; os.link(p, p + '.keep'); os.unlink(p); open(p,'w').write('FOREIGN')\" \"$rm_env\"\n"
            "fail FORCED_LATE_FAILURE\n"
        )
        run = self.harness(self.CREATE + swap)
        self.assertEqual(run.returncode, 2)
        self.assertIn("CANDIDATE_ROLLBACK=FAILED_REVIEW", run.stdout)
        self.assertEqual((self.cand / ".env").read_text(), "FOREIGN")

    def test_preplanted_env_symlink_is_never_followed_or_truncated(self) -> None:
        victim = Path(self.tmp.name) / "victim"
        victim.write_text("precious")
        (self.cand / ".env").symlink_to(victim)
        run = self.harness(self.CREATE)
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(victim.read_text(), "precious")
        self.assertTrue((self.cand / ".env").is_symlink())

    def test_raced_existing_env_is_not_overwritten_or_removed(self) -> None:
        (self.cand / ".env").write_text("RACED")
        run = self.harness(self.CREATE)
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual((self.cand / ".env").read_text(), "RACED")

    def test_existing_public_link_is_not_clobbered(self) -> None:
        (self.cand / "public/storage").symlink_to("elsewhere")
        run = self.harness(self.CREATE)
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(os.readlink(self.cand / "public/storage"), "elsewhere")
        self.assertFalse((self.cand / ".env").exists(), "env created in the same run is rolled back")

    def test_failure_before_receipt_delivery_self_cleans(self) -> None:
        # Parent closes the pipe before the id can be delivered.
        run = self.harness('fs_op create-env "$LIVE_APP" "$CAND_APP" >&- || true\n'
                           'fs_op create-link "$CAND_APP/public" >&- || true\n')
        self.assertFalse((self.cand / ".env").exists(), run.stdout + run.stderr)
        self.assertFalse((self.cand / "public/storage").is_symlink())

    def test_link_created_but_inode_receipt_fails_requires_owner_review(self) -> None:
        # Inject a failure after symlink(2) succeeds, before lstat returns its
        # inode id. The link MUST NOT be removed based only on its pathname.
        needle = '            info = os.stat("storage", dir_fd=pub, follow_symlinks=False)'
        self.assertEqual(self.source.count(needle), 1)
        fault = self.source.replace(
            needle,
            '            raise OSError("INJECTED_LINK_RECEIPT_FAILURE")\n' + needle,
        )
        run = self.harness(self.CREATE, source_override=fault)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("FS_OP_POST_CREATE_RECEIPT=UNATTESTED_OWNER_REVIEW", run.stderr)
        self.assertIn("CANDIDATE_ROLLBACK=FAILED_REVIEW", run.stdout)
        self.assertFalse((self.cand / ".env").exists())
        self.assertTrue((self.cand / "public/storage").is_symlink())
        self.assertEqual(os.readlink(self.cand / "public/storage"),
                         "../storage/app/public")

    def test_env_created_but_inode_receipt_fails_requires_owner_review(self) -> None:
        # Even an O_EXCL-created file cannot be blindly removed when fstat
        # fails before its inode receipt; keep it for the privileged review.
        needle = '            created = ident(os.fstat(dst))'
        self.assertEqual(self.source.count(needle), 1)
        fault = self.source.replace(
            needle,
            '            raise OSError("INJECTED_ENV_RECEIPT_FAILURE")\n' + needle,
        )
        run = self.harness(self.CREATE, source_override=fault)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("FS_OP_POST_CREATE_RECEIPT=UNATTESTED_OWNER_REVIEW", run.stderr)
        self.assertIn("CANDIDATE_ROLLBACK=FAILED_REVIEW", run.stdout)
        # os.open(O_EXCL) created an empty candidate before its fstat failed.
        # Without a receipt it must be LEFT FOR REVIEW, not mistaken for a
        # successfully copied or rolled-back runtime secret.
        self.assertEqual((self.cand / ".env").read_bytes(), b"")
        self.assertEqual((self.live / ".env").read_bytes(),
                         b"APP_KEY=base64:abc\nDB=x\n")
        self.assertFalse((self.cand / "public/storage").is_symlink())

    def test_malformed_env_receipt_never_claims_rollback_done(self) -> None:
        # A successful O_EXCL write may have created a secret file even if
        # the emitted receipt is malformed. It cannot be unlinked by pathname.
        needle = '        sys.stdout.write(created + "\\n")'
        self.assertEqual(self.source.count(needle), 1)
        fault = self.source.replace(
            needle,
            '        sys.stdout.write("BROKEN_ID\\n")',
        )
        tail = (
            'env_id="$(fs_op create-env "$LIVE_APP" "$CAND_APP")" '
            '|| { receipt_uncertain=1; fail ENV_CREATE_FAILED; }\n'
            '[[ "$env_id" =~ ^[0-9]+:[0-9]+$ ]] '
            '|| { env_id=""; receipt_uncertain=1; fail ENV_CREATE_FAILED; }\n'
        )
        run = self.harness(tail, source_override=fault)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("CANDIDATE_ROLLBACK=FAILED_REVIEW", run.stdout)
        self.assertNotIn("CANDIDATE_ROLLBACK=DONE", run.stdout)
        self.assertEqual((self.cand / ".env").read_bytes(),
                         (self.live / ".env").read_bytes())
        self.assertFalse((self.cand / "public/storage").is_symlink())

    def test_malformed_link_receipt_never_deletes_unattested_link(self) -> None:
        needle = '        emit(created, None, pub, "storage", "l")'
        self.assertEqual(self.source.count(needle), 1)
        fault = self.source.replace(needle, '        print("BROKEN_LINK_ID")')
        tail = (
            'env_id="$(fs_op create-env "$LIVE_APP" "$CAND_APP")" '
            '|| { receipt_uncertain=1; fail ENV_CREATE_FAILED; }\n'
            '[[ "$env_id" =~ ^[0-9]+:[0-9]+$ ]] '
            '|| { env_id=""; receipt_uncertain=1; fail ENV_CREATE_FAILED; }\n'
            'link_id="$(fs_op create-link "$CAND_APP/public")" '
            '|| { receipt_uncertain=1; fail LINK_CREATE_FAILED; }\n'
            '[[ "$link_id" =~ ^[0-9]+:[0-9]+$ ]] '
            '|| { link_id=""; receipt_uncertain=1; fail LINK_CREATE_FAILED; }\n'
        )
        run = self.harness(tail, source_override=fault)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("CANDIDATE_ROLLBACK=FAILED_REVIEW", run.stdout)
        self.assertNotIn("CANDIDATE_ROLLBACK=DONE", run.stdout)
        self.assertFalse((self.cand / ".env").exists())
        self.assertEqual(os.readlink(self.cand / "public/storage"),
                         "../storage/app/public")

    def test_unknown_rollback_receipt_returns_nonzero(self) -> None:
        run = self.harness('receipt_uncertain=1\nrollback_candidate\n')
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("CANDIDATE_ROLLBACK=FAILED_REVIEW", run.stdout)
        self.assertNotIn("CANDIDATE_ROLLBACK=DONE", run.stdout)

    def test_sigterm_after_creation_rolls_back(self) -> None:
        run = self.harness(self.CREATE + "kill -TERM $$\nsleep 5\n")
        self.assertEqual(run.returncode, 143, run.stdout + run.stderr)
        self.assertFalse((self.cand / ".env").exists())
        self.assertFalse((self.cand / "public/storage").is_symlink())

    def test_root_receipt_never_uses_a_temp_pathname(self) -> None:
        source = self.source
        for forbidden in ("mktemp", "tee ", "sandbox_out", "TMPDIR=", "/tmp/"):
            self.assertNotIn(forbidden, source, forbidden)
        self.assertIn("unset BASH_ENV ENV CDPATH TMPDIR", source)
        self.assertIn('sandbox_text="$(run_sandbox materialize materialize)"', source)
        self.assertIn("NOT atomic", source)

    def test_artifacts_are_created_after_all_fallible_checks(self) -> None:
        source = self.source
        create = source.index('fs_op create-env "$LIVE_APP" "$CAND_APP"')
        for token in ("SHARED_STORAGE_MOVING_TARGET", "PUBLIC_TREE_ACL_FAILED",
                      "CANDIDATE_DIRTY_BEFORE_WRITE", "LIVE_PUBLIC_STORAGE_LINK_UNEXPECTED"):
            self.assertLess(source.index(token), create, token)
        self.assertLess(create, source.index("CANDIDATE_DIRTY_AFTER"))
        self.assertIn("trap on_exit EXIT", source)
        self.assertIn("post_fail NGINX_PRIVATE_ENV_EXPOSED", source)
        self.assertNotIn("runuser -u www-data -- test ! -r \"$CAND_APP/.env\" || fail", source)


class StorageDirectoryBoundaryTest(unittest.TestCase):
    def test_directory_and_root_access_metadata_changes_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a = root / "a"
            a.mkdir()
            (a / "sub").mkdir()
            b = root / "b"
            shutil.copytree(a, b, copy_function=shutil.copy2)
            self.assertEqual(storage_manifest.inventory(a), storage_manifest.inventory(b))
            original = (a / "sub").stat().st_mode & 0o777
            (b / "sub").chmod(original ^ 0o077)
            self.assertNotEqual(storage_manifest.inventory(a), storage_manifest.inventory(b))
            (b / "sub").chmod(original)
            b.chmod((a.stat().st_mode & 0o777) ^ 0o077)
            self.assertNotEqual(storage_manifest.inventory(a), storage_manifest.inventory(b))

    def test_directory_swap_to_symlink_is_rejected(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a = root / "a"
            a.mkdir()
            (a / "sub").mkdir()
            outside = root / "outside"
            outside.mkdir()
            original_open = os.open
            swapped = False
            def racing_open(name, flags, *args, **kwargs):
                nonlocal swapped
                if name == "sub" and kwargs.get("dir_fd") is not None and not swapped:
                    swapped = True
                    (a / "sub").rename(a / "original-sub")
                    (a / "sub").symlink_to(outside, target_is_directory=True)
                return original_open(name, flags, *args, **kwargs)
            with patch.object(storage_manifest.os, "open", side_effect=racing_open):
                with self.assertRaises((OSError, ValueError)):
                    storage_manifest.inventory(a)
            self.assertTrue(swapped)

if __name__ == "__main__":
    unittest.main()

