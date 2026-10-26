# KMJ TECHNO — Secure AI Coding Release Gate

Source: the owner-supplied *Secure Vibe Coding* two-page PDF. Its five layers
(server validation, login throttling, password hashing, error hygiene and
established authentication) and six review steps guide this check.

## Existing protections (do not replace)

Laravel Fortify owns user login/password hashing, MFA and session flow. CodeBridge
device enrollment and owner endpoints already use request validation, throttling
and explicit authorization. Their runtime behavior must still be verified; a
source-level check cannot attest live security.

## Added protection

- The CI gate rejects Git-tracked private environment/key files and scans
  recognized source files for likely private keys and API tokens. Findings show
  file and line, **never the token**. Lockfiles and binary assets are not scanned.
- Composer and production npm advisories are checked in the Laravel verification
  lane. Any audit failure blocks the PR release candidate.
- Security regression tests include positive and negative controls.
- Before promoting a real production environment, run the read-only private
  check on that host with an already-existing .env file:

  ```bash
  python3 scripts/security_release_gate.py --production-env apps/platform/.env
  ```

  This verifies APP_ENV=production, APP_DEBUG=false, HTTPS APP_URL, and
  SESSION_SECURE_COOKIE=true without printing values. **CI cannot check the
  production host's private env file.** Running this script alone is not a
  deployment authorization or proof of HTTPS, session behavior or correct CORS.

## Human review — six steps

1. Run dependency audits; remediate findings without downgrading security.
2. Review password storage, sessions, MFA, recovery and authentication.
3. Exercise unauthorized, malformed, oversized and rate-limited endpoints.
4. Test customer A attempting to access customer B's tenant/device/order.
5. Confirm production HTTPS, secure cookies, error masking and no exposed
   secrets, plus configuration of CSRF, CORS and security headers.
6. Attach exact candidate SHA, passing CI results and owner review. Fail
   closed on missing evidence.

No DNS change, live deploy or existing device authorization is modified by
this change. The release criteria in RELEASE_GATE.md remain authoritative.
