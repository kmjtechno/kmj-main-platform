"""P0 isolated staging ACME vhost must be safe on a live production host."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "infra/server/KMJ_NATIVE_STAGE_ACME_VHOST.sh"
S = SCRIPT.read_text(encoding="utf-8")


class StagingAcmeVhostContract(unittest.TestCase):
    def test_guards_precede_any_side_effect(self):
        self.assertIn('hostname -s', S)
        self.assertIn('/home/kmjprod/current', S)
        self.assertIn('WRONG_HOST_OR_USER', S)
        self.assertIn('NGINX_NOT_HEALTHY', S)
        self.assertIn('DNS_OR_SERVER_IDENTITY_MISMATCH', S)
        self.assertLess(S.index('WRONG_HOST_OR_USER'), S.index('install -d -o root'))
        self.assertLess(S.index('DNS_OR_SERVER_IDENTITY_MISMATCH'), S.index('install -d -o root'))

    def test_no_existing_prod_or_stage_path_is_overwritten(self):
        self.assertIn('CONFIG_ALREADY_EXISTS', S)
        self.assertIn('STAGING_SERVER_ALREADY_DEFINED', S)
        self.assertIn('CONFIG_DIRECTORY_UNSAFE', S)
        self.assertIn('STAGING_PATH_SYMLINK', S)
        self.assertIn('STAGING_SITE_REQUIRES_REVIEW', S)
        self.assertIn('STAGING_SITE_REQUIRES_REVIEW', S.replace('EXISTING_STAGE_SITE_REQUIRES_REVIEW', 'STAGING_SITE_REQUIRES_REVIEW'))
        self.assertIn('install -o root -g root -m 0644 "$tmp" "$conf"', S)
        self.assertNotIn('tee /etc/nginx/nginx.conf', S)

    def test_only_new_stage_http_site_no_laravel_claim(self):
        match = re.search(r"cat >\"\$tmp\" <<'NGINX'\n(.*?)\nNGINX\n", S, re.S)
        self.assertIsNotNone(match)
        nginx = match.group(1)
        self.assertIn('server_name staging.kmjtechno.com;', nginx)
        self.assertIn('location ^~ /.well-known/acme-challenge/', nginx)
        self.assertIn('try_files $uri =404;', nginx)
        self.assertIn('return 503;', nginx)
        self.assertNotIn('fastcgi_pass', nginx)
        self.assertNotIn('listen 443', nginx)
        self.assertNotIn('server_name kmjtechno.com;', nginx)
        self.assertIn('STAGING_LARAVEL=NOT_INSTALLED', S)
        self.assertIn('STAGING_TLS=NOT_ISSUED', S)

    def test_owner_authorization_and_rollback(self):
        self.assertIn('STAGING_HTTP_ONLY', S)
        self.assertIn('</dev/tty', S)
        self.assertIn('flock -n 9', S)
        self.assertIn('trap rollback EXIT', S)
        self.assertIn('expected_conf_hash', S)
        self.assertIn('ROLLED_BACK_OR_NEEDS_OPERATOR_REVIEW', S)
        self.assertIn('PRODUCTION_POINTER_CHANGED', S)
        self.assertIn('nginx -t', S)
        self.assertIn('systemctl reload nginx', S)

    def test_no_unsafe_upgrade_or_fake_full_deployment(self):
        for prohibited in (
            'systemctl restart', 'apt-get', 'clpctl', 'certbot certonly',
            'git reset --hard', 'nginx -T | grep -q', 'curl -k',
            'rm -rf', 'psql -c', 'php artisan migrate', 'ufw ',
        ):
            self.assertNotIn(prohibited, S)

    def test_host_origin_and_acme_local_probe(self):
        self.assertIn('103.212.136.154', S)
        self.assertIn('https://api.ipify.org', S)
        self.assertIn('getent ahostsv4', S)
        self.assertIn("--noproxy '*'", S)
        self.assertIn('KMJ_STAGE_ACME_PROBE', S)


if __name__ == "__main__":
    unittest.main()
