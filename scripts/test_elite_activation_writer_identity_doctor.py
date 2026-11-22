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

    def test_mixed_pool_uid_mismatch_is_only_bounded_counts_and_remains_blocked(self):
        actors = [
            worker(pid=4322, uid=1001, pool="php-fpm: pool kmjprod"),
            worker(pid=4323, uid=33, pool="php-fpm: pool www"),
            worker(pid=4324, uid=1002, pool="php-fpm: pool kmjstage"),
            worker(pid=4325, uid=1002, pool="php-fpm: pool PRIVATE_SECRET_POOL"),
        ]
        with patch("builtins.print") as emitted, self.assertRaisesRegex(
            mod.Blocked, "FPM_WRITER_UID_MISMATCH"
        ):
            mod.pool_identity(4321, master(), actors, 1001)
        lines = [str(c.args[0]) for c in emitted.call_args_list]
        self.assertIn("KMJ_FPM_POOL_KMJPROD_OWNER_UID_COUNT=1", lines)
        self.assertIn("KMJ_FPM_POOL_WWW_OTHER_UID_COUNT=1", lines)
        self.assertIn("KMJ_FPM_POOL_STAGING_OTHER_UID_COUNT=1", lines)
        self.assertIn("KMJ_FPM_POOL_OTHER_OTHER_UID_COUNT=1", lines)
        self.assertNotIn("PRIVATE_SECRET_POOL", " ".join(lines))
        self.assertNotIn("1002", " ".join(lines))
        self.assertNotIn("1001", " ".join(lines))

    def test_untrusted_child_shape_is_rejected_before_any_uid_aggregate(self):
        group = [worker(uid=33), worker(pid=4323, uid=1001, pool="BAD_PROCESS secrets")]
        with patch("builtins.print") as emitted, self.assertRaisesRegex(
            mod.Blocked, "BLOCKED_UNKNOWN_FPM_CHILD"
        ):
            mod.pool_identity(4321, master(), group, 1001)
        emitted.assert_not_called()

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

    def test_production_only_binding_allows_isolated_www_worker(self):
        prod = worker(pid=4322, uid=1001, pool=mod.PRODUCTION_POOL)
        other = worker(pid=4323, uid=33, pool="php-fpm: pool www")
        actors = [prod, other]
        with patch.object(mod, "host_network_namespace", return_value="net:[1]"), patch.object(
            mod, "listener_inode", return_value="987654"
        ), patch.object(
            mod, "holds_listener", side_effect=lambda pid, inode: pid in (4321, 4322)
        ), patch.object(mod, "fixed_live_children", return_value=actors):
            self.assertEqual(mod.production_pool_binding(4321, master(), actors, 1001), 1)

    def test_production_binding_fails_on_unsafe_socket_ownership(self):
        prod = worker(pid=4322, uid=1001, pool=mod.PRODUCTION_POOL)
        other = worker(pid=4323, uid=33, pool="php-fpm: pool www")
        actors = [prod, other]
        examples = [
            ("BLOCKED_MASTER_LISTENER_BINDING", {4322}),
            ("BLOCKED_PRODUCTION_WORKER_LISTENER_BINDING", {4321}),
            ("BLOCKED_FOREIGN_POOL_LISTENER_BINDING", {4321, 4322, 4323}),
        ]
        for expected, holders in examples:
            with self.subTest(expected=expected), patch.object(
                mod, "host_network_namespace", return_value="net:[1]"
            ), patch.object(mod, "listener_inode", return_value="987654"), patch.object(
                mod, "holds_listener", side_effect=lambda pid, inode: pid in holders
            ), patch.object(mod, "fixed_live_children", return_value=actors):
                with self.assertRaisesRegex(mod.Blocked, expected):
                    mod.production_pool_binding(4321, master(), actors, 1001)

    def test_production_binding_wrong_worker_uid_or_pool_denied(self):
        bad = [
            ([worker(uid=33, pool=mod.PRODUCTION_POOL)], "FPM_WRITER_UID_MISMATCH"),
            ([worker(uid=1001, pool="php-fpm: pool www")], "NO_LIVE_FPM_WORKER"),
            ([{**worker(pool=mod.PRODUCTION_POOL), "exe": "/tmp/php-fpm"}], "UNKNOWN_FPM_CHILD"),
            ([{**worker(pool=mod.PRODUCTION_POOL), "parent": 123}], "UNKNOWN_FPM_CHILD"),
        ]
        with patch.object(mod, "listener_inode", side_effect=AssertionError("should fail early")):
            for group, expected in bad:
                with self.subTest(expected=expected), self.assertRaisesRegex(mod.Blocked, expected):
                    mod.production_pool_binding(4321, master(), group, 1001)

    def test_production_binding_race_or_wrong_netns_denied(self):
        actors = [worker(pid=4322, pool=mod.PRODUCTION_POOL)]
        with patch.object(
            mod, "host_network_namespace", side_effect=lambda pid: "net:[2]" if pid == 4321 else "net:[1]"
        ), patch.object(mod, "listener_inode", side_effect=AssertionError("should fail early")):
            with self.assertRaisesRegex(mod.Blocked, "MASTER_NETNS"):
                mod.production_pool_binding(4321, master(), actors, 1001)

        def safe_holds(pid, inode):
            return pid in (4321, 4322)

        with patch.object(mod, "host_network_namespace", return_value="net:[1]"), patch.object(
            mod, "listener_inode", side_effect=["987654", "999999"]
        ), patch.object(mod, "holds_listener", side_effect=safe_holds), patch.object(
            mod, "fixed_live_children", return_value=actors
        ):
            with self.assertRaisesRegex(mod.Blocked, "PRODUCTION_BINDING_RACE"):
                mod.production_pool_binding(4321, master(), actors, 1001)

        with patch.object(mod, "host_network_namespace", return_value="net:[1]"), patch.object(
            mod, "listener_inode", return_value="987654"
        ), patch.object(mod, "holds_listener", side_effect=safe_holds), patch.object(
            mod, "fixed_live_children", return_value=[]
        ):
            with self.assertRaisesRegex(mod.Blocked, "PRODUCTION_BINDING_RACE"):
                mod.production_pool_binding(4321, master(), actors, 1001)

    def test_listener_inode_exact_tcp_state_and_unique_inode(self):
        from unittest.mock import mock_open
        def tcp_body(ports):
            return "sl local_address rem_address st tx_queue tr tm->when retrnsmt uid timeout inode\n" + (
                "\n".join(
                    f"{i}: {p} 00000000:0000 {state} 0:0 0:0 00 00000000 0 {ino}"
                    for i, (p, state, ino) in enumerate(ports)
                )
            ) + "\n"
        accepted = tcp_body([
            ("0100007F:525C", "0A", "987654"),
            ("0100007F:525C", "01", "123456"),
            ("00000000:0050", "0A", "42"),
        ])
        with patch.object(mod.Path, "open", mock_open(read_data=accepted)):
            self.assertEqual(mod.listener_inode(), "987654")
        for bad, reason in (
            (tcp_body([]), "PRODUCTION_LISTENER_COUNT"),
            (tcp_body([("0100007F:525C", "0A", "987654"), ("0100007F:525C", "0A", "777777")]), "PRODUCTION_LISTENER_COUNT"),
            (tcp_body([("0100007F:525C", "0A", "0")]), "TCP_INODE"),
        ):
            with self.subTest(reason=reason), patch.object(mod.Path, "open", mock_open(read_data=bad)):
                with self.assertRaisesRegex(mod.Blocked, reason):
                    mod.listener_inode()

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

        # Parent is still owned by UID 1001. A broker configured for a
        # different owner MUST refuse it without reading request contents.
        with patch.object(mod, "directory_identity"), patch.object(
            mod.Path, "lstat", lstat
        ), patch.object(mod, "no_extended_acl"):
            with self.assertRaisesRegex(mod.Blocked, "INBOX_NOT_OWNER_UID"):
                mod.fixed_parent_chain(1002)

    def test_absent_intent_is_not_a_request_or_permission_to_create_one(self):
        safe_dir = SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=1001)

        def lstat(self):
            if self == mod.INBOX:
                raise FileNotFoundError()
            return safe_dir

        with patch.object(mod, "directory_identity"), patch.object(mod.Path, "lstat", lstat):
            mod.fixed_parent_chain(1001)

    def test_proc_scan_reads_executable_only_for_fixed_fpm_master_children(self):
        import io
        from unittest.mock import Mock

        paths = [Path("/proc/50"), Path("/proc/60")]
        status = {
            "/proc/50/status": b"PPid:\t1\nUid:\t0 0 0 0\n",
            "/proc/60/status": b"PPid:\t4321\nUid:\t1001 1001 1001 1001\n",
        }

        def only_status(self, mode="rb"):
            if str(self) not in status:
                raise AssertionError("Unexpected process file access")
            return io.BytesIO(status[str(self)])

        with patch.object(mod.Path, "iterdir", return_value=paths), patch.object(
            mod.Path, "open", only_status
        ), patch.object(mod, "process_identity", return_value=worker(pid=60)) as probe:
            result = mod.fixed_live_children(4321)
            self.assertEqual(result, [worker(pid=60)])
            probe.assert_called_once_with(60)

        with patch.object(mod.Path, "iterdir", return_value=paths), patch.object(
            mod.Path, "open", only_status
        ), patch.object(mod, "process_identity", return_value=worker(pid=60, parent=7)):
            with self.assertRaisesRegex(mod.Blocked, "FPM_WORKER_PARENT_RACE"):
                mod.fixed_live_children(4321)

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
            mod, "production_pool_binding", return_value=1
        ), patch("builtins.print") as output:
            p.return_value.pw_uid = 1001
            self.assertEqual(mod.inspect(), 0)
            printed = " ".join(" ".join(str(x) for x in call.args) for call in output.call_args_list)
            self.assertIn("READY_FOR_OWNER_REVIEW_NOT_INSTALLED", printed)
            self.assertIn("PRODUCTION_MUTATION=NONE", printed)
            self.assertNotIn("DEPLOY=PASS", printed)

    def test_os_error_classified_by_fixed_phase_without_leaking_exception(self):
        with patch.object(mod.os, "geteuid", return_value=0), patch.object(
            mod.socket, "gethostname", return_value="KMJ-elite"
        ), patch.object(mod.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=1001)), patch.object(
            mod, "fixed_parent_chain", side_effect=OSError("DO_NOT_PRINT_SECRET_PATH")
        ), patch("builtins.print") as emitted:
            self.assertEqual(mod.inspect(), 2)
            messages = [str(c.args[0]) for c in emitted.call_args_list]
            self.assertIn("KMJ_ACTIVATION_WRITER_IDENTITY=BLOCKED_READONLY_PROBE_UNVERIFIED", messages)
            self.assertIn("KMJ_ACTIVATION_PROBE_PHASE=PRIVATE_INBOX", messages)
            self.assertNotIn("DO_NOT_PRINT_SECRET_PATH", " ".join(messages))

        with patch.object(mod.os, "geteuid", return_value=0), patch.object(
            mod.socket, "gethostname", return_value="KMJ-elite"
        ), patch.object(mod.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=1001)), patch.object(
            mod, "fixed_parent_chain"
        ), patch.object(mod, "fixed_master_pid", return_value=4321), patch.object(
            mod, "process_identity", return_value=master()
        ), patch.object(mod, "fixed_live_children", side_effect=OSError("PRIVATE_PROC_DATA")), patch(
            "builtins.print"
        ) as emitted:
            self.assertEqual(mod.inspect(), 2)
            messages = [str(c.args[0]) for c in emitted.call_args_list]
            self.assertIn("KMJ_ACTIVATION_PROBE_PHASE=FPM_CHILD_PROCESSES", messages)
            self.assertNotIn("PRIVATE_PROC_DATA", " ".join(messages))

    def test_unknown_owner_uid_reports_categorical_phase_not_traceback(self):
        with patch.object(mod.os, "geteuid", return_value=0), patch.object(
            mod.socket, "gethostname", return_value="KMJ-elite"
        ), patch.object(mod.pwd, "getpwnam", side_effect=KeyError("SENSITIVE_NSS_LOOKUP")), patch(
            "builtins.print"
        ) as emitted:
            self.assertEqual(mod.inspect(), 2)
            messages = [str(c.args[0]) for c in emitted.call_args_list]
            self.assertIn("KMJ_ACTIVATION_PROBE_PHASE=OWNER_UID", messages)
            self.assertNotIn("SENSITIVE_NSS_LOOKUP", " ".join(messages))

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
