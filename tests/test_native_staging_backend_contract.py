"""Fail-closed checks for the native KMJ-elite PHP8.4/PostgreSQL stage."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/"infra/server/KMJ_NATIVE_STAGE_BACKEND_PREPARE.sh"
SCRIPT=FILE.read_text(encoding="utf-8")

class StageBackendSafety(unittest.TestCase):
    def test_shell_syntax(self):
        subprocess.run(["bash", "-n", str(FILE)], check=True, timeout=10)

    def test_non_kmj_host_has_no_side_effects(self):
        # Hosted CI is NOT KMJ-elite. This must fail before writes or file checks.
        result=subprocess.run(["bash", str(FILE), "--inspect"], capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("KMJ_STAGE_BACKEND=BLOCKED", result.stderr)

    def test_existing_prod_and_source_are_not_reused_or_modified(self):
        for text in ("PRODUCTION_BASELINE_MISSING", "STAGING_SITE_ALREADY_PRESENT",
                     "STAGING_RELEASE_ALREADY_PRESENT","STAGING_FPM_POOL_ALREADY_PRESENT",
                     "STAGING_SECRETS_ALREADY_PRESENT","EXISTING_STAGE_USER_UNSAFE",
                     "STAGING_DB_OR_ROLE_ALREADY_PRESENT","STAGING_DOMAIN_NOT_ISOLATED",
                     "STAGING_PLACEHOLDER_NOT_PRESENT","PRODUCTION_OR_NGINX_CHANGED")
        self.assertIn("STAGING_VHOST_SYMLINK_OUTSIDE_APPROVED_PATH",SCRIPT)
        self.assertIn("/etc/nginx/sites-available/staging.kmjtechno.com.conf",SCRIPT)
        self.assertIn("! -L \"$vhost_target\"",SCRIPT):
            self.assertIn(text, SCRIPT)
        self.assertIn('readlink -f /home/kmjprod/current', SCRIPT)
        self.assertIn("sha256sum \"$VHOST\"", SCRIPT)
        for forbidden in ("git reset --hard", "git clean", "rm -rf", "DROP DATABASE",
                          "DROP ROLE", "apt-get", "ufw ", "certbot", "nginx -s reload",
                          "systemctl restart", "clpctl", "systemctl reload nginx"):
            self.assertNotIn(forbidden, SCRIPT)

    def test_exact_approved_sha_only(self):
        self.assertIn("refs/heads/staging-approved", SCRIPT)
        self.assertIn("CURRENT_STAGING_APPROVED_SHA_MISMATCH", SCRIPT)
        self.assertIn("FINAL_APPROVED_SOURCE_UNREACHABLE", SCRIPT)
        self.assertIn("PROMOTION_MOVED_DURING_PREPARE", SCRIPT)
        self.assertIn('checkout --quiet --detach "$SHA"', SCRIPT)
        self.assertIn("OWNER_CONFIRMATION_REQUIRED", SCRIPT)
        self.assertIn("PREPARE_ISOLATED_STAGING", SCRIPT)
        self.assertIn("flock -n 9", SCRIPT)

    def test_restrict_external_effects_and_secrets(self):
        for item in ("APP_DEBUG", "false", "PUBLIC_INDEXING_ENABLED",
                     "MAIL_MAILER", "log", "SESSION_COOKIE",
                     "CODEBRIDGE_OAUTH_ENABLED","kmj_stage_2026",
                     "kmjstage_2026","NOSUPERUSER","NOCREATEDB",
                     "NOCREATEROLE", "NO_REPLICATION", "php8.4 artisan migrate"):
            if item == "NO_REPLICATION":
                item="NOREPLICATION"
            self.assertIn(item, SCRIPT)
        self.assertIn("DB_PASSWORD", SCRIPT)
        self.assertIn('chmod 0600 "$CRED"', SCRIPT)
        self.assertIn("p.chmod(0o600)", SCRIPT)
        self.assertIn("php-fpm8.4 -t", SCRIPT)
        self.assertIn("systemctl reload php8.4-fpm", SCRIPT)
        self.assertIn("STAGING_HTTP=STILL_503_NOT_LIVE", SCRIPT)
        self.assertIn("PRODUCTION_POINTER=UNCHANGED", SCRIPT)

    def test_only_new_pool_and_isolated_staging_paths(self):
        self.assertIn("/etc/php/8.4/fpm/pool.d/kmjstage.conf", SCRIPT)
        self.assertIn("listen = /run/php/kmjstage-php84-fpm.sock", SCRIPT)
        self.assertIn("listen.owner = www-data", SCRIPT)
        self.assertIn("SITE_LINK=/home/kmjstage/htdocs/staging.kmjtechno.com", SCRIPT)
        self.assertIn("production pointer", SCRIPT)
        self.assertNotIn("php8.5", SCRIPT)

if __name__=="__main__":
    unittest.main()
