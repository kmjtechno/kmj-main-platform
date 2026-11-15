# KMJ-elite public IPv4 rotation — 11 November 2026

## Confirmed routing

Read from the connected **authoritative Cloudflare** zone `kmjtechno.com`, after the owner-reported host-IP change:

| Role | Name | A record | Proxy |
| --- | --- | --- | --- |
| Production | `kmjtechno.com` | `150.242.200.81` | DNS only |
| Production WWW | `www.kmjtechno.com` | `150.242.200.81` | DNS only |
| Staging | `staging.kmjtechno.com` | `150.242.200.81` | DNS only |
| CloudOS | `cloudos.kmjtechno.com` | `150.242.200.81` | DNS only |
| Mail origin | `mail.kmjtechno.com` | `150.242.200.81` | DNS only |

Old ELITE address: `103.212.136.154`. Current apex SPF also names `ip4:150.242.200.81`. The **separate approved Google VPS SFTP receiver is `34.63.5.14`**; never replace this receiver address with ELITE's new origin IP.

## Source-level updates (draft PRs)

* **Main Platform #853:** staging-only ACME bootstrap and manual-only external TLS/approved-SHA evidence updated to `150.242.200.81`; related contract assertions updated. No staging TLS certificate, release, service, Cloudflare zone, or nginx mutation. Do not manually rerun billed GitHub Actions.
* **CodeBridge #881:** bounded read-only ELITE host-key probe, existing-relay hostpin preflight, and no-start N2 egress inventory have the new ELITE target. The previously attested ED25519 host-key fingerprint is **unchanged**; new address must be revalidated against that exact public-key pin. No GCE VM start.
* **CloudOS main:** default-branch source search found no literal `103.212.136.154`. CloudOS public HTTPS and precise origin parity are still not production-attested.

## Strictly pending safety gates

1. **No SSH trust auto-rotation.** The historical staging host-key file and action-capable `staging-tls-repair-execute.yml` remain on the old address, intentionally failing closed. Verify SSH public host key served by the *new* ELITE IP, using a previously trusted independent key/pin before modifying those paths. Never use `StrictHostKeyChecking=no`, replace keys by blind `ssh-keyscan`, or grant shell to restricted SFTP users.
2. **No offsite backup PASS from old SFTP canary.** Earlier root-run Google restricted-SFTP auth / encrypted upload / SHA-256 readback passed before the owner-reported IP rotation; egress source-IP authorization must be verified again. Protected legacy `kmj-elite-offsite-backup.service` remains failed, last effective exit code 3; this is not proof the previous exit-255 issue was permanently repaired. PR #851 is a *draft* guarded service-only repair with actual invocation receipts required. Independent restore and retention not verified.
3. **Runtime and mail:** DNS/SPF source records at new address are confirmed, but this record alone is not direct evidence of live origin HTTPS, SMTP PTR/FCrDNS, or application login/backup readiness. Do not change MX, sender keys, production release pointer or storage without separate proof.
4. **CodeBridge:** agent connections are reachable by project/device identity, but authorized CloudOS root operator command catalog is empty. Do not bypass owner-signed release boundaries.

## Evidence boundary

This document records authoritative **DNS source-of-truth and source PR changes**, not a production cutover executed by this PR. GitHub hosted CI was not independently verified at drafting, and no paid workflow was manually triggered. Main Platform, CloudOS, backup services, keys, Google VM and Cloudflare DNS were not changed by these source edits.
