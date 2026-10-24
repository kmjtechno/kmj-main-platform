# 2026-10-24 — Staging TLS recovery evidence

## Observed blocker

- The active Cloudflare zone for `kmjtechno.com` has exactly one staging DNS-only A record, `staging.kmjtechno.com -> 103.212.136.154` (Cloudflare configuration readback).
- The independent staging HTTPS readback failed with curl error **60**: certificate SAN does not match `staging.kmjtechno.com`. Expected approved SHA at observation time was `940d7ecf39c26ba39a06cc49bd927e0a80a2f040`; this **did not prove that staging served the SHA**.
- Protected Main Platform production supervisor reports `currentRelease=platform-8070dad72c55`, `approvedSha=8070dad72c551e5e13d1a78b0d4e6933c2d2ae9b`, `expectedCurrentRelease=platform-54142f844c0b`, `readyToActivate=false`. **Do not invoke production activation with a guessed current pointer.**

## Safe authorized path

The existing `Staging P0 TLS Repair (Pinned Host)` workflow uses staging-only environment approval, a committed exact SSH host key, a single fixed IP, an operator-installed script whose sha256 must match repository source, checks the production symlink before and after, and validates `https://staging.kmjtechno.com/` with default certificate validation. The new DNS guard rejects unexpected/ambiguous public staging records **before any SSH**.

If the run blocks at a missing staging SSH secret, missing operator script, missing CloudPanel CLI/site, or installer failure, preserve the failing evidence. Do not turn on Cloudflare orange-cloud proxying as a blind workaround, turn off TLS checks, edit production DNS, reissue production certificates, or alter the production release pointer.

The preinstalled guard script needs the canonical staging CloudPanel site, public staging A record resolving to the **actual VPS IPv4**, and an installed certificate with exact staging DNS SAN. Production deployment is a separate release stage, requiring exact-current-approval reconciliation and authenticated browser QA. This workflow does not deploy Main Platform.

## Protected repair attempt result — Oct 24 2026

The reviewed staging-only repair workflow on merged main SHA `4c472140c764bdc898231d0068418c35a5dc419b` ran with `STAGING_DNS_PIN=PASS` and a valid pinned SSH host key. The SSH server rejected the configured environment credential:

`Permission denied (publickey,password)` — job `120815560963`, workflow `40074729217`.

**Outcome: staging TLS NOT REPAIRED.** The owner/operator must provision an authorized, host-key-pinned restricted SSH identity for the protected `staging` environment (or a formally equivalent audited server-side execution mechanism), confirm the staging operator-installed script matches the repo digest, then rerun the staging-only repair. Do **not** weaken SSH host verification, paste private keys in logs, switch Cloudflare proxy to camouflage the origin certificate, or touch production current-release symlinks.

## Follow-on test

After a certificate is verified, run independent `Staging Exact SHA Readback`: require matching `X-KMJ-Deploy-SHA`, valid /products and /login response, then authenticated owner acceptance before a guarded production activation. Dashboard source PR #539 and quota PR #540 are already merged but not proven live.
