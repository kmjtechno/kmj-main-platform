import copy
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

import native_ops as n
import orchestrator as o


class PureTests(unittest.TestCase):
    def test_php_namespace_is_syntactically_single_backslash(self):
        line = next(x for x in n.MAINTENANCE_PROBE.splitlines() if x.startswith("$kernel="))
        self.assertIn("Illuminate" + chr(92) + "Contracts", line)
        self.assertNotIn(chr(92) * 2, line)

    def test_environment_preserves_application_values(self):
        self.assertEqual(n.parse_environment(b"APP_ENV=production\0CACHE_PREFIX=abc\0"),
                         {"APP_ENV": "production", "CACHE_PREFIX": "abc"})

    def test_environment_duplicate_or_invalid_is_rejected(self):
        for raw in (b"A=x\0A=y\0", b"A=x", b"BAD-KEY=x\0", b"A\0"):
            with self.subTest(raw=raw), self.assertRaises(o.Blocked): n.parse_environment(raw)

    def test_ruleset_counters_do_not_change_identity(self):
        first = {"nftables": [{"rule": {"handle": 9, "expr": [{"counter": {"packets": 1, "bytes": 40}}]}}]}
        second = copy.deepcopy(first)
        second["nftables"][0]["rule"]["expr"][0]["counter"] = {"packets": 80, "bytes": 9000}
        self.assertEqual(n.ruleset_identity(json.dumps(first)), n.ruleset_identity(json.dumps(second)))
        second["nftables"][0]["rule"]["handle"] = 10
        self.assertNotEqual(n.ruleset_identity(json.dumps(first)), n.ruleset_identity(json.dumps(second)))

    def test_ruleset_counter_type_not_normalized_away(self):
        with self.assertRaises(o.Blocked): n.ruleset_identity('{"counter":{"packets":true}}')

    def test_exact_live_sha_is_pinned(self):
        self.assertEqual(n.LIVE_SHA, "574e443a2c75a387aa4741e86d426c06a33e5b4c")

    def test_only_three_validated_systemd_metadata_fields_may_differ(self):
        left = {"APP_ENV": "production", "INVOCATION_ID": "a" * 32, "JOURNAL_STREAM": "1:2", "SYSTEMD_EXEC_PID": "12"}
        right = {"APP_ENV": "production", "INVOCATION_ID": "b" * 32, "JOURNAL_STREAM": "1:3", "SYSTEMD_EXEC_PID": "13"}
        self.assertEqual(n.application_environment(left), n.application_environment(right))
        right["CACHE_PREFIX"] = "changed"
        self.assertNotEqual(n.application_environment(left), n.application_environment(right))

    def test_invalid_systemd_metadata_is_rejected(self):
        with self.assertRaises(o.Blocked): n.application_environment({"INVOCATION_ID": "ignore me"})

    def test_recursive_descendants_include_grandchildren(self):
        processes = {2: {"ppid": 1}, 3: {"ppid": 2}, 4: {"ppid": 3}, 9: {"ppid": 1}}
        self.assertEqual(set(n.descendants(processes, 2)), {3, 4})


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.ops = n.NativeOps.__new__(n.NativeOps)
        self.ops.evidence = {"nonce": "a" * 32, "original_units": {unit: {"ControlGroup": ""} for unit in o.UNITS}}
        self.ops.account = types.SimpleNamespace(pw_uid=os.geteuid(), pw_gid=os.getegid())
        self.ops.flags, self.ops.fpm_fds, self.ops.queue_fd = {}, {}, None
        self.ops.marker_dir = None
        self.ops.env = {"APP_ENV": "production"}
        self.ops.pointer = Mock()
        self.ops.checkpoint = Mock()
        self.ops.execute = Mock()

    def test_inactive_missing_cgroup_proves_only_fixed_unit_absence(self):
        values = {"ActiveState": "inactive", "MainPID": "0", "ControlGroup": ""}
        self.ops.execute.return_value = b"Slice=system.slice\n"
        with patch.object(n, "cgroup_empty", side_effect=FileNotFoundError) as empty:
            self.assertTrue(self.ops.unit_empty(n.SCHEDULER, values))
        empty.assert_called_once_with("/system.slice/" + n.SCHEDULER)

    def test_missing_cgroup_never_excuses_active_process(self):
        values = {"ActiveState": "active", "MainPID": "12", "ControlGroup": ""}
        with patch.object(n, "cgroup_empty") as empty:
            self.assertFalse(self.ops.unit_empty(n.QUEUE, values))
        empty.assert_not_called()

    def test_unknown_slice_blocks_absence_inference(self):
        self.ops.execute.return_value = b"Slice=other.slice\n"
        with self.assertRaises(o.Blocked):
            self.ops.unit_empty(n.SCHEDULER, {"ActiveState": "inactive", "MainPID": "0", "ControlGroup": ""})

    def test_failed_wait_never_delivers_a_signal(self):
        self.ops.pointer = Mock()
        with patch.object(n.time, "monotonic", side_effect=[0, 2]), patch.object(n.time, "sleep"), self.assertRaises(o.Blocked):
            self.ops.wait(lambda: False, 1)
        self.ops.execute.assert_not_called()

    def test_recover_override_unlink_before_systemd_reload(self):
        prior = {"SendSIGKILL": "yes", "TimeoutStopUSec": "2min"}
        self.ops.evidence.update(stop_override={"name": "owned.conf"}, stop_policy_original=prior,
                                 stop_override_remove_intent=True)
        self.ops.unit_empty = Mock(return_value=True)
        self.ops.stop_policy = Mock(return_value=prior)
        self.ops.execute.side_effect = lambda args: self.assertNotIn("stop_override_removed", self.ops.evidence)
        with tempfile.TemporaryDirectory() as directory:
            self.ops.override_directory = lambda: os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            with patch.object(n.p, "properties", return_value=({}, "hash")):
                self.ops.remove_queue_stop_override()
        self.ops.execute.assert_called_once_with(["/usr/bin/systemctl", "daemon-reload"])
        self.assertTrue(self.ops.evidence["stop_override_removed"])

    def test_active_recovery_binds_journal_plan_before_scanner_mutation(self):
        self.ops.pointer = Mock()
        self.ops.release_lock = types.SimpleNamespace(verify=Mock())
        self.ops.guard_counter = Mock()
        self.ops.unit_empty = Mock(return_value=True)
        self.ops.fpm_children = Mock(return_value=[])
        self.ops.socket_empty = Mock(return_value=True)
        entry = {"phase": "begin", "plan": "aaaaaaaaaaaaaaaa"}
        scanner = types.SimpleNamespace(journal_read=lambda _: ([entry], 1, True), _LOCKS=[])
        mutations = []
        def recover(args):
            scanner.journal_read(None)
            mutations.append(args.apply)
            return {"status": "OK", "mutated": True}
        scanner.cmd_recover = recover
        self.ops.module = Mock(return_value=scanner)
        state = {"phase": "switch_intent", "plan_id": "bbbbbbbbbbbbbbbb"}
        with patch.object(n.p, "properties", return_value=({"ActiveState": "inactive"}, "hash")):
            with self.assertRaisesRegex(o.Blocked, "RECOVERY_JOURNAL_NOT_BOUND"):
                self.ops.recover_active_scanner(state)
            self.assertEqual(mutations, [])
            state["plan_id"] = entry["plan"]
            self.assertTrue(self.ops.recover_active_scanner(state))
        self.assertEqual(mutations, [True])

    def test_archived_v6_recovery_receipt_can_end_at_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o700)
            app = Path(directory) / "app"
            name = "storage.pre-shared-20261107T010203Z"
            key = n.p.digest(str(app).encode())[:12]
            (Path(directory) / (key + ".journal.done-1")).touch()
            receipt = [{"kept": name}, {"phase": "verified"}]
            helper = types.SimpleNamespace(receipt_entries=Mock(return_value=receipt))
            self.ops.module = Mock(side_effect=[helper, object()])
            def open_state(path):
                return os.open(path, os.O_RDONLY | os.O_DIRECTORY)
            with patch.object(n, "SCANNER_STATE", directory), patch.object(o, "protected_dir", side_effect=open_state):
                self.assertEqual(self.ops.completed_receipt(app, name), receipt)

    def test_stop_policy_is_never_restored_while_busy(self):
        self.ops.unit_empty = Mock(return_value=False)
        self.ops.evidence["original_units"][n.QUEUE]["ControlGroup"] = "/system.slice/queue"
        with patch.object(n.p, "properties", return_value=({"ActiveState": "deactivating"}, "hash")), self.assertRaises(o.Blocked):
            self.ops.remove_queue_stop_override()
        self.ops.execute.assert_not_called()

    def test_runtime_restore_rejects_unrestored_override(self):
        self.ops.evidence["stop_override"] = {"name": "owned.conf"}
        self.ops.systemctl = Mock()
        with self.assertRaises(o.Blocked): self.ops.restore_units(dict.fromkeys(o.UNITS, "active"))
        self.ops.systemctl.assert_not_called()

    def test_override_wal_precedes_create_and_reload_and_proves_effective_policy(self):
        self.ops.evidence["queue_replacement"] = {"pid": 44, "start": 100}
        self.ops.evidence["original_units"][n.QUEUE]["ControlGroup"] = "/system.slice/queue"
        self.ops.marker_bound = Mock()
        self.ops.maintenance_probe = Mock()
        prior = {"SendSIGKILL": "yes", "TimeoutStopUSec": "90s"}
        safe = {"SendSIGKILL": "no", "TimeoutStopUSec": "infinity"}
        self.ops.stop_policy = Mock(side_effect=[prior, safe])
        with tempfile.TemporaryDirectory() as directory:
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            name = "zzzz-kmj-storage-" + self.ops.evidence["nonce"] + ".conf"
            target = Path(directory) / name
            checkpoints = []
            self.ops.checkpoint = lambda: checkpoints.append(target.exists())
            self.ops.override_directory = lambda: os.dup(fd)
            def reload(args):
                self.assertEqual(args, ["/usr/bin/systemctl", "daemon-reload"])
                self.assertIsNotNone(self.ops.evidence["stop_override"]["inode"])
                self.assertEqual(target.read_bytes(), self.ops.override_payload())
            self.ops.execute.side_effect = reload
            try:
                with patch.object(n.p, "process", return_value=self.ops.evidence["queue_replacement"]), \
                     patch.object(n, "all_processes", return_value={}), patch.object(n, "cgroup_members", return_value={44}):
                    self.ops.install_queue_stop_override()
            finally:
                os.close(fd)
            self.assertEqual(checkpoints, [False, True, True])
            self.assertTrue(self.ops.evidence["stop_override_effective"])

    def test_foreign_override_inode_is_never_unlinked(self):
        self.ops.unit_empty = Mock(return_value=True)
        self.ops.evidence["stop_override"] = {"name": "owned.conf", "inode": [-1, -1]}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "owned.conf"
            target.write_text("foreign keep")
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            self.ops.override_directory = lambda: os.dup(fd)
            try:
                with patch.object(n.p, "properties", return_value=({}, "hash")), self.assertRaises(o.Blocked):
                    self.ops.remove_queue_stop_override()
            finally:
                os.close(fd)
            self.assertEqual(target.read_text(), "foreign keep")
        self.ops.execute.assert_not_called()

    def test_maintenance_probe_rejects_cache_only_in_current_process(self):
        result = {"driver": "file", "class": "Illuminate\\Foundation\\FileBasedMaintenanceMode",
                  "worker": "Illuminate\\Queue\\Worker", "storage": str(n.APP / "storage"),
                  "active": True, "config_cached": False, "cache_store": "Illuminate\\Cache\\ArrayStore"}
        self.ops.execute.return_value = json.dumps(result).encode()
        with self.assertRaises(o.Blocked): self.ops.maintenance_probe(True)

    def test_maintenance_probe_requires_exact_worker_class(self):
        result = {"driver": "file", "class": "Illuminate\\Foundation\\FileBasedMaintenanceMode",
                  "worker": "App\\CustomWorker", "storage": str(n.APP / "storage"),
                  "active": True, "config_cached": False, "cache_store": "Illuminate\\Cache\\RedisStore"}
        self.ops.execute.return_value = json.dumps(result).encode()
        with self.assertRaises(o.Blocked): self.ops.maintenance_probe(True)

    def test_no_mutation_for_unapproved_scanner_operation(self):
        with self.assertRaises(o.Blocked): self.ops.scanner_run("rollback")
        self.ops.execute.assert_not_called()

    def test_guard_never_deleted_if_baseline_identity_changed(self):
        self.ops.guard_absent = Mock(return_value=True)
        self.ops.evidence["ruleset_sha256"] = "wrong"
        with patch.object(n.p, "command", return_value=(b'{"nftables":[]}', b'')), self.assertRaises(o.Blocked):
            self.ops.remove_owned_guard()
        self.ops.execute.assert_not_called()

    def test_failed_insertion_absence_does_not_require_deleting_foreign_table(self):
        raw = b'{"nftables":[]}'
        self.ops.guard_absent = Mock(return_value=True)
        self.ops.evidence["ruleset_sha256"] = n.ruleset_identity(raw)
        with patch.object(n.p, "command", return_value=(raw, b'')):
            self.ops.remove_owned_guard()
        self.ops.execute.assert_not_called()
        self.assertTrue(self.ops.evidence["guard_removed"])

    def test_unexpected_guard_disappearance_blocks_reopen(self):
        self.ops.guard_absent = Mock(return_value=True)
        self.ops.evidence["guard_installed"] = True
        with self.assertRaises(o.Blocked): self.ops.remove_owned_guard()
        self.ops.execute.assert_not_called()

    def test_recovery_after_guard_deleted_before_completion_checkpoint(self):
        raw = b'{"nftables":[]}'
        self.ops.guard_absent = Mock(return_value=True)
        self.ops.evidence.update(guard_installed=True, guard_remove_intent=True,
                                 ruleset_sha256=n.ruleset_identity(raw))
        with patch.object(n.p, "command", return_value=(raw, b'')):
            self.ops.remove_owned_guard()
        self.ops.execute.assert_not_called()
        self.assertTrue(self.ops.evidence["guard_removed"])

    def test_resume_waits_through_activating(self):
        self.ops.env = {"APP_ENV": "production"}
        self.ops.verify_queue = Mock()
        self.ops.maintenance_probe = Mock()
        states = iter([False, True])
        def bounded(predicate, seconds):
            self.assertEqual(seconds, 30)
            self.assertFalse(predicate())
            self.assertTrue(predicate())
        self.ops.wait = bounded
        calls = [({"ActiveState": "activating", "MainPID": "0"}, "hash"),
                 ({"ActiveState": "active", "MainPID": "0"}, "hash"),
                 ({"ActiveState": "active", "MainPID": "99"}, "hash"),
                 ({"ActiveState": "active", "MainPID": "0"}, "hash")]
        with patch.object(n.p, "properties", side_effect=calls), patch.object(n.p, "process", return_value={"pid": 99}), \
             patch.object(n.p, "read_file", return_value=b"APP_ENV=production\0"):
            self.assertTrue(self.ops.runtime_restored({n.QUEUE: "active", n.TIMER: "active"}))
        self.ops.maintenance_probe.assert_called_once_with(False)

    def test_scanner_child_inherits_same_global_lock(self):
        raw = b"# harmless fixture; never executed\n"
        self.ops.release_lock = types.SimpleNamespace(fd=9999, verify=Mock())
        output = types.SimpleNamespace(stdout=b'{"command":"plan","plan_id":"4e95373c30a007b4"}')
        with patch.object(n.p, "read_file", return_value=raw), patch.dict(n.PINS, {"scanner": n.p.digest(raw)}), \
             patch.object(n.subprocess, "run", return_value=output) as run:
            self.assertEqual(self.ops.scanner_run("plan")["plan_id"], "4e95373c30a007b4")
        self.assertIn(9999, run.call_args.kwargs["pass_fds"])
        self.assertIn("-I", run.call_args.args[0])
        self.assertIn("-B", run.call_args.args[0])


class MarkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.storage = Path(self.temp.name) / "storage"
        (self.storage / "framework").mkdir(parents=True)
        self.ops = n.NativeOps.__new__(n.NativeOps)
        self.ops.account = types.SimpleNamespace(pw_uid=os.geteuid(), pw_gid=os.getegid())
        self.ops.evidence = {"nonce": "b" * 32, "maintenance_time": 1234,
                             "maintenance_storage": str(self.storage), "marker": None}
        self.ops.marker_dir = os.open(self.storage / "framework", os.O_RDONLY | os.O_DIRECTORY)
        self.ops.evidence["marker_directory"] = n.stamp(os.fstat(self.ops.marker_dir))
        self.path = self.storage / "framework/down"

    def tearDown(self):
        os.close(self.ops.marker_dir)
        self.temp.cleanup()

    def test_marker_nonce_and_inode_must_both_match(self):
        self.path.write_bytes(self.ops.marker_payload())
        self.ops.evidence["marker"] = n.stamp(self.path.stat())
        self.ops.marker_bound()
        self.path.write_bytes(b'{"kmj_storage_nonce":"foreign"}')
        with self.assertRaises(o.Blocked): self.ops.marker_bound()

    def test_symlink_cannot_redirect_root_marker_read(self):
        victim = Path(self.temp.name) / "victim"
        victim.write_text("do not change")
        self.path.symlink_to(victim)
        self.ops.evidence["marker"] = n.stamp(victim.stat())
        with self.assertRaises(OSError): self.ops.marker_bound()
        self.assertEqual(victim.read_text(), "do not change")

    def test_same_nonce_on_replacement_inode_is_rejected(self):
        self.path.write_bytes(self.ops.marker_payload())
        self.ops.evidence["marker"] = n.stamp(self.path.stat())
        replacement = self.path.with_name("replacement")
        replacement.write_bytes(self.ops.marker_payload())
        os.replace(replacement, self.path)
        with self.assertRaises(o.Blocked): self.ops.marker_bound()


if __name__ == "__main__":
    unittest.main()
