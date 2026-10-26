"""No fake staging: production host cannot run fresh-VPS bootstrap."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "infra" / "server" / "KMJ_SERVER_BOOTSTRAP.sh"
DOCTOR = ROOT / "scripts" / "KMJ_NATIVE_STAGE_PREFLIGHT_20261026.py"

spec = importlib.util.spec_from_file_location("kmj_native_stage_doctor", DOCTOR)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NativeStagePreflightContractTests(unittest.TestCase):
    def test_new_vps_bootstrap_blocks_any_existing_production_host_first(self):
        source = BOOTSTRAP.read_text(encoding="utf-8")
        marker = "KMJ_FRESH_SERVER_BOOTSTRAP=BLOCKED_EXISTING_PRODUCTION_HOST"
        self.assertIn(marker, source)
        for condition in (
            "hostname -s",
            "-e /home/kmjprod/current",
            "-L /home/kmjprod/current",
        ):
            self.assertIn(condition, source[:source.index(marker)])
        for mutating_step in (
            "exec > >(tee",
            "timedatectl set-timezone",
            "apt-get",
            "systemctl restart php8.5-fpm",
            "clpctl user:add",
        ):
            self.assertLess(source.index(marker), source.index(mutating_step))

    def test_stage_hostname_classifier(self):
        cases = (
            ("", "MISSING"),
            ("# server_name staging.kmjtechno.com;", "MISSING"),
            ("server_name kmjtechno.com;", "MISSING"),
            ("server_name staging.kmjtechno.com;", "DEDICATED"),
            ("  server_name staging.kmjtechno.com;\n", "DEDICATED"),
            ("server_name staging.kmjtechno.com kmjtechno.com;", "SHARED_OR_DUPLICATED"),
            ("server_name staging.kmjtechno.com;\nserver_name staging.kmjtechno.com;", "SHARED_OR_DUPLICATED"),
        )
        for config, want in cases:
            with self.subTest(config=config):
                self.assertEqual(module.classify_server_names(config), want)

    def test_diagnostics_only_no_bypass_or_mutating_actions(self):
        source = DOCTOR.read_text(encoding="utf-8")
        self.assertIn("FULL_STAGING_READINESS=NOT_YET_PROVEN", source)
        self.assertIn("PRODUCTION_POINTER=UNCHANGED", source)
        self.assertIn("STAGING_DEPLOYED_SHA=NOT_VERIFIED", source)
        self.assertIn("NATIVE_STAGE_INSPECTION=PASS_READ_ONLY", source)
        self.assertIn('parser.add_argument("--inspect"', source)
        self.assertIn("capture_output=True", source)
        self.assertIn("nginx", source)
        for forbidden in ("shell=True", "sudo ", "os.system", "write_text(", "unlink(", "mkdir(", "chmod(", "certbot certonly", "systemctl reload", "rm -rf"):
            self.assertNotIn(forbidden, source)

    def test_target_site_location_is_isolated(self):
        self.assertEqual(str(module.SITE), "/home/kmjstage/htdocs/staging.kmjtechno.com")
        self.assertEqual(str(module.PRODUCTION), "/home/kmjprod/current")


if __name__ == "__main__":
    unittest.main()
