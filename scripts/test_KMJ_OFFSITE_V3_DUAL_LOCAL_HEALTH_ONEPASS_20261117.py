"""Fixture-only tests for the V3 dual-local health helper health-file pin.

No real /usr/local, /var/backups, systemd or root access is used. The health
file text below is the exact owner-edited /usr/local/sbin/kmj-elite-health-check
observed on 2026-11-24 (36 lines, 2219 bytes). The test proves that text hashes
to the pin and passes health_contract(), that the previous 1840-byte version
no longer passes, and that the real production failure (file larger than the
old 2048-byte limit) is the one this change fixes.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SRC = Path(__file__).with_name("KMJ_OFFSITE_V3_DUAL_LOCAL_HEALTH_ONEPASS_20261117.py")
spec = importlib.util.spec_from_file_location("kmj_v3_health_onepass", SRC)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

HEAD = [
    "#!/usr/bin/env bash",
    "set -Eeuo pipefail",
    'test "$(hostname)" = KMJ-elite',
    "hostname -I | tr ' ' '\\n' | grep -Fxq 150.242.200.81",
    "for s in ssh nginx php8.4-fpm postgresql redis-server kmj-main-platform-queue.service kmj-codebridge-gateway-stage.service kmj-codebridge-kmj-main-platform.service kmj-desktop-commander.service; do",
    ' systemctl is-active --quiet "$s" || { echo "UNHEALTHY_SERVICE=$s";exit 5; }',
    "done",
    "nginx -t >/dev/null 2>&1",
    "code=$(curl --silent --show-error --max-time 12 --resolve kmjtechno.com:443:127.0.0.1 -o /dev/null -w '%{http_code}' https://kmjtechno.com/login)",
    'test "$code" = 200 || { echo "UNHEALTHY_PUBLIC_LOGIN_$code";exit 6; }',
    "code=$(curl --silent --show-error --max-time 8 -o /dev/null -w '%{http_code}' http://127.0.0.1:18787/healthz)",
    'test "$code" = 200 || { echo "UNHEALTHY_GATEWAY_$code";exit 7; }',
    "python3 - <<'PY'",
    "import json",
    "with open('/etc/kmj-codebridge-main-platform/agent.json',encoding='utf-8') as f:",
    "    c=json.load(f)",
    "assert c.get('id')=='kmj-elite-main-platform'",
    "assert c.get('gateway')=='http://127.0.0.1:18787'",
    "assert [p.get('id') for p in c.get('projects',[])]==['kmj-main-platform']",
    "PY",
    "openssl x509 -in /etc/letsencrypt/live/kmjtechno.com/fullchain.pem -checkend 1209600 -noout >/dev/null",
    "grep -qx 'DB_DATABASE=kmj_platform_final_cutover_20261011' /home/kmjprod/shared/.env",
    "runuser -u postgres -- psql -X -qAtd kmj_platform_final_cutover_20261011 -c 'SELECT 1' | grep -qx 1",
    "systemctl is-active --quiet kmj-main-platform-scheduler.timer",
    "find /var/backups/kmj-elite-daily -mindepth 2 -maxdepth 2 -name platform.dump -type f -mtime -2 | grep -q .",
]
OLD_OFFSITE = ["systemctl is-active --quiet kmj-elite-offsite-backup.timer"]
NEW_OFFSITE = [
    "if systemctl is-active --quiet kmj-elite-offsite-backup.timer; then",
    '  echo "KMJ_OFFSITE_TIMER=ACTIVE; DR=NOT_VERIFIED"',
    'elif [[ "$(systemctl is-active kmj-elite-offsite-backup.timer 2>/dev/null || true)" == "inactive" && "$(systemctl is-enabled kmj-elite-offsite-backup.timer 2>/dev/null || true)" == "disabled" ]]; then',
    '  echo "KMJ_OFFSITE_TIMER=DISABLED_BY_OWNER; DR=NOT_VERIFIED"',
    "else",
    '  echo "UNHEALTHY_OFFSITE_TIMER_STATE"',
    "  exit 8",
    "fi",
]
TAIL = [
    "test -s /root/kmj-bootstrap/offsite-age-recipients.txt",
    "find /var/backups/kmj-elite-offsite-encrypted -mindepth 1 -maxdepth 1 -name '20*.tar.age' -type f -mtime -2 | grep -q .",
    "echo KMJ_ELITE_HEALTH_PASS",
]
NEW = ("\n".join(HEAD + NEW_OFFSITE + TAIL) + "\n").encode()
OLD = ("\n".join(HEAD + OLD_OFFSITE + TAIL) + "\n").encode()
OLD_SHA = "2a8cb007acaea2ef8d240ee82a95b13314799dcea36c0cac594e7e5d32acca20"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class HealthPinTests(unittest.TestCase):
    def test_fixtures_are_the_two_real_files(self):
        self.assertEqual((len(NEW.splitlines()), len(NEW), sha(NEW)),
                         (36, 2219, h.HEALTH_SHA))
        self.assertEqual((len(OLD.splitlines()), len(OLD), sha(OLD)),
                         (29, 1840, OLD_SHA))

    def test_pin_constants_match_the_new_file(self):
        self.assertEqual(h.HEALTH_LINES, 36)
        self.assertEqual(h.HEALTH_BYTES, 2219)
        self.assertGreaterEqual(h.HEALTH_MAX_BYTES, h.HEALTH_BYTES)
        self.assertLessEqual(h.HEALTH_MAX_BYTES, 4096)

    def _contract(self, body: bytes):
        seen = {}

        def fake_private_bytes(path, digest, *, uid=None, maximum=131072):
            seen.update(path=path, digest=digest, uid=uid, maximum=maximum)
            return body

        regular = os.stat_result((0o100600, 1, 1, 1, 0, 0, 10, 0, 0, 0))
        with mock.patch.object(h, "private_bytes", fake_private_bytes), \
                mock.patch.object(h.os, "lstat", return_value=regular):
            return h.health_contract(), seen

    def test_contract_accepts_the_current_health_file(self):
        ok, seen = self._contract(NEW)
        self.assertTrue(ok)
        self.assertEqual(seen["path"], h.HEALTH)
        self.assertEqual(seen["digest"], h.HEALTH_SHA)
        self.assertEqual(seen["uid"], 0)
        self.assertEqual(seen["maximum"], h.HEALTH_MAX_BYTES)

    def test_contract_rejects_the_previous_file(self):
        with self.assertRaises(h.Deny) as e:
            self._contract(OLD)
        self.assertEqual(str(e.exception), "HEALTH_PINNED_SOURCE_CHANGED")

    def test_contract_rejects_a_changed_line_count_or_size(self):
        with self.assertRaises(h.Deny):
            self._contract(NEW + b"# extra\n")
        with self.assertRaises(h.Deny):
            self._contract(NEW.replace(b"echo KMJ_ELITE_HEALTH_PASS\n", b""))

    def test_line_offsets_point_at_the_expected_commands(self):
        lines = NEW.decode().splitlines()
        self.assertIn("kmj-elite-daily", lines[h.HEALTH_DAILY_LINE])
        self.assertTrue(lines[h.HEALTH_METADATA_LINE].startswith("test -s /"))
        self.assertIn("kmj-elite-offsite-encrypted", lines[h.HEALTH_VAULT_LINE])

    def test_real_private_bytes_fixes_the_production_failure(self):
        """On 2026-11-22 the file (2219 bytes) exceeded the old 2048 limit."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "health"
            path.write_bytes(NEW)
            path.chmod(0o600)
            uid = os.geteuid()
            with self.assertRaises(h.Deny) as old_limit:
                h.private_bytes(path, h.HEALTH_SHA, uid=uid, maximum=2048)
            self.assertEqual(str(old_limit.exception), "SOURCE_METADATA_UNTRUSTED")
            self.assertEqual(
                h.private_bytes(path, h.HEALTH_SHA, uid=uid, maximum=h.HEALTH_MAX_BYTES),
                NEW)
            path.write_bytes(NEW.replace(b"exit 8", b"exit 0"))
            path.chmod(0o600)
            with self.assertRaises(h.Deny) as tampered:
                h.private_bytes(path, h.HEALTH_SHA, uid=uid, maximum=h.HEALTH_MAX_BYTES)
            self.assertEqual(str(tampered.exception), "SOURCE_SHA_UNVERIFIED")

    def test_group_or_world_writable_health_file_is_still_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "health"
            path.write_bytes(NEW)
            path.chmod(0o620)
            with self.assertRaises(h.Deny) as e:
                h.private_bytes(path, h.HEALTH_SHA, uid=os.geteuid(),
                                maximum=h.HEALTH_MAX_BYTES)
            self.assertEqual(str(e.exception), "SOURCE_METADATA_UNTRUSTED")

    def test_helper_still_never_touches_the_health_source(self):
        text = SRC.read_text()
        for forbidden in ("HEALTH.write", "os.replace(HEALTH", "chmod(HEALTH", "unlink(HEALTH"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
