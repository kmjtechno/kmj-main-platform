#!/usr/bin/env python3
"""Hermetic negative tests for root-only Elite activation writer identity doctor.

No root, no production filesystem reads, no privileged service calls.
"""
import importlib.util
import errno
from pathlib import Path
from types import SimpleNamespace
import stat
import subprocess
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).parent / "operations" / "elite_activation_writer_identity_doctor.py"
spec = importlib.util.spec_from_file_location("kmj_elite_activation_writer_identity_doctor", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def master(pid=4321):
    return {"pid": pid, "parent": 1, "uids": (0, 0, 0, 0),
            "exe": mod.MASTER_EXE, "cmd": "php-fpm: master process"}


def worker(pid=4322, uid=1001, parent=4321, pool="php-fpm: pool kmjprod"):
    return {"pid": pid, "parent": parent, "uids": (uid, uid, uid, uid),
            "exe": mod.MASTER_EXE, "cmd": pool}


class WriterIdentityTests(unittest.TestCase):
    def test_realistic_master_and_all_kmjprod_workers_are_advisory_only(self):
        self.assertEqual(mod.pool_identity(4321, master(), [worker(), worker(pid=4323)], 1001), 2)

    def test_wrong_master_uid_executable_or_pid_fail_closed(self):
        bad = [
            {**master(), "pid": 4},
            {**master(), "uids": (0, 1001, 0, 0)},
            {**master(), "exe": "/tmp/php-fpm"},
        ]
        for item in bad:
            with self.subTest(item=item), self.assertRaises(mod.Blocked):
                mod.pool_identity(4321, item, [worker()], 1001)

    def test_no_fpm_worker_or_duplicate_snapshot_is_not_proof(self):
        with self.assertRaisesRegex(mod.Blocked, "NO_LIVE_FPM_WORKER"):
            mod.pool_identity(4321, master(), [], 1001)
        with self.assertRaisesRegex(mod.Blocked, "DUPLICATE_WORKER"):
            mod.pool_identity(4321, master(), [worker(), worker()], 1001)

    def test_non_owner_fpm_workers_and_mixed_stage_pool_rejected(self):
        for group in ([worker(uid=33)], [worker(), worker(pid=4323, uid=33)],
                      [worker(uid=0)], [worker(uid=1001, pool="php-fpm: pool stage"),
                                        worker(pid=4323, uid=1002)]):
            with self.subTest(group=group), self.assertRaisesRegex(
                mod.Blocked, "FPM_WRITER_UID_MISMATCH"
            ):
                mod.pool_identity(4321, master(), group, 1001)

    def test_unexpected_direct_child_or_wrong_parent_is_not_accepted(self):
        examples = [
            worker(parent=9876),
            worker(pool="worker --unsafe"),
            {**worker(), "exe": "/usr/bin/php"},
            worker(pool="php-fpm: pool " + "x" * 110),
        ]
        for item in examples:
            with self.subTest(item=item), self.assertRaisesRegex(
                mod.Blocked, "UNKNOWN_FPM_CHILD"
            ):
                mod.pool_identity(4321, master(), [item], 1001)

    def test_proc_status_parsing_real_effective_saved_and_fs_uids(self):
        raw = b"Name:\tphp-fpm8.4\nPPid:\t4321\nUid:\t1001\t1001\t1001\t1001\n"
        self.assertEqual(mod.parse_status(raw), (4321, (1001,) * 4))

    def test_proc_missing_duplicate_or_malformed_fields_rejected(self):
        raws = [
            b"PPid:\t4321\n",
            b"PPid:\t4321\nPPid:\t4321\nUid:\t1001 1001 1001 1001\n",
            b"PPid:\tBAD\nUid:\t1001 1001 1001 1001\n",
            b"PPid:\t4321\nUid:\t1001 1001 1001\n",
            b"PPid:\t4321\nUid:\t1001 1001 x 1001\n",
        ]
        for raw in raws:
            with self.subTest(raw=raw), self.assertRaises(mod.Blocked):
                mod.parse_status(raw)

    def test_directory_wrong_user_symlink_and_group_writable_are_blocked(self):
        info = SimpleNamespace(st_mode=stat.S_IFDIR | 0o750, st_uid=1001)
        with patch.object(mod.Path, "lstat", return_value=info), patch.object(
            mod, "no_extended_acl"
        ):
            mod.directory_identity(mod.INBOX_DIR, 1001)

        for bad in (
            SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_uid=1001),
            SimpleNamespace(st_mode=stat.S_IFDIR | 0o777, st_uid=1001),
            SimpleNamespace(st_mode=stat.S_IFDIR | 0o750, st_uid=1002),
        ):
            with self.subTest(bad=bad), patch.object(
                mod.Path, "lstat", return_value=bad
            ), self.assertRaises(mod.Blocked):
                mod.directory_identity(mod.INBOX_DIR, 1001)

    def test_empty_acl_is_required_and_extended_acl_rejected(self):
        missing = OSError(errno.ENODATA, "no xattr")
        with patch.object(mod.os, "getxattr", side_effect=missing):
            mod.no_extended_acl(mod.INBOX_DIR)

        with patch.object(mod.os, "getxattr", return_value=b"\x02\x00\x00"):
            with self.assertRaisesRegex(mod.Blocked, "EXTENDED_ACL"):
                mod.no_extended_acl(mod.INBOX_DIR)

        with patch.object(mod.os, "getxattr", side_effect=PermissionError("no access")):
            with self.assertRaisesRegex(mod.Blocked, "ACL_UNVERIFIED"):
                mod.no_extended_acl(mod.INBOX_DIR)

    def test_existing_request_never_reported_safe_to_overwrite(self):
        safe_dir = SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=1001)
        safe_file = SimpleNamespace(
            st_mode=stat.S_IFREG | 0o640, st_uid=1001, st_nlink=1,
        )

        def lstat(self):
            return safe_file if self == mod.INBOX else safe_dir

        with patch.object(mod, "directory_identity"), patch.object(
            mod.Path, "lstat", lstat
        ), patch.object(mod, "no_extended_acl"):
            with self.assertRaisesRegex(mod.Blocked, "EXISTING_REQUEST_REQUIRES"):
                mod.fixed_parent_chain(1001)

        with patch.object(mod, "directory_identity"), patch.object(
            mod.Path, "lstat", side_effect=lambda p: safe_file
            if p == mod.INBOX else safe_dir
        ), patch.object(mod, "no_extended_acl"):
            with self.assertRaises(mod.Blocked):
                mod.fixed_parent_chain(1002)

    def test_absent_intent_is_not_a_request_or_permission_to_create_one(self):
        safe_dir = SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=1001)

        def lstat(self):
            if self == mod.INBOX:
                raise FileNotFoundError()
            return safe_dir

        with patch.object(mod, "directory_identity"), patch.object(mod.Path, "lstat", lstat):
            mod.fixed_parent_chain(1001)

    def test_fixed_systemctl_requires_active_exact_service_and_pid(self):
        proc = SimpleNamespace(returncode=0, stdout="MainPID=4321\nActiveState=active\n")
        with patch.object(mod.subprocess, "run", return_value=proc) as p:
            self.assertEqual(mod.fixed_master_pid(), 4321)
            self.assertEqual(p.call_args.args[0][:4], [
                "/usr/bin/systemctl", "show", "--no-pager", mod.UNIT
            ])
        for response in (
            SimpleNamespace(returncode=0, stdout="MainPID=0\nActiveState=active\n"),
            SimpleNamespace(returncode=0, stdout="MainPID=4321\nActiveState=failed\n"),
            SimpleNamespace(returncode=0, stdout="MainPID=4321\n"),
            SimpleNamespace(returncode=1, stdout="MainPID=4321\nActiveState=active\n"),
        ):
            with patch.object(mod.subprocess, "run", return_value=response):
                with self.assertRaises(mod.Blocked):
                    mod.fixed_master_pid()

    def test_wrong_host_nonroot_cannot_even_probe_php_workers(self):
        with patch.object(mod.os, "geteuid", return_value=1001), patch.object(
            mod, "fixed_master_pid", side_effect=AssertionError("unsafe probe")
        ):
            self.assertEqual(mod.inspect(), 2)
        with patch.object(mod.os, "geteuid", return_value=0), patch.object(
            mod.socket, "gethostname", return_value="google-vps1"
        ), patch.object(mod, "fixed_master_pid", side_effect=AssertionError("unsafe probe")):
            self.assertEqual(mod.inspect(), 2)

    def test_success_only_means_review_ready_not_installed_or_deployed(self):
        with patch.object(mod.os, "geteuid", return_value=0), patch.object(
            mod.socket, "gethostname", return_value="KMJ-elite"
        ), patch.object(mod.pwd, "getpwnam") as p, patch.object(
            mod, "fixed_parent_chain"
        ), patch.object(mod, "fixed_master_pid", return_value=4321), patch.object(
            mod, "process_identity", return_value=master()
        ), patch.object(mod, "fixed_live_children", return_value=[worker()]), patch.object(
            mod, "pool_identity", return_value=1
        ), patch("builtins.print") as output:
            p.return_value.pw_uid = 1001
            self.assertEqual(mod.inspect(), 0)
            printed = " ".join(" ".join(str(x) for x in call.args) for call in output.call_args_list)
            self.assertIn("READY_FOR_OWNER_REVIEW_NOT_INSTALLED", printed)
            self.assertIn("PRODUCTION_MUTATION=NONE", printed)
            self.assertNotIn("DEPLOY=PASS", printed)

    def test_source_never_starts_or_mutates_privileged_services(self):
        source = SOURCE.read_text()
        self.assertIn("INBOX_DIR = Path(", source)
        self.assertIn("MASTER_EXE = ", source)
        self.assertNotIn("systemctl start", source)
        self.assertNotIn("subprocess.Popen", source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.chown", source)
        self.assertNotIn("os.chmod", source)
        self.assertNotIn("mkdir(", source)
        self.assertNotIn("os.unlink", source)
        self.assertNotIn("open(INBOX", source)
        self.assertNotIn("fixed_root_preflight = true", source)


if __name__ == "__main__":
    unittest.main()
