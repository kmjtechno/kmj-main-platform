#!/usr/bin/env python3
"""Offline fail-closed contract tests for the exact 09e8 native READ-ONLY inventory."""
from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest import mock

SOURCE = (Path(__file__).resolve().parent /
          "operations/09e8-native-writer-inventory-readonly-20261109.py")
SPEC = importlib.util.spec_from_file_location("native_inventory_09e8", SOURCE)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def ok(data):
    return {"observed": True, "data": data}


class ExactNativeInventoryTests(unittest.TestCase):
    def test_exact_live_candidate_and_installed_scanner_contract(self):
        self.assertEqual(module.LIVE, "/home/kmjprod/releases/platform-bce4100d005e")
        self.assertEqual(module.CANDIDATE, "/home/kmjprod/releases/platform-09e8a224cd37")
        self.assertEqual(module.CANDIDATE_SHA, "09e8a224cd37445c42588a073a6b52d207475a09")
        self.assertEqual(module.SHARED, "/home/kmjprod/shared/storage")
        self.assertEqual(module.PINS["scanner"],
                         "f4d01f6e3b40c9ad774c8ada5129b241cee93dac782ce75bb0e229b26bbc95ba")
        self.assertEqual(module.EXPECTED_ARGV_HASHES, {"queue": "", "scheduler": ""})
        self.assertEqual(module.PORT if hasattr(module, "PORT") else 21084, 21084)
        self.assertEqual(module.POOL, "kmj-elite-stage")

    def test_root_materializer_is_distinct_from_stale_dev_source(self):
        self.assertEqual(
            module.MATERIALIZER_ROOT,
            "/usr/local/libexec/kmj-codebridge/main-platform-candidate-materialize-v2.sh"
        )
        doc = {"dependencies": {
            "helper": ok({"pin_matches": True}),
            "scanner": ok({"pin_matches": True}),
            "materializer": {"observed": False, "reason": "UNVERIFIED"},
            "materializer_project_source": ok({"pin_matches": True}),
        }}
        result = module.attest_report(doc)
        self.assertEqual(result["MATERIALIZER_SOURCE_PINNED"], "YES")
        self.assertEqual(result["MATERIALIZER_ROOT_PINNED"], "NO_OR_UNVERIFIED")
        self.assertEqual(result["MATERIALIZER_ROOT_INSTALL_REQUIRED"], "YES_UNTIL_PROVEN")
        self.assertEqual(result["STORAGE_APPLY_ALLOWED"], "NO")
        doc["dependencies"]["materializer"] = ok({"pin_matches": True})
        result = module.attest_report(doc)
        self.assertEqual(result["MATERIALIZER_ROOT_PINNED"], "YES")
        self.assertEqual(result["MATERIALIZER_ROOT_INSTALL_REQUIRED"], "NO")
        self.assertEqual(result["STORAGE_APPLY_ALLOWED"], "NO")

    def test_root_materializer_checks_root_protected_bytes_not_project_copy(self):
        def get_file(path, limit=1048576, protected=False):
            if path == module.MATERIALIZER_ROOT:
                self.assertTrue(protected)
                return b"installed-root-script"
            if path == module.MATERIALIZER_SOURCE:
                self.assertFalse(protected)
                return b"stale-dev-source"
            if path in module.DEPENDENCIES.values():
                self.assertTrue(protected)
                return b"protected-other"
            raise AssertionError("unexpected path " + str(path))

        def hasher(data):
            if data == b"installed-root-script":
                return module.PINS["materializer"]
            if data == b"stale-dev-source":
                return "0" * 64
            return "1" * 64

        with mock.patch.object(module, "read_file", side_effect=get_file), \
             mock.patch.object(module, "digest", side_effect=hasher):
            deps = module.dependency_inventory()
        self.assertIs(deps["materializer"]["data"]["pin_matches"], True)
        self.assertIs(deps["materializer_project_source"]["data"]["pin_matches"], False)
        self.assertNotIn("stale-dev-source", str(deps))

    def test_service_timer_properties_are_type_scoped(self):
        self.assertNotIn("Triggers", module.SERVICE_PROPERTIES)
        self.assertNotIn("MainPID", module.TIMER_PROPERTIES)
        self.assertNotIn("Restart", module.TIMER_PROPERTIES)
        self.assertIn("Triggers", module.TIMER_PROPERTIES)

    def test_empty_inventory_never_approves(self):
        values = module.attest_report({})
        self.assertEqual(values["STORAGE_APPLY_ALLOWED"], "NO")
        self.assertEqual(values["PROCESS_DRAIN_ATTESTED"], "NO")
        self.assertEqual(values["WRITER_ADMISSION_CLOSED"], "NOT_ATTESTED")
        self.assertEqual(values["LIVE_STORAGE_SWITCH_REQUIRED"], "NO")
        for key in ("PINNED_SCANNER", "FPM_POOL_EXACT_LISTEN",
                    "FPM_MASTER_LISTENER_IDENTITY", "ROOT_LOCK_SAFE",
                    "MATERIALIZER_ROOT_PINNED"):
            self.assertEqual(values[key], "NO_OR_UNVERIFIED")

    def test_exact_scope_can_be_reported_without_claiming_writer_exclusion(self):
        units = {
            module.UNITS[0]: {"ActiveState": "active", "Restart": "always",
                              "unit_command": ok({"exact_direct_live_command": True}),
                              "runtime": ok({"all_uids_kmjprod": True,
                                             "host_network_namespace": True})},
            module.UNITS[1]: {"ActiveState": "inactive",
                              "unit_command": ok({"exact_direct_live_command": True})},
            module.UNITS[2]: {"exact_scheduler_trigger": True},
        }
        data = {
            "candidate_identity": ok({"expected_sha_matches": True}),
            "units": ok(units),
            "production_pool_config": ok({"listen_exact": True, "user_kmjprod": True,
                                         "ondemand": True}),
            "production_fpm_processes": ok({"single_listener_owned_by_master": True,
                                           "master_root_uids": True,
                                           "master_executable_exact": True,
                                           "master_host_netns": True}),
            "nginx_workers": ok({"workers_verified": True}),
            "nginx_config": ok({"production_fastcgi_references": 1}),
            "maintenance": ok({"uncached_explicit_file_driver": True}),
            "dependencies": {"scanner": ok({"pin_matches": True}),
                             "helper": ok({"pin_matches": True}),
                             "materializer": ok({"pin_matches": True})},
            "nft": ok({"cross_family_hook_semantics_verified": True}),
            "release_lock": ok({"protected_root_0600_single_link": True}),
            "root_capabilities": ok({"net_admin": True, "linux_immutable": True}),
        }
        report = module.attest_report(data)
        self.assertEqual(report["QUEUE_DIRECT_LIVE_COMMAND"], "YES")
        self.assertEqual(report["PINNED_SCANNER"], "YES")
        self.assertEqual(report["FPM_POOL_EXACT_LISTEN"], "YES")
        self.assertEqual(report["CANDIDATE_EXACT_GIT_HEAD"], "YES")
        self.assertEqual(report["QUEUE_OLD_ARGV_PINS_REUSED"], "NO")
        self.assertEqual(report["WRITER_ADMISSION_CLOSED"], "NOT_ATTESTED")
        self.assertEqual(report["PROCESS_DRAIN_ATTESTED"], "NO")
        self.assertEqual(report["STORAGE_APPLY_ALLOWED"], "NO")
        self.assertEqual(report["PRODUCTION_MUTATION"], "NONE")

    def test_unobserved_and_transient_process_cannot_pass(self):
        doc = {"units": ok({
            module.UNITS[0]: {"ActiveState": "activating", "Restart": "on-failure",
                              "unit_command": {"observed": False, "reason": "UNVERIFIED"}},
            module.UNITS[1]: {"ActiveState": "deactivating"},
            module.UNITS[2]: {"exact_scheduler_trigger": False},
        })}
        result = module.attest_report(doc)
        self.assertEqual(result["QUEUE_STATE"], "ACTIVATING")
        self.assertEqual(result["SCHEDULER_STATE"], "DEACTIVATING")
        self.assertEqual(result["QUEUE_DIRECT_LIVE_COMMAND"], "NO_OR_UNVERIFIED")
        self.assertEqual(result["QUEUE_RESTART_ALWAYS"], "NO_OR_UNVERIFIED")
        self.assertEqual(result["TIMER_EXACT_TRIGGER"], "NO_OR_UNVERIFIED")
        self.assertEqual(result["STORAGE_APPLY_ALLOWED"], "NO")

    def test_bad_nft_output_family_fails_closed(self):
        with self.assertRaises(module.Blocked):
            module.output_priority({"nftables":[{"chain": {
                "hook":"output","family":"unknown","prio":0}}]})

    def test_failed_runtime_has_no_untrusted_diagnostics_or_changes(self):
        with mock.patch.object(module, "inventory", side_effect=module.Blocked("PRIVATE_SECRET")):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = module.main()
        self.assertEqual(rc, 2)
        self.assertNotIn("PRIVATE_SECRET", out.getvalue())
        self.assertIn("STORAGE_APPLY_ALLOWED=NO", out.getvalue())
        self.assertIn("PRODUCTION_MUTATION=NONE", out.getvalue())

    def test_source_only_fixed_reads(self):
        source = SOURCE.read_text("utf-8")
        for forbidden in (
                "systemctl stop", "systemctl start", "systemctl restart",
                "subprocess.Popen(", "shell=True", "os.symlink(", "os.replace(",
                "os.unlink(", "os.rename(", "os.chmod(", "os.chown(",
                " --apply", "git reset", "nft add", "artisan migrate"):
            self.assertNotIn(forbidden, source)
        self.assertIn("WRITER_ADMISSION_CLOSED", source)
        self.assertIn("STORAGE_APPLY_ALLOWED", source)
        self.assertIn("PRODUCTION_MUTATION", source)


if __name__ == "__main__":
    unittest.main()
