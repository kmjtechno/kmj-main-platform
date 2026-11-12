# KMJ-elite: IP-independent public origin (12 Nov 2026)

## Desired result

When the hosting provider changes KMJ-elite's public IPv4, routine IP
rotations must require no changes to GitHub workflows or application
configuration, and no manual Cloudflare DNS editing.

Two compatible layers are staged; **neither is active on KMJ-elite**. The
Cloudflare remotely managed Tunnel resource and its four safe HTTPS ingress
rules are already created in the account (ID
`b18c637f-2700-442a-a12e-b225c43dfc72`), but cloudflared is not
installed/verified and **live DNS is unchanged**:

1. **Preferred web path: Cloudflare Tunnel.** A locally running
   \`cloudflared\` daemon connects outbound to Cloudflare and publishes
   \`kmjtechno.com\`, \`www.kmjtechno.com\`, \`staging.kmjtechno.com\`
   and \`cloudos.kmjtechno.com\` to the local Nginx HTTPS origin.
   DNS becomes CNAMEs to the named Tunnel rather than public server A records.
   A public-IP change does not require DNS updates. TLS from cloudflared to
   Nginx uses a validated certificate with per-hostname SNI.
2. **Fallback/direct-mail path: least-privilege Cloudflare DNS reconciling
   agent.** A hardened systemd one-shot/timer discovers the current
   server *outbound* IPv4 using two independent HTTPS sources, requires exact
   agreement and globally routable IPv4, then confirms local origin HTTPS via
   direct \`curl --resolve\` before updating only five allowlisted DNS-only
   A records and the exact pre-existing SPF policy. After Tunnel cutover,
   change mode to \`mail_only\`: web CNAMEs are never touched again; only
   \`mail.kmjtechno.com\` A and the reviewed SPF token remain dynamic.

Neither approach assumes that detecting outbound IP proves inbound reachability.
The direct-DNS mode fails closed when origin HTTPS identity or network cannot
be established. Failing closed can require host-level investigation if the
provider uses asymmetric NAT/firewall, an outage or different inbound/outbound IP.

## Cloudflare audit before deployment (12 November)

Five distinct DNS-only A records (main/www/staging/cloudos/mail) point to
\`150.242.200.81\`. The only SPF TXT is exactly
\`v=spf1 ip4:150.242.200.81 include:_spf.mx.cloudflare.net ~all\`.
Cloudflare Email Routing owns MX records. The unrelated
\`host.kmjtechno.com\` and \`authsp.kmjtechno.com\` use a DIFFERENT IP
and must not be modified. **The new remotely managed Cloudflare Tunnel exists with configured HTTPS
ingress, but has no verified connected daemon or live DNS routes.**

## Once-only secure provisioning, authorized root operator required

There is **no arbitrary root-shell CodeBridge profile**. This branch does not
silently install software, mint tokens, or change live DNS.

1. Review and run the source-contract and offline Python tests on the
   **exact reviewed GitHub commit**. Pin the content SHA-256 before installing.
   Review the real on-host executable, systemd unit and the SSH public host
   identity (KMJ-elite ED25519, not a public IP).
2. Create a Cloudflare **zone-scoped API token** with only DNS Read and DNS
   Edit on the KMJ zone. Put it on KMJ-elite at
   \`/etc/kmj-ip-autopilot/cloudflare-token\` as root:root 0600, not in
   GitHub, chat, GitHub Actions secrets or user environment.
   \`/etc/kmj-ip-autopilot/config.json\` is root:root 0600 and must contain
   only \`{"zone_id":"<32 lowercase hex>","mode":"ddns"}\`.
   No arbitrary managed-record list or API URL is accepted.
3. Copy the reviewed Python file to
   \`/usr/local/libexec/kmj-origin-ip-autopilot.py\` (root:root 0500),
   verify exact SHA-256, install the two pinned systemd unit/timer files
   in \`/etc/systemd/system\`, run \`systemd-analyze verify\`, and run
   \`python3 -I -B ... --inspect\` first. **Inspect makes no DNS writes.**
4. Only after the current five-record Cloudflare snapshot and all origin
   HTTPS preflights PASS, activate \`kmj-ip-autopilot.timer\`. The timer
   retries a failed check later; a periodic run is a one-shot and never
   restarts Nginx/Postfix/PHP/CloudOS or the production release pointer.
5. Configure a named Cloudflare Tunnel with separately protected credentials
   and \`cloudflared\`. First demonstrate **all four** routes on a
   nonproduction canary hostname with Full (strict) TLS and correct origin
   SNI. Then migrate each public web hostname to the named Tunnel using
   Cloudflare-controlled CNAMEs, with independent HTTPS/browser validation.
   Only after the tunnel cutover set \`config.json\` to \`mail_only\`:
   the reconciler must stop managing web A records. Existing staging
   TLS workflow uses DNS **hostname + pinned SSH host key**, not rotating IP.
6. Preserve and validate rollback of Cloudflare DNS, including HTTP/S and
   staging. Never turn off SSH StrictHostKeyChecking or enable
   \`noTLSVerify\` to make a broken tunnel look healthy.

## Scope and honest limitations

- Standard Cloudflare Tunnel covers HTTP(S) applications. It does **not**
  transparently proxy SMTP 25/465/587, IMAP or POP through the ordinary
  HTTP proxy; mail A must be DNS-only when used for direct mail.
- Incoming email currently uses Cloudflare Email Routing MX (preserve).
- Outbound SMTP's **reverse DNS/PTR is controlled by the IP provider**, not
  by the Cloudflare authoritative forward DNS API. SPF can be updated, but
  matching PTR, HELO, IP warm-up/reputation, provider restrictions and some
  SMTP peers might still require work. True zero-human outbound mail across
  arbitrary IP rotations requires a stable reputable outbound SMTP relay or
  a provider PTR automation API; neither is configured by this branch.
- CodeBridge access, firewall allowlists, pinned external server IPs and
  backup transport must be independently audited for host identities.
  Repointing SSH \`known_hosts\` by hostname preserves key-pinning, but
  does not remove the need to attest the ED25519 identity on reinstallation.
- **Important current blocker:** the live \`kmj-elite-health-check\` script
  was patched from the old public IP to \`150.242.200.81\` and may contain
  another literal. It must be migrated to dynamic DNS/origin proof in a
  separate root-SHA-reviewed release. It is **not** fixed by this branch.
- Automated offsite backup still exits 3 at local-prefix creation and
  independent Google decrypt/restore is not verified; DNS automation
  never counts as backup readiness.

## No-cost and release safety

This is a **source-only feature branch** layered onto
\`fix/elite-new-ip-cutover-20261111\` (PR #852). It must not be merged
directly to protected \`main\`, because the existing staging TLS workflow
can run upon main push. Avoid unexpected hosted Actions minutes, API
token exposure, production mutations or a DNS cutover before Cloudflare
Tunnel is actually connected. No provider subscription is created by the
files in this branch.

### Automated service status

- \`DNS_CONVERGED=YES\`: records match a candidate IP, **not** proof of
  PTR, email deliverability, tunnel status or application readiness.
- \`PTR_AUTOMATED=NO_PROVIDER_CONTROL\`: always explicit.
- \`RESULT=BLOCKED_FAIL_CLOSED\`: no future updates assumed; repeat
  after the next timer activation; investigate only through
  sanitized logs/approved operator channel.
- \`--inspect\`: Cloudflare Read only; \`--apply\`: allowlisted PATCH
  on named A records and exactly one existing SPF TXT, no creation or
  deletion of MX, DKIM, DMARC, NS, proxied unrelated hostnames or SSH trust.
