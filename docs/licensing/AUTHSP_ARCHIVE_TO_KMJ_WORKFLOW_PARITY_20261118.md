# AuthSP archive → KMJ Licensing Hub: verified workflow parity

Owner requirement (18 Nov 2026): retain the **complete useful legacy user workflow** while using the modern Main Platform / KSLP authority, approved enterprise design and safer signed licensing. This is a **source inventory and staged parity contract**, not evidence that every feature is deployed.

## Legacy reference: actual archive inspection

Reviewed library archives `authsp.kmjtechno.com.zip` (1,658 entries) and `authsp.kmjtechno.com(1).zip` (1,889 entries). The following labels are present in legacy **page source**, but a label alone does **not** prove secure backend operation.

| Legacy source in `authsp.kmjtechno.com/app/pages/` | Verified UI actions | New KMJ pathway | Current parity |
|---|---|---|---|
| `manage-apps.php` | Create, rename, pause/unpause, refresh, delete application; app credentials and settings | Developer Apps / shared KSLP licensed products | Create gated by issuer + release; rename/status lifecycle **missing** |
| `app-settings.php` | Version, download, webhooks, HWID policy, app hash, customer panel, reseller store | Product configuration, signed client policy, download/release catalog | **Partial**; no direct import of old HWID/IP collection |
| `licenses.php` | Generate batches, import, export, copy, levels, durations, notes, extend, ban, destructive cleanup | Unified KSLP commercial licenses, trial bootstrap keys, verified export/import | Trial individual key + owner license lifecycle **partial**; guarded batch/import/export **missing** |
| `users.php` | User create/import/export, subscriptions, extend/subtract duration, edit/ban, HWID reset | Organization/customer + device activation management | Customer/organization directory **partial**; audited self-service device transfer **missing** |
| `subscriptions.php` | Create/edit/delete subscription levels | Separate issuer subscription + customer commercial entitlements | Backend issuer model exists; owner read-only visibility added; commercial settlement workflow **not finished** |
| `manage-accs.php` | Managed team accounts, role/page permissions, reseller balances, allowed license levels | Owner RBAC / scoped developer/reseller/support roles | **Partial**; complete reseller grants + quotas missing |
| `reseller-licenses.php` | Reseller create/edit/ban/delete keys and linked users | Owner-approved delegated seats, reseller ledger and audit | **Missing production reseller console** |
| `reseller-balance.php` | Day/week/month/lifetime balance/purchases | Reseller quota/credit ledger bound to verified billing | **Missing**; never infer balance from external checkout links |
| `sdk-downloads.php` | Application-specific connector, x86/x64 SDK downloads, snippets | Signed verifiers with conformance tests and per-language packages | Eight-language **configuration starters only**, not production SDKs |
| `billing.php` | Gateway setup and fees (Razorpay/Cashfree/Stripe/PayPal labels) | Verified order/payment → subscription → entitlement → license | **Partial**; no license rights from unverified payments |
| `admin-panel.php` | Global account, billing, mail, security, policy and support controls | Super Admin owner authority, audit, KSLP settings | **Partial**; keep platform owner-only permissions and passkey step-up |

Some legacy files are stubs (e.g. `reseller-users.php` is 58 bytes); **do not interpret filenames alone as a working subsystem**. Neither old archive should be extracted into production or committed into Git: ZIPs may contain legacy secrets/configuration, SQL data, obsolete authentication and deployment assumptions. Reuse verified behavior, **not** its credential scheme, insecure operations or UI assets.

## One authority, four permission-filtered workspaces

1. **Super Admin**: `/operator/kslp`—global KSLP license directory, issuance, lifecycle, customer search, audit, read-only issuer organizations and policy readiness. Role is verified platform owner + registered passkey + recent password confirmation. Commercial CloudOS licenses are **not** developer issuer subscriptions.
2. **Developer**: `/developer/apps`—organization-scoped application registration, trial-key issuance, selected app, SDK *starter* snippets, revocation and activation challenge. Requires verified user, `license.manage`, active unexpired issuer subscription, recent password and `KMJ_DEVELOPER_LICENSING_ENABLED` rollout gate. With global flag OFF, display records and blocker but do not issue.
3. **Customer**: owns purchased products, licensed seats/devices, verified renewal/download/support and payments. Workflows must reference the same subscriptions/entitlements/license service; cross-product customer dashboard and device recovery remain parity work.
4. **Reseller**: owner-approved reseller role, per-product key allowance, balance/quota ledger, customer inventory and audit; **do not expose a reseller admin portal until server authorization/settlement and tests exist**.

Canonical authority chain: **Account → Organization → Subscription → Entitlement → License → Device Activation**. A current KSLP CloudOS license is *not* evidence of active developer issuer subscription; an app subscription is *not* evidence that a customer purchased a paid license. All commercial decisions are server-side with secure audit, strong key/device proof and signed entitlements.

## Screenshot-specific problem reproduced from source

- `/developer/apps` renders `not_subscribed` from `kslp_issuer_subscriptions`, and separately checks the global developer issuance feature flag. Both may block new app/key mutations. It shows only organization-scoped data.
- `/operator/kslp` counts records from `kslp_licenses` and `kslp_activations`; its `issuerSubscriptions` count queries a **different** table. It previously did not expose issuer-organization readiness, making the two screens look inconsistent.
- This PR adds **owner-only read-only issuer workspace table** and explicit status/role boundaries; developer page receives owner-link authorization and shows expired subscriptions as expired. No license is issued, no privilege granted, no global feature flag enabled.

## Outstanding release gates

- Real AuthSP workflow-to-API mapping for app rename/pause, bulk keys, customer import/export, audit history, device release/transfer, subscriptions/renewal, reseller quota and downloadable signed SDKs.
- Per-tenant negative tests; owner approval/step-up, rate limit, quota/race tests, privacy, idempotency, no-leaked-key checks, billing settlement->entitlement correctness.
- Exact-head CI, isolated PostgreSQL migrations/backups/restore, per-language SDK verification, protected staging and production approval, full role-based browser QA.
- Never bypass release gates, treat sandbox/test tokens as commercial keys, import legacy secrets, or manufacture subscription/revenue records.

**Status:** This PR is a focused source-only first integration slice. Full AuthSP parity is **NOT YET COMPLETE**, and production remains on its existing release until all authorization, security, testing and owner-gated rollout checks pass.
