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

    def test_argument_guards_run_before_host_access(self) -> None:
        sha = "8e1a4973204e58050c794eec1ec3b8178b15dd33"
        for args, code in {
            (): "EXACT_SHA_AND_CURRENT_RELEASE_REQUIRED",
            ("x", "platform-8070dad72c55"): "EXACT_SHA_REQUIRED",
            (sha, "live"): "EXPECTED_CURRENT_RELEASE_INVALID",
            (sha, "platform-8e1a4973204e"): "TARGET_ALREADY_CURRENT",
            (sha, "platform-8070dad72c55"): "WRONG_HOST",
        }.items():
            result = subprocess.run(["bash", str(MATERIALIZE), *args], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("KMJ_MATERIALIZE=BLOCKED " + code, result.stdout)

    def test_copies_only_into_candidate_and_proves_parity(self) -> None:
        for token in ("cp -a --no-clobber", 'install -o kmjprod -g kmjprod -m 0600 "$LIVE_APP/.env" "$CAND_APP/.env"',
                      "STORAGE_PARITY_MISMATCH", "SOURCE_STORAGE_CHANGED_DURING_COPY",
                      "verify-main-platform-storage-manifest.py", "CANDIDATE_DIRTY_AFTER", "LIVE_AGENT_PUBLIC_URL_DIFFERS_REVIEW",
                      "CODEBRIDGE_AGENT_PUBLIC_URL=https://kmjtechno.com", "flock -n 9",
                      "DATABASE NOT_TOUCHED", "PRODUCTION_SWITCH NOT_ATTEMPTED"):
            self.assertIn(token, self.source)
        for forbidden in ("artisan migrate", "systemctl", "mv ", "rm -", "ln -sfn", '>>"$LIVE_APP',
                          '> "$LIVE_APP', "main-platform-production-release.json", "backupVerified",
                          "psql", "pg_dump", "sed -i"):
            self.assertNotIn(forbidden, self.source)


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

    def test_materialize_uses_three_content_snapshots_and_no_quiescence_claim(self) -> None:
        source = MATERIALIZE.read_text()
        for token in ("source_before=", "source_after=", "candidate_after=",
                      "SOURCE_STORAGE_CHANGED_DURING_COPY", "STORAGE_PARITY_MISMATCH",
                      "STORAGE_WRITER_QUIESCENCE NOT_ATTESTED",
                      "STORAGE_SYMLINK_TARGET_CONTENT NOT_DEREFERENCED"):
            self.assertIn(token, source)
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
                      '-p "ReadWritePaths=$CAND_APP"', '-p "ReadOnlyPaths=$LIVE_APP"',
                      "-p NoNewPrivileges=yes", "-p PrivateTmp=yes",
                      "SANDBOX_USER_MISMATCH", "export GIT_OPTIONAL_LOCKS=0"):
            self.assertIn(token, source)
        self.assertGreater(source.index('install -o kmjprod'), boundary)
        self.assertGreater(source.index('cp -a --no-clobber'), boundary)
        self.assertTrue(source.rstrip().endswith("KMJ_UNPRIVILEGED_MATERIALIZE"))
        self.assertNotIn("--system", source)
        self.assertNotIn("sudo", source)

if __name__ == "__main__":
    unittest.main()
