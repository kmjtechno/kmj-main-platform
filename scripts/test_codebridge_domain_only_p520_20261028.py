#!/usr/bin/env python3
"""Source-only regression: first-party P520 delivery and trust boundary."""
from pathlib import Path
import hashlib
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/"apps/platform/public"
SCRIPT=PUBLIC/"KMJ-CodeBridge-P520-Connect.ps1"
COMMAND=PUBLIC/"KMJ-CodeBridge-P520-Connect.cmd"
PORTAL=PUBLIC/"codebridge-connect.html"
PIN="07a9478695172587f01bc28076880a845cd7b7917ec6025a13c9316abe0a3e11"
DEVICE="kmj-homeoffice-desktop-5fvjmet"
PROJECT="kmj-calibration-pro"

class DomainOnlyP520Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script=SCRIPT.read_text(encoding="utf-8")
        cls.command=COMMAND.read_text(encoding="utf-8")
        cls.portal=PORTAL.read_text(encoding="utf-8")

    def test_hash_pinned_local_script(self):
        self.assertEqual(hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),PIN)
        self.assertIn(PIN,self.command)
        self.assertLess(self.command.index("Get-FileHash"),self.command.index("Unblock-File"))

    def test_only_website_network_origin(self):
        joined=self.script+self.command+self.portal
        for disallowed in ("raw.githubusercontent.com","github.com/kmjtechno/kmj-codebridge/archive",
                           "ExecutionPolicy Bypass","https://api.github.com","curl | bash"):
            self.assertNotIn(disallowed,joined)
        self.assertIn("https://kmjtechno.com/KMJ-CodeBridge-P520-Connect.ps1",self.command)
        self.assertIn("/api/codebridge/v1/device-enrollments/readiness",self.script)
        self.assertIn("/agent/health",self.script)
        self.assertIn("/KMJ-CodeBridge-P520-Connect.cmd",self.portal)

    def test_exact_identity_and_existing_local_runtime(self):
        for v in ("DESKTOP-5FVJMET",DEVICE,PROJECT,"0a1fcd6804a70e915ecf66df0d4a7786f5270f02"):
            self.assertIn(v,self.script)
        self.assertIn("ONE-CLICK-AGENT-AUTOCONNECT.ps1",self.script)
        self.assertIn("-Device HomeOffice",self.script)
        self.assertIn("PINNED_LOCAL_RUNTIME_NOT_FOUND",self.script)
        self.assertIn("MULTIPLE_PINNED_RUNTIMES_NEED_REVIEW",self.script)

    def test_fail_closed_public_readiness_and_gateway_auth(self):
        for v in ("SERVER_UPDATE_REQUIRED_404","PAIRING_CONFIG_NOT_READY_503",
                  "DOMAIN_PAIRING_CONTRACT_NOT_READY","PUBLIC_AGENT_AUTH_NOT_ENFORCED",
                  "PUBLIC_AGENT_ROUTE_NOT_READY","OWNER_APPROVAL_OR_LOCAL_RECONNECT_PENDING"):
            self.assertIn(v,self.script)
        self.assertIn("KMJ_DOMAIN_CONNECT=LOCAL_FLOW_COMPLETE_ACCOUNT_READY_MUST_BE_VERIFIED",self.script)
        self.assertIn("Owner approval",self.portal) if "Owner approval" in self.portal else self.assertIn("Approve",self.portal)

    def test_never_overwrites_credentials_or_calls_live_prod(self):
        for prohibited in ("Set-Content","Remove-Item","Stop-Service","Restart-Service",
                           "Set-ExecutionPolicy","git clone","git pull","npm install"):
            self.assertNotIn(prohibited,self.script)
        self.assertNotIn("token" + "=", self.command.lower())
        self.assertIn("CREDENTIALS_EXPORTED=NO",self.script)
        self.assertIn("noindex, nofollow",self.portal)

if __name__=="__main__":
    unittest.main()
