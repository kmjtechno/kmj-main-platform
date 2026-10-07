# KMJ CodeBridge — Internal Owner/Admin Plan

**Status:** implementation in PR #322; **not** a live entitlement until the
Main Platform release gates, deployment, authenticated owner activation, and
signed agent renewal have been verified.

## Purpose and authority

This is a non-billable internal engineering entitlement for a verified KMJ
Platform Owner operating their own organization. It is **not** a public
Professional/Business plan, a free customer upgrade, a ChatGPT subscription,
or an authorization to bypass CodeBridge's project security.

KMJ Main Platform is the sole plan/license issuer. A CodeBridge gateway/agent
must accept only valid signed, product/tenant/device-bound leases. No agent
creates or signs its own owner license.

## Limits and behavior

| Capability | Internal Owner/Admin |
| --- | --- |
| Catalog code | `codebridge.owner` |
| License plan | `owner` |
| Billing | Internal, non-billable; no checkout or auto-charge |
| Devices | Signed ceiling 2,147,483,647; actual enrollment remains bounded by valid credentials, storage, security controls and operational capacity |
| Concurrent jobs | 16 maximum, subject to CPU/RAM/disk and queue policy |
| Project access | Only individually authorized project roots; no unrestricted host access |
| Execution | Explicitly approved gates/command profiles |
| File changes | Scoped, hash-guarded and audited |
| Job management | Persistent IDs, queue, cancellation, bounded logs, safe recovery |
| Autopilot | Task DAG and checkpoints; does not itself grant shell privileges |
| AI model usage | External provider quotas and charges are separate |
| Validity | Preserve existing license expiry; lease renewal remains mandatory |

**Do not advertise the signed device ceiling or 16 concurrent jobs as active until the
production signed entitlement and gateway policy have been verified.** The
current Community agent reports one effective concurrent job. A larger
entitlement does not guarantee faster execution under resource pressure.
The device ceiling is an entitlement upper bound, not a practical deployment target or permission to create unbounded registrations.

## Owner activation

1. Platform Owner signs into Main Platform with a verified account, a
   registered passkey and recent password confirmation.
2. Owner opens `/operator/codebridge/owner-plan` and sees only licenses of
   organizations they own.
3. Owner enters `UPGRADE_CODEBRIDGE_OWNER` and activates the desired
   active `KMJ_CODEBRIDGE` license.
4. A database transaction verifies license status and tenant binding,
   preserves activation and expiry, increments the license sequence and
   appends an auditable plan-change event.
5. Repeated activation is idempotent. No branch push, CI job or login event
   silently upgrades an account.
6. Verify new signed lease, per-device binding, effective job capacity,
   reconnect and renewal after activation.

## Required release gates

- GitHub-hosted CI for Main Platform and CodeBridge licensing runs to
  completion and passes on the exact PR head.
- No self-hosted runner is needed and no CI push is permitted to mutate the
  production license database.
- Deploy via Main Platform's guarded release process, confirm catalog sync
  and owner-only route availability, then perform explicit owner activation.
- Test tenant isolation, expired/revoked licenses, idempotent upgrades,
  policy-conflict denial, audit evidence and existing customer plan stability.
- Validate signing key custody, renewal, revocation and account-wide device
  enforcement; fail closed on invalid claims.
- Follow-up: configure the Main Platform CodeBridge agent with the signed
  renewal adapter, then measure safe parallel job throughput.
- Follow-up: durable journal archival and idempotency tombstones for 24/7
  workloads (CodeBridge issue #186).

## Current blockers

- GitHub-hosted Main Platform workflows currently report failed jobs with
  no executed steps (tracked by Main Platform issue #333); do not merge or
  deploy on the assumption that tests passed.
- The existing Main Platform `platform` quality gate reports `vp: not
  found` in its current VPS checkout. The `fast` gate passes. Dependency
  bootstrap must be performed through an approved CodeBridge profile.
- The Main Platform device agent still runs an older CodeBridge runtime;
  update it through a verified, rollback-safe route before relying on new
  Job Manager capabilities.

**Operational rule:** use KMJ CodeBridge and GitHub as the development
control plane, not a separate Desktop Commander backend.
