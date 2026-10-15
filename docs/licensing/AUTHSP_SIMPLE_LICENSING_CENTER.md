# KMJ KSLP — AuthSP-inspired Licensing Center (device and SDK slice)

Reference: owner-supplied `authsp.kmjtechno.com(1).zip`. Its practical
application selector, license directory, actions and SDK downloads were
reviewed. AuthSP PHP/database artifacts and secrets are **not** integrated;
KMJ Main Platform stays the only licensing authority.

## Developer flow

1. Create organization (if needed). Issuer approval is still required; no
   subscription, payment or license is created by opening a page.
2. Register an app. Its product code is auto-suggested from the name but
   remains editable and subject to global uniqueness and issuer product quotas.
3. Issue an authorized **trial** key. The full random key is shown once, only
   to its issuer. Backend stores SHA-256 digest, never recoverable plaintext.
4. Use app/language-specific setup starter. This is a **configuration**
   starter, not yet a production signed-license verifier.
5. First-use device challenge/complete uses KSLP proof of possession. The
   endpoint **only records a device**; it explicitly returns
   `signed_lease_issued: false`. It grants no commercial entitlement.
6. The issuer sees only its scoped active device registration IDs, dates and
   a bounded audit-action stream; no MAC address, device fingerprint, private
   signing material or stored bootstrap key is returned.
7. Release an obsolete seat using recent password confirmation and an
   audited reason. Release locks the key/license/device in one transaction,
   marks the registration inactive and increments the server license
   sequence. An already-issued offline lease cannot be recalled instantly;
   the device must enforce expiry and sequence on its next verified check.
   A retry is idempotent.

## New Python first-use reference

`apps/platform/public/sdk/python/kmj_kslp_first_use.py` implements bounded HTTPS-only
challenge/complete registration using the canonical `kmjtechno.com` origin.
The caller must supply an existing Ed25519 public key and a stable
**caller-managed** detached signer. Persist the private signing key only
through an OS credential store/secure enclave/TPM as appropriate for the
target platform; this library never writes it. Also supply a random
per-install identifier **already hashed** with SHA-256, not serial numbers,
MAC addresses or raw HWIDs. The license key must come from a protected
user credential workflow, not a hard-coded source literal.

Example integration shape (not an out-of-box signer):

```python
from kmj_kslp_first_use import register_device

# Load these inputs securely from the target platform's approved key store.
receipt = register_device(
    license_key=secure_bootstrap_key,
    product="YOUR.APP",
    device_public_key=device_public_key_bytes,
    machine_hash=sha256_random_install_id,
    sign=secure_device_ed25519_signer,
)
assert receipt.device_registered
assert receipt.grants_entitlement is False
```

Running `python -m unittest discover -s tests -p 'test_kslp_python_first_use.py'`
executes the offline transport-mocked contract tests, requiring no paid cloud
service or live network. Test the actual PHP/Python cross-language Ed25519
handshake in an authorized staging environment before enabling client use.

## Security and remaining production gates

- Org capabilities `license.manage`, authenticated verified email, recent
  password, throttling and server validation remain authoritative.
- Only active, unrevoked, organization-owned licenses may release a seat.
  Cross-tenant IDs return 403; other-license activation IDs return 404.
- Release is not a free transfer of a commercial paid entitlement and cannot
  renew an expired plan, overwrite payment evidence or create a signed lease.
- Previous active device key material and tokens are never included in
  developer UI, logs or SDK starter downloads.
- Dev console shows a bounded recent list. Search is local to returned rows;
  it is **not** advertised as full database pagination.
- Still required: real production Ed25519 KMS/signer and key rotation,
  per-product audience registry, verifiers for each supported language,
  billing-settlement entitlement gate, tenant-scoped device transfer recovery
  ceremony, PostgreSQL race/idempotency tests, migration rollback, protected
  staging/browser QA and exact-head hosted/private CI recovery.
- No private-to-public repository switch, CI protection bypass, self-hosted
  GitHub runner or paid cloud charge. Draft code is not deployed by writing a PR.

## Zero-extra-hosted-CI local source verifier

A clean **non-production, detached Git worktree** at the exact reviewed
commit can run `bash scripts/ci/verify-authsp-licensing-local.sh <FULL_40_CHAR_HEAD_SHA>`.
The script checks the SHA and isolated worktree, refuses dirty/untracked files,
production checkout locations and actual .env secret files, and executes PHP
syntax, offline Python SDK tests, locked Node install, frontend source checks,
TypeScript and build. It never accesses a production database, issues a
license, posts a payment, pushes code or sets a GitHub check status.

A local receipt is **not** a hosted GitHub Actions PASS and does not permit
overriding protected branch checks. PostgreSQL migrations/race and real
browser/SDK signing integration are separate supervised tests.
