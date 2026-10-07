# KMJ CodeBridge — Owner Admin plan

This is a **Main Platform owner-only** entitlement, not a public pricing plan or
a ChatGPT subscription upgrade. It does not change OpenAI usage, cloud-model
quotas, billing or account permissions in ChatGPT.

## Activation

1. Sign into KMJ Main Platform as a verified platform owner with a registered
   passkey. Confirm your password again when requested.
2. Open `/operator/kslp` and locate the existing active `KMJ_CODEBRIDGE`
   **Professional** license for the correct tenant. Do not choose a CloudOS
   license or create a replacement tenant/device.
3. Enter a specific audit reason (10–500 characters) and select
   **Grant CodeBridge Owner Admin** on that license.
4. Verify the license's plan changes to `admin` and its sequence increases.
   The action is idempotent; a repeat does not create another audit event.
5. Ensure the agent uses signed-license mode and its existing authenticated
   device-credential renewal. Wait for a **new signed lease** to arrive and
   confirm the effective job capacity. A free-mode agent stays at one job even
   if a license record changes.

## Plan policy

- No monthly commercial job/mission meter is introduced.
- `features`: `read`, `write`, `execute`.
- `devices`: 2,147,483,647 (schema-level maximum; **not** a promise of
  infinite physical connections).
- `concurrent_jobs`: 16, the current signed-agent verification ceiling.
- Existing license ID, tenant, activation, device credentials, expiry and
  signing authority remain unchanged.
- All job execution remains subject to project allowlists, explicit approvals,
  host CPU/RAM/disk availability, queue limits and durable audit retention.
- Future host-aware expansion beyond 16 requires a separately verified
  CodeBridge agent release. Never raise this plan limit beyond the version
  actually deployed and verified.

## Security and rollback

Only `auth`, `verified`, `password.confirm` and `PlatformOwnerAccess`
(passkey registered) sessions can call the upgrade endpoint. The license and
tenant must match and the license must be active and already Professional.
The transition is transactional, logged in `kslp_license_events`, and never
returns signing keys or credentials.

This release **does not** auto-upgrade any account or alter production data
during migration/deploy. A real owner action is mandatory. If owner login or
device renewal is unavailable, the account remains on its existing plan and
the system must report the upgrade as pending, not complete.
