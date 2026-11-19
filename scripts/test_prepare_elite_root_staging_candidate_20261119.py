"""Non-root, offline tests for exact-SHA Elite staging root finalizer.

No root, SSH, production reads, service starts, approval writes or pointers.
"""
import importlib.util
import io
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stdout

SCRIPT = Path(__file__).resolve().parent / "operations/prepare-elite-root-staging-candidate-20261119.py"
spec = importlib.util.spec_from_file_location("stage_root_finalizer", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

SHA = "681d75531cd5fa91e47de2b4b639129ca53bcee2"
OLD = "b2e69decab3acd861e94e11992cd8a4cff4f2b94"
LIVE = "platform-ce6ad7dc9d89"


class StageRootFinalizerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.tree = self.root / "repo"
        app = self.tree / "apps/platform"
        (app / "public/build").mkdir(parents=True)
        (app / "storage/app").mkdir(parents=True)
        (app / "storage/logs").mkdir()
        (app / "storage/framework/cache").mkdir(parents=True)
        (app / "storage/framework/sessions").mkdir()
        (app / "storage/framework/views").mkdir()
        (app / ".env").write_text("APP_ENV=staging\n")
        (app / "public/build/manifest.json").write_text("{}")
        (app / "storage/app/upload.txt").write_text("fixture")
        (app / "storage/framework/views/rendered.php").write_text("<?php // compiled test")
        (app / "artisan").write_text("#!/usr/bin/env php\n")
        os.chmod(app / "artisan", 0o755)

    def operations(self):
        return {rel: (uid, gid, mode) for _p, rel, uid, gid, mode in
                m.freeze_plan(self.tree, 4567, 5678)}

    def test_root_readonly_executable_tree_and_exact_stage_env(self):
        x = self.operations()
        self.assertEqual(x["apps/platform"], (0, 5678, 0o750))
        self.assertEqual(x["apps/platform/.env"], (0, 5678, 0o640))
        self.assertEqual(x["apps/platform/artisan"], (0, 5678, 0o550))
        self.assertEqual(x["apps/platform/public/build/manifest.json"], (0, 5678, 0o440))
        self.assertEqual(x["apps/platform/storage/framework/views/rendered.php"],
                         (0, 0, 0o444))

    def test_only_runtime_mutable_subtrees_are_stage_owned(self):
        x = self.operations()
        self.assertEqual(x["apps/platform/storage"], (0, 0, 0o755))
        self.assertEqual(x["apps/platform/storage/framework"], (0, 0, 0o755))
        self.assertEqual(x["apps/platform/storage/framework/views"], (0, 0, 0o755))
        for path in ("apps/platform/storage/app",
                     "apps/platform/storage/framework/cache",
                     "apps/platform/storage/framework/sessions",
                     "apps/platform/storage/logs"):
            self.assertEqual(x[path], (4567, 5678, 0o750), path)
        self.assertEqual(x["apps/platform/storage/app/upload.txt"], (4567, 5678, 0o640))

    def test_no_world_readable_private_source(self):
        x = self.operations()
        for key in ("apps/platform/artisan",
                    "apps/platform/public/build/manifest.json",
                    "apps/platform/.env"):
            self.assertEqual(x[key][2] & 0o007, 0, key)
        self.assertEqual(x["apps/platform/storage/framework/views"], (0, 0, 0o755))
        self.assertEqual(x["apps/platform/storage/framework/views/rendered.php"], (0, 0, 0o444))

    def test_symlinked_executable_is_rejected(self):
        path = self.tree / "apps/platform/public/build/evil.php"
        path.symlink_to("/etc/passwd")
        with self.assertRaisesRegex(m.Block, "EXECUTABLE_TREE_SYMLINK_OR_SPECIAL"):
            self.operations()

    def test_hardlinked_executable_is_rejected(self):
        source = self.tree / "apps/platform/artisan"
        os.link(source, self.tree / "apps/platform/public/hardlink")
        with self.assertRaisesRegex(m.Block, "EXECUTABLE_TREE_HARDLINK"):
            self.operations()

    def test_symlinked_dir_outside_ignored_subtrees_rejected(self):
        path = self.tree / "apps/platform/public/link"
        path.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(m.Block, "EXECUTABLE_TREE_SYMLINK_OR_SPECIAL"):
            self.operations()

    def test_mutability_is_narrow_and_never_includes_views_or_code(self):
        for rel in ("apps/platform/storage/app",
                    "apps/platform/storage/app/a/b",
                    "apps/platform/storage/framework/sessions/x",
                    "apps/platform/storage/framework/cache/y",
                    "apps/platform/storage/logs/a.log"):
            self.assertTrue(m.mutable(rel), rel)
        for rel in ("apps/platform/storage", "apps/platform/storage/framework",
                    "apps/platform/storage/framework/views",
                    "apps/platform/storage/framework/views/a.php",
                    "apps/platform/vendor/autoload.php", "apps/platform/.env",
                    "apps/platform/storage/app-evil/extension.php"):
            self.assertFalse(m.mutable(rel), rel)

    def test_runner_digest_extraction_requires_literal_pinned_program(self):
        s = b"before <<'DIGEST_PY'\nprint('OK ' + 'a'*64)\nDIGEST_PY\nafter"
        self.assertEqual(m.digest_program(s), "print('OK ' + 'a'*64)")
        with self.assertRaisesRegex(m.Block, "INSTALLED_RUNNER_DIGEST_ABSENT"):
            m.digest_program(b"print('OK')")
        with self.assertRaises(UnicodeDecodeError):
            m.digest_program(b"<<'DIGEST_PY'\n\xff\nDIGEST_PY\n")

    def test_approved_source_sha_rejects_noncanonical_git_response(self):
        good = SHA + "\trefs/heads/staging-approved"
        with mock.patch.object(m, "fixed", return_value=good):
            self.assertEqual(m.approved_ref_sha(), SHA)
        for bad in ("", "fake", SHA + "\trefs/heads/main", SHA + "\trefs/heads/staging-approved\nx"):
            with mock.patch.object(m, "fixed", return_value=bad):
                with self.assertRaisesRegex(m.Block, "APPROVED_REF_UNVERIFIED"):
                    m.approved_ref_sha()

    def test_staging_env_isolation_never_reuses_production_database(self):
        safe = (b"APP_ENV=staging\n"
                b"APP_URL=https://staging.kmjtechno.com\n"
                b"APP_DEBUG=false\nDB_CONNECTION=pgsql\n"
                b"DB_HOST=127.0.0.1\nDB_PORT=5432\n"
                b"DB_DATABASE=kmj_stage_a9796a25\n"
                b"DB_USERNAME=kmjstage_a9796a25\n"
                b"MAIL_MAILER=log\nDB_PASSWORD=redacted-fixture\n")
        self.assertTrue(m.staging_env_isolated(safe))
        for bad in (
            safe.replace(b"kmj_stage_a9796a25", b"kmj_platform"),
            safe.replace(b"127.0.0.1", b"db.production.internal"),
            safe.replace(b"MAIL_MAILER=log", b"MAIL_MAILER=smtp"),
            safe.replace(b"APP_ENV=staging", b"APP_ENV=production"),
            safe.replace(b"APP_URL=https://staging.kmjtechno.com",
                         b"APP_URL=https://kmjtechno.com"),
            safe + b"DB_HOST=127.0.0.1\n",
            safe + b"\xff",
        ):
            with self.subTest(bad=bad[:36]):
                self.assertFalse(m.staging_env_isolated(bad))

    def test_parent_acl_rollback_requires_successful_restore(self):
        with mock.patch.object(m.subprocess, "run") as run:
            run.return_value.returncode = 0
            self.assertTrue(m.restore_metadata([b"one", b"two"]))
            self.assertEqual(run.call_count, 2)
        with mock.patch.object(m.subprocess, "run") as run:
            run.return_value.returncode = 1
            self.assertFalse(m.restore_metadata([b"one"]))

    def test_requires_exact_confirmation_before_any_host_audit(self):
        with mock.patch.object(m, "inspect") as audit:
            with self.assertRaisesRegex(m.Block, "EXPLICIT_OWNER_CONFIRMATION_REQUIRED"):
                m.run(["--prepare", SHA, OLD, LIVE])
            audit.assert_not_called()

    def test_dry_run_is_no_mutation_and_reports_parent_lock_requirement(self):
        with mock.patch.object(m, "inspect", return_value=(
                Path("/stage/old"), Path("/stage/new"),
                [(Path("/stage"), 1234, 1234, 0o750)])):
            with io.StringIO() as out, redirect_stdout(out):
                self.assertEqual(m.run(["--inspect", SHA, OLD, LIVE]), 0)
                text = out.getvalue()
        self.assertIn("STAGE_PARENT_ROOT_LOCK=REQUIRED_EXPLICIT_OWNER_PREPARE", text)
        self.assertIn("STAGE_PREPARE=INSPECT_PASS_NO_CHANGES", text)
        self.assertIn("PRODUCTION_SWITCH=NOT_ATTEMPTED", text)

    def test_cannot_run_with_unknown_mode(self):
        with self.assertRaises(SystemExit):
            m.run(["--activate", SHA, OLD, LIVE])

    def test_no_unapproved_activation_approval_or_live_pointer_write(self):
        src = SCRIPT.read_text()
        self.assertIn("STAGING_PROTECTED_APPROVAL=NOT_CREATED", src)
        self.assertIn("STAGING_POINTER=UNCHANGED", src)
        self.assertIn("PRODUCTION_POINTER=UNCHANGED", src)
        self.assertNotIn("systemctl start", src)
        self.assertNotIn("os.replace(SITE", src)
        self.assertNotIn("os.rename(SITE", src)
        self.assertNotIn("main-platform-staging-approval.json", src)
        self.assertNotIn("main-platform-production-release.json", src)

    def test_parent_plan_rejects_world_writable_or_symlinked_ancestor(self):
        home = self.root / "fakehome"
        releases = home / "releases"
        htdocs = home / "htdocs"
        home.mkdir()
        releases.mkdir()
        htdocs.mkdir()
        with mock.patch.multiple(m, STAGE=home, RELEASES=releases,
                                 SITE=htdocs / "site", PARENTS=(home, htdocs, releases)):
            self.assertEqual(len(m.parent_plan(os.getuid())), 3)
            os.chmod(releases, 0o777)
            with self.assertRaisesRegex(m.Block, "STAGING_PARENT_UNSAFE"):
                m.parent_plan(os.getuid())
            os.chmod(releases, 0o755)
            releases.rmdir()
            releases.symlink_to(self.root, target_is_directory=True)
            with self.assertRaisesRegex(m.Block, "PARENT_NOT_REAL_DIRECTORY"):
                m.parent_plan(os.getuid())

    def test_noclobber_publisher_preserves_existing_final_candidate(self):
        scratch = self.root / "scratch"
        old = self.root / "candidate"
        scratch.mkdir()
        old.mkdir()
        with self.assertRaisesRegex(m.Block, "CANDIDATE_PUBLISH_CONFLICT"):
            m.publish_noclobber(scratch, old)
        self.assertTrue(scratch.is_dir())
        self.assertTrue(old.is_dir())


if __name__ == "__main__":
    unittest.main()
