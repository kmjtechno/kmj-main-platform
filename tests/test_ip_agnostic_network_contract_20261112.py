"""Static no-network IP-independent origin and pinned SSH safety contract."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUTOPILOT = ROOT / "scripts/operations/kmj-origin-ip-autopilot-20261112.py"
WORKFLOW = ROOT / ".github/workflows/staging-tls-repair-execute.yml"
EXTERNAL = ROOT / ".github/workflows/staging-external-tls-sha-evidence.yml"
HOSTKEY = ROOT / "infra/server/trust/kmj-elite-staging-known_hosts"
ACME = ROOT / "infra/server/KMJ_NATIVE_STAGE_ACME_VHOST.sh"
SERVICE = ROOT / "infra/server/systemd/kmj-ip-autopilot.service"
TIMER = ROOT / "infra/server/systemd/kmj-ip-autopilot.timer"
TUNNEL = ROOT / "infra/server/cloudflared/kmj-elite-tunnel.example.yml"
TUNNEL_SERVICE = ROOT / "infra/server/systemd/cloudflared-kmj-elite.example.service"

def contents(p):
    return p.read_text(encoding="utf-8")

class IPIndependenceContract(unittest.TestCase):
    def test_exact_six_dns_names_never_accept_caller_selected_scope(self):
        s = contents(AUTOPILOT)
        for expected in ("kmjtechno.com", "www.kmjtechno.com",
                         "staging.kmjtechno.com", "cloudos.kmjtechno.com",
                         "mail.kmjtechno.com", "elite-ssh.kmjtechno.com"):
            self.assertIn(expected, s)
        self.assertIn("EXPECTED_HOSTS = WEB_HOSTS + (MAIL_HOST, SSH_HOST)", s)
        self.assertIn('"direct_only"', s)
        self.assertIn('names = EXPECTED_HOSTS if mode == "ddns" else (MAIL_HOST, SSH_HOST)', s)
        self.assertNotIn("mail_only", s)

    def test_staging_web_may_be_proxy_but_ssh_requires_single_direct_ip(self):
        workflow = contents(WORKFLOW)
        self.assertIn("SSH_HOST: 'elite-ssh.kmjtechno.com'", workflow)
        self.assertIn("StrictHostKeyChecking=yes", workflow)
        self.assertIn("UserKnownHostsFile=", workflow)
        self.assertIn("HOST_KEY_NOT_PINNED", workflow)
        self.assertIn("ssh_ips", workflow)
        self.assertIn(" -eq 1 ", workflow)
        self.assertIn("resolved", workflow)
        self.assertIn(" -le 8 ", workflow)
        self.assertNotIn("150.242.200.81", workflow)
        self.assertNotIn("StrictHostKeyChecking=no", workflow)
        self.assertNotIn("curl -k", workflow)
        self.assertEqual(contents(HOSTKEY).strip(),
           "elite-ssh.kmjtechno.com ssh-ed25519 "
           "AAAAC3NzaC1lZDI1NTE5AAAAINZMT7YHsS5qRX/ciXTbLxKZVCgpJS7m/L9Nwgr3RNZS")

    def test_external_tls_and_acme_do_not_pin_ephemeral_ip(self):
        external = contents(EXTERNAL)
        acme = contents(ACME)
        for raw in (external, acme):
            self.assertNotIn("150.242.200.81", raw)
            self.assertIn("ipaddress.IPv4Address", raw)
            self.assertIn("addr.is_global", raw)
            self.assertNotIn("--insecure", raw)
        self.assertIn(" -le 8 ", external)
        self.assertIn("https://ipv4.icanhazip.com", acme)
        self.assertIn("PRODUCTION_POINTER_CHANGED", acme)

    def test_tunnel_has_strict_local_https_and_nonprod_canary(self):
        config = contents(TUNNEL)
        for host in ("kmjtechno.com", "www.kmjtechno.com",
                     "staging.kmjtechno.com", "cloudos.kmjtechno.com",
                     "tunnel-canary.kmjtechno.com"):
            self.assertIn("hostname: " + host, config)
        self.assertEqual(config.count("noTLSVerify: false"), 5)
        self.assertIn("httpHostHeader: kmjtechno.com", config)
        self.assertTrue(config.rstrip().endswith("service: http_status:404"))
        self.assertNotIn("noTLSVerify: true", config)
        self.assertNotIn("token: ", config)

    def test_cloudflared_token_file_not_embedded_or_on_argv(self):
        service = contents(TUNNEL_SERVICE)
        self.assertIn("cloudflared --no-autoupdate tunnel run --token-file", service)
        self.assertIn("/etc/cloudflared/kmj-elite-ip-independent.token", service)
        self.assertIn("ProtectSystem=strict", service)
        self.assertIn("NoNewPrivileges=true", service)
        self.assertNotIn(" --token ", service)
        self.assertNotIn("Environment=TUNNEL_TOKEN", service)

    def test_legacy_mail_stage_only_preflight_tracks_current_egress(self):
        for path in (
            ROOT / "scripts/operations/stage-existing-kmj2026-mail-20261021.sh",
            ROOT / "scripts/operations/stage-selfhosted-outbound-mail-20261021.sh",
        ):
            script = contents(path)
            self.assertNotIn("IP=150.242.200.81", script)
            self.assertNotIn("103.212.136.154", script)
            self.assertIn("https://api.ipify.org", script)
            self.assertIn("https://ipv4.icanhazip.com", script)
            self.assertIn("PUBLIC_IP_CONSENSUS_FAILED", script)
            self.assertIn("PUBLIC_IP_NOT_GLOBAL", script)
            self.assertIn("mail_ips", script)
            self.assertIn("--noproxy", script)
            self.assertIn("OWNER", script.upper())

    def test_autopilot_read_only_inspect_and_zero_privilege_escalation(self):
        s = contents(AUTOPILOT)
        service = contents(SERVICE)
        timer = contents(TIMER)
        self.assertIn("RefuseRedirect", s)
        self.assertIn("SPF_POLICY_UNREVIEWED", s)
        self.assertIn('exact_mode=0o600', s)
        self.assertIn("PRIVATE_FILE_RACE", s)
        self.assertIn("origin_https(ip, mode=mode)", s)
        self.assertNotIn("subprocess.Popen", s)
        self.assertNotIn("shell=True", s)
        self.assertIn("Type=oneshot", service)
        self.assertIn("TimeoutStartSec=300", service)
        self.assertIn("ProtectSystem=strict", service)
        self.assertIn("CapabilityBoundingSet=", service)
        self.assertIn("OnUnitInactiveSec=5min", timer)
        self.assertIn("Unit=kmj-ip-autopilot.service", timer)

if __name__ == "__main__":
    unittest.main()
