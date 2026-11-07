"""Disposable file and mocked syscall tests; never inventory the host."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_plan as n


class PriorityTests(unittest.TestCase):
    def doc(self, *chains):
        return {"nftables": [{"chain": c} for c in chains]}

    def chain(self, family, priority):
        return {"family": family, "hook": "output", "prio": priority}

    def test_all_families_contribute_to_priority(self):
        result = n.output_priority(self.doc(self.chain("ip", -10), self.chain("inet", 40), self.chain("ip6", 90)))
        self.assertEqual(result["proposed_priority"], 91)
        self.assertEqual(result["output_families"], ["inet", "ip", "ip6"])

    def test_non_ip_family_requires_review_even_with_numeric_priority(self):
        result = n.output_priority(self.doc(self.chain("bridge", 100)))
        self.assertEqual(result["proposed_priority"], 101)
        self.assertFalse(result["cross_family_hook_semantics_verified"])

    def test_empty_ruleset_default_zero(self):
        self.assertEqual(n.output_priority(self.doc())["proposed_priority"], 0)

    def test_negative_priority_does_not_assume_zero(self):
        self.assertEqual(n.output_priority(self.doc(self.chain("ip", -10)))["proposed_priority"], -9)

    def test_bool_symbol_and_integer_exhaustion_rejected(self):
        for value in (True, "filter", 2**31 - 1, -(2**31) - 1, 1.5, None):
            with self.subTest(value=value), self.assertRaises(n.Blocked):
                n.output_priority(self.doc(self.chain("ip", value)))

    def test_unknown_family_and_malformed_records_rejected(self):
        for doc in (self.doc(self.chain("unknown", 1)), {"nftables": {}, "other": []},
                    {"nftables": [{"chain": {}, "rule": {}}]}):
            with self.assertRaises(n.Blocked): n.output_priority(doc)


class CommandEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.args = ["/usr/bin/php8.4", "artisan", "queue:work", "--timeout=90"]
        self.raw = "{ path=/usr/bin/php8.4 ; argv[]=" + " ".join(self.args) + " ; ignore_errors=no ; }"

    def test_relative_artisan_cwd_and_known_hash(self):
        hashed = hashlib.sha256(json.dumps(self.args).encode()).hexdigest()
        with patch.dict(n.EXPECTED_ARGV_HASHES, {"queue": hashed}):
            result = n.unit_command(self.raw, str(n.APP), "queue:work", "queue")
        self.assertTrue(result["exact_direct_live_command"])
        self.assertTrue(result["known_argv_hash_matches"])
        self.assertFalse(result["force"])

    def test_wrong_cwd_and_actual_executable_not_admitted(self):
        self.assertFalse(n.unit_command(self.raw, "/", "queue:work", "queue")["exact_direct_live_command"])
        raw = self.raw.replace("path=/usr/bin/php8.4", "path=/bin/sh")
        self.assertFalse(n.unit_command(raw, str(n.APP), "queue:work", "queue")["exact_direct_live_command"])

    def test_force_and_secret_values_are_not_printed(self):
        args = self.args + ["--force", "--password=private-fixture"]
        result = n.argv_evidence(args, args[0], str(n.APP), "queue:work", "queue")
        self.assertTrue(result["force"])
        self.assertNotIn("private-fixture", json.dumps(result))

    def test_multiple_and_expanded_commands_rejected(self):
        for value in (self.raw + self.raw, self.raw.replace("--timeout=90", "$FLAGS")):
            with self.assertRaises(n.Blocked): n.unit_command(value, str(n.APP), "queue:work", "queue")

    def test_command_runner_rejects_mutation_before_any_process(self):
        with patch.object(n.subprocess, "run") as run, patch.object(n, "read_file") as read:
            for args in (["/usr/bin/systemctl", "stop", "nginx.service"], ["/usr/sbin/nft", "flush", "ruleset"],
                         ["/usr/bin/php8.4", str(n.APP / "artisan"), "down"]):
                with self.assertRaises(n.Blocked): n.command(args)
            run.assert_not_called(); read.assert_not_called()

    def test_allowed_read_contract_has_no_shell_and_scrubbed_environment(self):
        result = Mock(stdout=b"{}", stderr=b"")
        with patch.object(n, "read_file", return_value=b"tool"), patch.object(n.Path, "resolve", lambda self, strict=True: self), \
                patch.object(n.subprocess, "run", return_value=result) as run:
            self.assertEqual(n.command(["/usr/sbin/nft", "-j", "list", "ruleset"]), (b"{}", b""))
        self.assertEqual(run.call_args.kwargs["env"], n.ENV)
        self.assertIs(run.call_args.kwargs["stdin"], n.subprocess.DEVNULL)
        self.assertNotIn("shell", run.call_args.kwargs)


class FileAndConfigTests(unittest.TestCase):
    def test_read_file_does_not_modify_and_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "file"; p.write_bytes(b"data")
            before = p.stat()
            self.assertEqual(n.read_file(p), b"data")
            self.assertEqual(p.stat().st_mtime_ns, before.st_mtime_ns)
            link = Path(directory) / "link"; link.symlink_to(p)
            with self.assertRaises(OSError): n.read_file(link)

    def test_bounded_file_read(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "file"; p.write_bytes(b"oversize")
            with self.assertRaises(n.Blocked): n.read_file(p, 2)

    def test_dependency_is_hashed_from_one_read(self):
        with patch.dict(n.DEPENDENCIES, {"helper": "/fixed"}, clear=True), patch.object(n, "read_file", return_value=b"test") as read:
            result = n.dependency_inventory()
        self.assertEqual(read.call_args_list[0].args, ("/fixed",))
        self.assertEqual(read.call_args_list[0].kwargs, {"protected": True})
        self.assertEqual(read.call_count, 2)
        self.assertTrue(result["helper"]["observed"])
        self.assertFalse(result["helper"]["data"]["pin_matches"])

    def test_materializer_is_source_only_never_claimed_installed(self):
        raw = b"source"
        with patch.object(n, "read_file", return_value=raw), patch.dict(n.PINS, {"materializer": n.digest(raw)}):
            item = n.dependency_inventory()["materializer"]["data"]
        self.assertEqual(item["installation"], "SOURCE_PINNED_NOT_ROOT_INSTALLED")
        self.assertFalse(item["protected_root_install_verified"])

    def test_missing_dependency_is_explicit_not_fallback(self):
        with patch.object(n, "read_file", side_effect=FileNotFoundError):
            result = n.dependency_inventory()
        self.assertTrue(all(not x["observed"] for x in result.values()))

    def test_environment_values_never_escape(self):
        raw = b"DB_PASSWORD=private-fixture\nAPP_MAINTENANCE_DRIVER=file\n"
        with patch.object(n, "read_file", return_value=raw), patch.object(n.os.path, "lexists", return_value=False):
            result = n.maintenance_inventory()
        self.assertTrue(result["uncached_explicit_file_driver"])
        self.assertNotIn("private-fixture", json.dumps(result))
        self.assertFalse(result["effective_application_config_executed"])

    def test_duplicate_or_unknown_maintenance_driver_unverified(self):
        for raw in (b"APP_MAINTENANCE_DRIVER=file\nAPP_MAINTENANCE_DRIVER=file\n", b"APP_MAINTENANCE_DRIVER=secret\n", b""):
            with patch.object(n, "read_file", return_value=raw), patch.object(n.os.path, "lexists", return_value=False):
                self.assertFalse(n.maintenance_inventory()["uncached_explicit_file_driver"])

    def test_pool_selection_and_private_directive_redaction(self):
        raw = b"NOTICE: [other]\nNOTICE: user = foreign\nNOTICE: [kmj-elite-stage]\nNOTICE: user = kmjprod\nNOTICE: pm = ondemand\nNOTICE: listen = 127.0.0.1:21084\nNOTICE: pm.process_idle_timeout = 30\nNOTICE: pm.status_path = undefined\nNOTICE: env[DB_PASSWORD] = private-fixture\n"
        result = n.pool_config(raw)
        self.assertTrue(result["ondemand"] and result["listen_exact"])
        self.assertEqual(result["idle_timeout_seconds"], 30)
        self.assertNotIn("private-fixture", json.dumps(result))

    def test_duplicate_pool_never_claims_unique(self):
        with self.assertRaises(n.Blocked): n.pool_config(b"[kmj-elite-stage]\n[kmj-elite-stage]\n")

    def test_storage_override_value_only_reports_fixed_path_matches(self):
        value = n.pool_config(b"[kmj-elite-stage]\nenv[LARAVEL_STORAGE_PATH] = private-fixture\n")
        self.assertTrue(value["storage_override_declared"])
        self.assertFalse(value["storage_override_matches_live_storage"])
        self.assertFalse(value["storage_override_matches_shared_storage"])
        self.assertFalse(value["status_path_undefined"])
        self.assertNotIn("private-fixture", json.dumps(value))

    def test_fpm_listener_only_exact_ipv4_loopback(self):
        lines = "header\n 0: 0100007F:525C 00000000:0000 0A 00000000:00000003 00:0 0 0 0 123\n 1: 00000000:525C 00000000:0000 0A 0:0 00:0 0 0 0 456\n"
        self.assertEqual(n.production_listeners(lines), [{"inode": "123", "backlog": 3}])

    def test_unverified_reason_cannot_echo_secret_exception(self):
        value = n.section(lambda: (_ for _ in ()).throw(ValueError("private-fixture")))
        self.assertEqual(value, {"observed": False, "reason": "UNVERIFIED"})


class ProcessContractTests(unittest.TestCase):
    def test_candidate_git_is_identity_only_nonroot_and_no_new_privileges(self):
        responses = [SimpleNamespace(stdout=(n.CANDIDATE + "\n").encode()),
                     SimpleNamespace(stdout=(n.CANDIDATE_SHA + "\n").encode())]
        with patch.object(n.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=1234, pw_gid=5678)), \
                patch.object(n.Path, "stat", return_value=SimpleNamespace(st_uid=1234)), \
                patch.object(n, "read_file", return_value=b"trusted git"), \
                patch.object(n.subprocess, "run", side_effect=responses) as run:
            value = n.candidate_identity()
        self.assertTrue(value["expected_sha_matches"])
        self.assertFalse(value["source_cleanliness_attested"])
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            self.assertIn("rev-parse", call.args[0])
            self.assertNotIn("status", call.args[0])
            self.assertEqual(call.kwargs["user"], 1234)
            self.assertEqual(call.kwargs["group"], 5678)
            self.assertEqual(call.kwargs["extra_groups"], [])
            self.assertIs(call.kwargs["preexec_fn"], n.no_new_privileges)
            self.assertEqual(call.kwargs["env"]["GIT_CONFIG_GLOBAL"], "/dev/null")

    def test_candidate_root_service_identity_rejected_before_git(self):
        with patch.object(n.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=0)), \
                patch.object(n.subprocess, "run") as run:
            with self.assertRaises(n.Blocked): n.candidate_identity()
            run.assert_not_called()

    def nginx_fixture(self, wrong_namespace=False, wrong_uid=False):
        master = {"pid": 50, "ppid": 1, "uids": [0] * 4, "exe": "/usr/sbin/nginx", "args": ["nginx: master process"], "netns": [1, 2]}
        worker = {"pid": 51, "ppid": 50, "uids": [99 if wrong_uid else 42] * 4, "exe": "/usr/sbin/nginx", "args": ["nginx: worker process"], "netns": [3, 4] if wrong_namespace else [1, 2]}
        with patch.object(n, "properties", return_value=({"MainPID": "50"}, "hash")), \
                patch.object(n, "process", side_effect=lambda pid: {50: master, 51: worker}[pid]), \
                patch.object(n, "read_file", return_value=b"trusted nginx"), \
                patch.object(n.Path, "iterdir", return_value=iter([Path("/proc/50"), Path("/proc/51")])), \
                patch.object(n.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=42)), \
                patch.object(n, "namespace", return_value=[1, 2]):
            return n.nginx_inventory()

    def test_nginx_uid_is_derived_and_real_worker_namespace_is_checked(self):
        value = self.nginx_fixture()
        self.assertEqual(value["derived_www_data_uid"], 42)
        self.assertTrue(value["workers_verified"])
        self.assertFalse(self.nginx_fixture(wrong_namespace=True)["workers_verified"])
        self.assertFalse(self.nginx_fixture(wrong_uid=True)["workers_verified"])


if __name__ == "__main__":
    unittest.main()
