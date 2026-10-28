#!/usr/bin/env python3
"""Static safeguards around exact release staging-only atomic switch."""
from pathlib import Path
import re
import unittest

SCRIPT=Path(__file__).parent/"operations"/"activate-prepared-ad4c-staging-only-20261028.sh"
SHA="ad4cfa68291ec6a05e88f30ed0a93b2d15af40fe"
OLD="9d15e14e39564ffb1e66085a483feb8331f9718f"

class PreparedStageContract(unittest.TestCase):
    def test_pins_release_and_rollback_origin(self):
        raw=SCRIPT.read_text()
        self.assertIn("sha="+SHA,raw)
        self.assertIn("old="+OLD,raw)
        self.assertIn("DEPLOY_APPROVED_STAGING_ONLY",raw)
        self.assertIn("STAGING-APPROVED",raw.upper())
        self.assertIn("PROD_POINTER",raw)
        self.assertIn("CONCURRENT_NGINX_CHANGE",raw)

    def test_staging_storage_continuity_preserved(self):
        raw=SCRIPT.read_text()
        self.assertIn("UPLOAD_TARGET",raw)
        self.assertIn("public_action=absent",raw)
        self.assertIn("OLD_PUBLIC_STORAGE_DIRECTORY_REQUIRES_REVIEW",raw)
        self.assertIn('if [[ "$public_action" == link ]]; then',raw)
        self.assertIn("candidate_scaffold_moved=1",raw)
        self.assertIn("KMJ_AD4C_CANDIDATE_SCAFFOLD=RESTORED",raw)
        self.assertIn("candidate_public_link_created=1",raw)
        self.assertIn("completed=1",raw)
        self.assertIn("NEW_UPLOAD_DATA",raw)
        self.assertIn("app.pre-stage-ad4c",raw)
        self.assertIn("NEW_ARTWORK_CONTINUITY",raw)
        self.assertNotIn("rm -rf",raw)
        self.assertNotIn("mkfs",raw)

    def test_race_safe_nginx_and_rollback(self):
        raw=SCRIPT.read_text()
        self.assertIn("flock -n 9",raw)
        self.assertIn("trap rollback EXIT",raw)
        self.assertIn('install -m 0644 "$work/original.conf" "$target"',raw)
        self.assertIn('mv -Tf "$tmp_link" "$link"',raw)
        self.assertIn("nginx -t",raw)
        self.assertIn("STAGING_HTTPS",raw)
        self.assertIn("HEADER_SHA_MISMATCH",raw)
        self.assertIn("127.0.0.1",raw)
        self.assertNotIn("curl -k",raw)
        self.assertNotIn("systemctl stop nginx",raw)

    def test_only_stage_site_is_mutable(self):
        raw=SCRIPT.read_text()
        self.assertIn("link=/home/kmjstage/htdocs/staging.kmjtechno.com",raw)
        self.assertIn("conf=/etc/nginx/sites-enabled/staging.kmjtechno.com.conf",raw)
        self.assertIn("prod=/home/kmjprod/current",raw)
        for token in (
            "ln -s ", "mv -Tf ", "install -m 0644 ", "systemctl reload nginx",
        ):
            self.assertIn(token,raw)
        self.assertNotIn("APP_ENV=production",raw)
        self.assertNotIn("artisan migrate",raw)

if __name__=="__main__":
    unittest.main()
