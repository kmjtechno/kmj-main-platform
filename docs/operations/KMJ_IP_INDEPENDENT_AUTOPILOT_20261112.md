# KMJ-elite: IP-independent public origin (12 Nov 2026)

## Desired result

When the hosting provider changes KMJ-elite's public IPv4, routine IP
rotations must require no changes to GitHub workflows or application
configuration, and no manual Cloudflare DNS editing.

Two compatible layers are staged; **neither is active on KMJ-elite**. The
Cloudflare remotely managed Tunnel resource and five safe HTTPS ingress
rules (including the isolated canary route) are already created in the account (ID
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
   direct \`curl --resolve\` before updating only six allowlisted DNS-only
   A records and the exact pre-existing SPF policy. Before Tunnel cutover,
   set mode to \`direct_only\`: web CNAMEs are never touched again; only
   \`mail.kmjtechno.com\`, \`elite-ssh.kmjtechno.com\` A records and the reviewed SPF token remain dynamic.

Neither approach assumes that detecting outbound IP proves inbound reachability.
The direct-DNS mode fails closed when origin HTTPS identity or network cannot
be established. Failing closed can require host-level investigation if the
provider uses asymmetric NAT/firewall, an outage or different inbound/outbound IP.

## Cloudflare audit before deployment (12 November)

Six distinct DNS-only A records (main/www/staging/cloudos/mail/elite-ssh) point to
\`150.242.200.81\`. The only SPF TXT is exactly
\`v=spf1 ip4:150.242.200.81 include:_spf.mx.cloudflare.net ~all\`.
Cloudflare Email Routing owns MX records. The unrelated
\`host.kmjtechno.com\` and \`authsp.kmjtechno.com\` use a DIFFERENT IP
and must not be modified. **The new remotely managed Cloudflare Tunnel exists with configured HTTPS
ingress, but has no verified connected daemon or live DNS routes.**


### Isolated Cloudflare Tunnel canary (12 November)

A remotely managed ingress was added for `tunnel-canary.kmjtechno.com`.
It points to `https://127.0.0.1:443` with explicit
`originServerName=kmjtechno.com`,
`httpHostHeader=kmjtechno.com`, and `noTLSVerify=false`.
The DNS entry is a **proxied CNAME** targeting
`b18c637f-2700-442a-a12e-b225c43dfc72.cfargotunnel.com`. This
is a new dedicated canary hostname; no production A, MX or SPF record was
altered. The Tunnel remains inactive with no connected origin connector,
so a canary request is expected to fail until the approved daemon is
installed. This is **configuration evidence**, not canary availability proof.

The direct management SSH hostname
`elite-ssh.kmjtechno.com` was also added as a DNS-only A record pointing
at the currently verified `150.242.200.81`. It does **not** change the
server's SSH listener or firewall; it is only a name for existing SSH.
The exact ED25519 server host public key remains pinned. It must be
automatically updated by the `direct_only` DNS reconciler after activation.

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
4. Only after the current six-record Cloudflare snapshot and all origin
   HTTPS preflights PASS, activate \`kmj-ip-autopilot.timer\`. The timer
   retries a failed check later; a periodic run is a one-shot and never
   restarts Nginx/Postfix/PHP/CloudOS or the production release pointer.
5. **Activate the existing remotely managed named Tunnel** (ID
   `b18c637f-2700-442a-a12e-b225c43dfc72`, already configured in
   Cloudflare). Do not create a replacement or expose any tunnel token.
   Install a verified cloudflared >=2025.4.0 with its root-owned token-file
   `/etc/cloudflared/kmj-elite-ip-independent.token` mode 0600 and the
   reviewed fixed `cloudflared-kmj-elite.example.service` unit. Token-file
   support is documented by Cloudflare; no token is printed in the process
   argv. The Tunnel must become connected, and
   `tunnel-canary.kmjtechno.com` must pass independently verified HTTPS,
   Host/SNI, origin certificate and browser checks before any live DNS edit.

   **First** set `config.json` mode to `direct_only` so the agent will
   manage only `mail.kmjtechno.com`, `elite-ssh.kmjtechno.com` and the
   exact existing SPF. Confirm an inspected no-op and pin the new mode.
   **Then** migrate public web A records (main/www/staging/cloudos) to the
   existing Tunnel CNAME in an audited rollback-ready operation.
   Staging web DNS can then resolve to multiple Cloudflare edge IPs.
   Staging release SSH must instead use the separate DNS-only
   `elite-ssh.kmjtechno.com` name with the exact pinned ED25519 key.
   Do not reuse staging's proxied web hostname for direct SSH.

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
  on named A records (six in `ddns`, mail plus SSH in `direct_only`)
  and exactly one existing SPF TXT, no creation or deletion of MX, DKIM,
  DMARC, NS, proxied unrelated hostnames or SSH trust.

## One-time owner-root bootstrap (12 Nov 2026, source staged, not executed)

The reviewed fail-closed launcher is checked into
`scripts/operations/kmj-ip-autopilot-onepass-bootstrap-20261112.py`
and already staged through the authorized CodeBridge project at
`/srv/kmj-codebridge-projects/kmj-main-platform/work/qa/KMJ_IP_AUTOPILOT_20261112/`.
Its current staged SHA-256 is
`4cf146da9a20c802dad077a31fc147f533d164a757097cec2a9b7d6b25883a24`
(16,106 bytes). Verify **this exact hash** before root execution; never
execute the GitHub URL without a pinned local copy.

`--preflight` is read-only: checks Ubuntu 24.04, exact KMJ-elite SSH ED25519
identity, and source SHA hashes. `--activate` is an **explicit privileged
mutation**, not installed and not callable through current CodeBridge
approved profiles. It runs the pinned 22 DNS-agent Python regression cases
plus nine root-bootstrap negative cases **before** any service/package change.
It then installs signed Cloudflare APT `cloudflared` >= 2025.4.0 if absent,
uses two hidden local TTY prompts to store the existing Tunnel token and
a KMJ-zone-scoped DNS Read/Edit API token as root-owned mode 0600 files,
installs exact source/systemd units, performs DNS-agent `--inspect` requiring
an initial no-diff, starts only the new Cloudflare Tunnel service, and
verifies the isolated Tunnel canary externally over HTTPS. It enables the
5-minute DNS-only `direct_only` timer **only if** canary HTTPS 200 passed.
This script neither changes live production A to CNAME nor modifies
Postfix, Nginx, main platform release pointers, existing health checks,
backup units, MX or PTR.

Tokens must be obtained from the Cloudflare account dashboard, **never**
pasted into ChatGPT or committed to GitHub. The remotely-managed Tunnel
token is available in Networking > Tunnels > this tunnel > Add replica.
The independent Cloudflare API token must be **limited to DNS Read and Edit
on the KMJ zone**; do not enter an account-global API key. The installer
only asks the operator for these secrets through the controlling root TTY,
with keyboard echo disabled, and refuses malformed tokens. If installation
or canary fails, production web DNS is unchanged and the script reports a
categorical blocker. Root-only files already installed are preserved for
idempotent retry, not deleted through an unsafe cleanup.

The existing Cloudflare Tunnel itself is
`b18c637f-2700-442a-a12e-b225c43dfc72` and is currently inactive,
zero connectors. Once the owner-root bootstrap has produced
`RESULT=BOOTSTRAP_READY_FOR_WEB_CNAME_CUTOVER`, confirm the named Tunnel is
healthy through the connected Cloudflare API, run a real nonproduction
canary browser QA, then migrate web A records to Tunnel CNAMEs **one by one**
using exact-record read-back and rollback checks. Keep mail and elite-ssh A
records DNS-only; preserve Cloudflare Email Routing MX and current SPF.
The live health-check's existing fixed IP literal and provider PTR remain
separate outstanding dependencies; do not mark every aspect zero-touch
until they are addressed.
