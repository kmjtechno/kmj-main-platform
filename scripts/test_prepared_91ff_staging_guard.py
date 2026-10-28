#!/usr/bin/env python3
"""Offline contract for exact current staging release; cannot deploy."""
from pathlib import Path
import unittest

SOURCE=Path(__file__).parent/"operations"/"activate-prepared-91ff-staging-only-20261028.sh"
SHA="91ff3296597c3901865960d39936816ac9ca4c7a"
PREV="9d15e14e39564ffb1e66085a483feb8331f9718f"

class StagingGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=SOURCE.read_text()

    def test_pinned_identities_and_no_production_change(self):
        text=self.source
        self.assertIn("sha="+SHA,text)
        self.assertIn("old="+PREV,text)
        self.assertIn("DEPLOY_APPROVED_STAGING_ONLY",text)
        self.assertIn("expected_prod=/home/kmjprod/releases/platform-8070dad72c55",text)
        self.assertIn("APP_ENV=staging",text)
        self.assertIn("DB_DATABASE=kmj_stage_2026",text)
        self.assertIn("APPROVED_SHA_CHANGED",text)
        self.assertIn("CONCURRENT_POINTER_CHANGE",text)
        self.assertNotIn("artisan migrate",text)
        self.assertNotIn("systemctl restart",text)

    def test_customer_storage_and_revert_controls(self):
        text=self.source
        for marker in (
           "UPLOAD_RELEASE_BOUND","NEW_UPLOAD_DATA",
           "OLD_PUBLIC_STORAGE_DIRECTORY_REQUIRES_REVIEW",
           "candidate_scaffold_moved=1",
           "CANDIDATE_SCAFFOLD=RESTORED",
           "STAGING_ROLLBACK=RESTORED_PREVIOUS",
           "trap rollback EXIT",
        ):
            self.assertIn(marker,text)
        self.assertNotIn("rm -rf",text)
        self.assertIn("flock -n 9",text)

    def test_root_sha_attestation_and_public_only_permissions(self):
        text=self.source
        for marker in (
          ".kmj-deploy-sha",
          "O_NOFOLLOW",
          "os.O_EXCL",
          "os.fchown(out.fileno(), 0, 0)",
          "attestation_created=1",
          "ATTESTATION=ROLLED_BACK",
          "ATTESTATION=ROOT_OWNED_EXACT_SHA",
          "runuser -u www-data -- test -r",
          "find \"$app/public\" -xdev",
          "ASSET_PARENT_OWNER",
        ):
            self.assertIn(marker,text)
        self.assertNotIn('chmod -R 777',text)
        self.assertNotIn('chmod -R a+r',text)

    def test_authenticated_origin_evidence(self):
        text=self.source
        self.assertIn("staging.kmjtechno.com:443:127.0.0.1",text)
        self.assertIn("STAGING_HEADER_SHA",text)
        self.assertIn("STAGING_HTTP_STATUS",text)
        self.assertIn("KMJ_RELEASE_STAGE_ACTIVATION=PASS_EXACT_SHA_HTTPS",text)

if __name__=="__main__":
    unittest.main()
