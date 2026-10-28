#!/usr/bin/env python3
"""CodeBridge first-party P520 domain-only installer source safety."""
import hashlib
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/"apps/platform/public"
PIN="ebe4a049b107a6cde710ffd65f5f32140c4bf8763e9535be4d1cfb63512f2495"

class P520DomainConnectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cmd=(PUBLIC/"KMJ-CodeBridge-P520-Connect.cmd").read_text()
        cls.ps=(PUBLIC/"KMJ-CodeBridge-P520-Connect.ps1").read_text()
        cls.html=(PUBLIC/"codebridge-connect.html").read_text()

    def test_exact_script_hash_and_windows_scope(self):
        self.assertEqual(hashlib.sha256((PUBLIC/"KMJ-CodeBridge-P520-Connect.ps1").read_bytes()).hexdigest(),PIN)
        self.assertIn(PIN,self.cmd)
        self.assertIn("DESKTOP-5FVJMET",self.ps)
        self.assertIn("kmj-homeoffice-desktop-5fvjmet",self.ps)
        self.assertIn("kmj-calibration-pro",self.ps)
        self.assertIn("0a1fcd6804a70e915ecf66df0d4a7786f5270f02",self.ps)
        self.assertLess(self.cmd.index("Get-FileHash"),self.cmd.index("Unblock-File"))

    def test_staged_local_runtime_discovery_is_precise(self):
        import re
        pattern = r"^CodeBridge-HomeOffice(?:-[a-fA-F0-9-]+|-stage-[a-fA-F0-9]{32})?$"
        self.assertIn(pattern, self.ps)
        for folder in (
            "CodeBridge-HomeOffice",
            "CodeBridge-HomeOffice-0a1fcd6804a70e915ecf66df0d4a7786f5270f02",
            "CodeBridge-HomeOffice-stage-81b63009c6f74e9dae97ac15fd9515ca",
        ):
            self.assertIsNotNone(re.fullmatch(pattern, folder))
        for folder in (
            "CodeBridge-HomeOffice-stage",
            "CodeBridge-HomeOffice-stage-other",
            "CodeBridge-HomeOffice-stage-" + "a" * 31,
            "CodeBridge-HomeOffice-stage-" + "a" * 33,
            "CodeBridge-HomeOffice-stage-" + "z" * 32,
            "CodeBridge-HomeOffice-stage-" + "a" * 32 + "-extra",
        ):
            self.assertIsNone(re.fullmatch(pattern, folder))
        self.assertIn("MULTIPLE_PINNED_RUNTIMES_NEED_REVIEW", self.ps)
        self.assertIn("REPARSE_POINT_DENIED", self.ps)
        self.assertIn("PINNED_LOCAL_RUNTIME_NOT_FOUND", self.ps)

    def test_only_official_domain_delivery(self):
        self.assertIn("https://kmjtechno.com/KMJ-CodeBridge-P520-Connect.ps1",self.cmd)
        self.assertIn("/KMJ-CodeBridge-P520-Connect.cmd",self.html)
        self.assertIn("/api/codebridge/v1/device-enrollments/readiness",self.ps)
        self.assertIn("/agent/health",self.ps)
        self.assertIn("ONE-CLICK-AGENT-AUTOCONNECT.ps1",self.ps)
        self.assertIn("-Device HomeOffice",self.ps)
        for bad in ("raw.githubusercontent.com","https://api.github.com",
                    "github.com/kmjtechno/kmj-codebridge/archive","ExecutionPolicy Bypass",
                    "git clone","npm install","curl | bash"):
            self.assertNotIn(bad,self.cmd+self.ps+self.html)

    def test_preflight_security_and_protected_public_identity(self):
        self.assertIn("SERVER_UPDATE_REQUIRED_404",self.ps)
        self.assertIn("PAIRING_CONFIG_NOT_READY_503",self.ps)
        self.assertIn("PUBLIC_AGENT_AUTH_NOT_ENFORCED",self.ps)
        self.assertIn("OWNER_APPROVAL_OR_LOCAL_RECONNECT_PENDING",self.ps)
        self.assertIn("CREDENTIALS_EXPORTED=NO",self.ps)
        self.assertIn("noindex, nofollow",self.html)
        self.assertNotIn("kmj-homeoffice-desktop-5fvjmet",self.html)
        self.assertNotIn("DESKTOP-5FVJMET",self.html)
        self.assertNotIn("git clone",self.ps)

if __name__=="__main__":
    unittest.main()
