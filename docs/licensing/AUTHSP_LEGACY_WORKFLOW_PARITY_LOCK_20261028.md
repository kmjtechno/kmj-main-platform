# KMJ Licensing Center — AuthSP user-workflow parity lock (28 Oct 2026)

**Owner directive:** The archived KMJ AuthSP licensing system defines the
user journey. The new KMJ Main Platform must preserve the **same user actions,
task order, feedback, bulk operations, and customer/reseller workflows** while
using a modern, secure, maintainable technology stack and the locked KMJ
graphite/red design. It must not silently discard old capabilities.

## Evidence provenance and confidentiality

The owner-supplied private Library archive was inspected read-only:
`authsp.kmjtechno.com.zip`, SHA-256
`8ac687642132f4dd2036c67b599766008788ac9d48dc07e30cc3de46ef1d78ce`.
A second `authsp.kmjtechno.com(1).zip` was also examined. Selected licensing,
accounts and SDK files have identical bytes across both archives. The original
ZIPs include historical runtime/database/config material and must **never be
committed, exposed via public URLs, run, imported into production, or copied
into a release**. This document contains only sanitized feature inventory, no
secrets, customer records, key plaintexts or private code.

Observed legacy evidence:
- `app/pages/manage-apps.php`: create/select app, rename, description,
  pause/unpause, delete with confirmation, credentials and SDK connectors.
- `app/pages/app-settings.php`: enabled status, HWID lock, hash checks,
  version/download URL, custom domain, webhook, customer panel, reset cooldown,
  session expiry, per-error messages, reseller store settings.
- `app/pages/licenses.php`: generate/import/export/copy keys in batches,
  key mask, key count, note, level, duration (seconds to years/lifetime),
  edit/extend, used/unused status, ban/unban, reset HWID, careful deletion.
- `app/pages/users.php`: accounts, create/import/edit/export, subscription
  dates, variables, ban/unban, device/HWID reset, extend/subtract time.
- `app/pages/reseller-licenses.php` and `manage-accs.php`: seller balance,
  allowed license levels, app-scoped managed accounts, seller-issued keys,
  permitted time bundles, ban linked user, scoped page permissions.
- `panel/dashboard/pages/index.php`: customer self-service account and
  HWID reset, web loader and download.
- `app/pages/subscriptions.php`, `billing.php`: subscriptions, pricing,
  role upgrades and multiple payment gateway settings.
- `sdk/spec/authsp-sdk-protocol.md` and
  `sdk/shared/offline-token-format.md`: online first activation, device
  identification, signed responses, refresh and bounded signed offline
  validation with rollback/revocation safeguards.
- `docs/legacy-active-pages-map.md`: keep legacy task access until the
  modern replacement has all actions, relevant API routes, real rows,
  confirmation handling and tests.
- `docs/current-working-functions-snapshot.md` is dated **3 June 2026**;
  its historical database counts and PASS claims are **not** today's
  production customer/license state.

## Locked workflow — users must be able to do all of this

### Developer / application owner
1. Sign in to one KMJ account, enter **Developer Apps & Keys**.
2. Create and select an application; edit its name, description, version,
   status and permitted product/plan, without unexpectedly opening another
   identity system. Confirm deliberate pause/unpause/delete operations.
3. Access app-specific settings: SDK/public API config, download/release,
   app domain, webhook, device policy and messages. No client secret in UI
   screenshots, docs, browser logs or downloadable SDK.
4. **Generate licenses**: select app and plan/level, quantity, key format,
   duration/unit (including lifetime where the product policy permits) and
   optional note. Show the one-time keys and copy/export authorized batches.
   Keys are plaintext only at issuance; durable storage is digest-only.
5. Import permitted legacy keys via a **review/dry-run** and conflict
   resolution; never blindly replay a historical SQL dump or reveal old
   key material. Distinguish a customer's paid entitlement from a developer
   issuer's authority to create keys.
6. Search/filter the same familiar license directory (key alias, app,
   plan, status, owner, activated device, creation/expiry, used/unused).
   View/edit note/plan/duration where policy allows, renew/extend, ban/unban,
   revoke, release or transfer a device seat, and view reason/audit history.
7. Bulk export and bulk operations are still available, but delete-all,
   revoke-all and cross-user actions require explicit owner step-up,
   preview, reversibility where possible and bounded job limits.
8. Retain SDK setup and usable working samples for C#/.NET (P720/desktop),
   C++/Qt (CineCore/Calibration), and later other languages. A text snippet
   is **not** an implemented SDK.

### Customer / end user
1. Register/login/verify the KMJ account and access **My Products ->
   Licenses -> Devices -> Downloads**, with the product entitlement
   readable on one screen.
2. Claim/activate an authorized license for a product, establish device key
   possession online, see activation status and permitted device count.
3. On a new or replaced computer: choose **Reset HWID / Release device seat /
   Transfer device**, with honest cooldown, allowed self-service recovery,
   confirmation and support escalation, keeping the user's familiar task.
4. Show remaining trial/subscription duration, expiry, grace, renewal,
   restriction and any precise entitlement denial reason. Download the
   correct signed app build and license-specific release channel.
5. Offline clients accept only server-signed, scoped time-bounded leases;
   validate trusted key ID, product, device, activation, sequence, expiry,
   clock rollback and revocation when next online. Do not promise real-time
   revocation while disconnected.
6. Upgrade/renew/manage subscriptions, read invoices/order references and
   account/security/audit history. Failed payment or suspended license must
   never destroy customer files or recovery/export access.

### Reseller / team admin
1. App-scoped delegated dashboard with balance, allowed license
   levels/durations, permitted app and customer/organization scope.
2. Issue authorized batches within quota, edit notes/duration, inspect
   Used On / Used By, renew/ban/unban, with optional linked user action
   independently confirmed and audited.
3. Invite/restrict managed staff, allocate quotas/seats, view allowed
   pages and action history. No cross-tenant data, signature keys, unbounded
   key creation or Super Admin privilege.

### Platform Super Admin
1. Global Customers, Applications, Plans, Keys, Subscriptions, Devices,
   Activations, Resellers, Payments, Releases, Webhooks, Security and Audit.
2. Full license lifecycle and critical recovery controls with reason,
   authorization, step-up, idempotency and immutable audit history.
3. Strong diagnostics that show **actual** database counts and errors;
   never fake statuses, "connected", license metrics or successful payment.
4. Migration review and event/record mapping from old AuthSP tables without
   auto-importing unverified legacy passwords, secrets, sessions or SQL.

## Existing modern implementation vs legacy parity

| User journey | New Main Platform evidence | Status |
|---|---|---|
| App registration + developer trial key | `docs/licensing/DEVELOPER_APPS_RELEASE_GATES.md`; `developer-apps.tsx` | Partial; trial-only |
| Super Admin license search/issue/plan/audit | `operator-kslp.tsx` | Partial; CloudOS-scoped |
| Signed license and offline expiry | `KSLP_AUTHSP_ADAPTATION.md`, signed Ed25519 lease / bounded offline policy | Partial; product profiles gated |
| Key quantity/mask/note/import/export/batch UX | Old AuthSP pages | **Parity not demonstrated** |
| Per-app HWID policy, reset/transfer/cooldown | Existing KSLP activation architecture plus legacy UI | **End-to-end parity not demonstrated** |
| Seller/reseller balance, level quotas, linked user actions | Old AuthSP pages | **Parity not demonstrated** |
| Complete customer dashboard and one-click recovery | Old AuthSP customer panel | **Parity not demonstrated** |
| Paid plans, settlement-verified entitlements | Existing KSLP commercial authority design | Release-gated |
| Working C#/C++/Qt SDKs | AuthSP SDK specification + new KMJ product profiles | Needs conformance tests |
| Legacy migration and rollback with customer counts | historical archive only | Not authorized or performed |

Do not label an existing route "feature parity" until a real authenticated
browser test exercises the equivalent task and the backend state transition.

## Modern architecture — no new paid service

- **One authority:** existing KMJ Main Platform (Laravel/PHP 8.4 +
  PostgreSQL/KSLP). Keep one KMJ login, one canonical business/entitlement
  ledger and Super Admin. No independent AuthSP/MySQL production server.
- **Domain services:** application registry, issuer/reseller quota, key
  lifecycle, payment-to-entitlement reconciliation, device/activation
  lifecycle, signed leases, audit, API/SDK compatibility. Extend existing
  KSLP rather than introducing a competing signer/issuer.
- **Session/API:** preserve established Laravel auth, owner passkeys/MFA and
  tenant-scoped policy. Evaluate Laravel Sanctum/Fortify, Spatie Permission or
  PHP-Casbin only where current built-in mechanisms fall short; importing
  duplicate auth/role frameworks is a regression.
- **Crypto:** sodium Ed25519 for server-signed leases, secure per-device
  keypair/possession proof, bounded lease/offline grace, key rotation and
  replay/idempotency protection. Never ship signing private keys.
- **UI:** keep exact legacy clicks/task order and labels where practical
  while rebuilding modern responsive screens in the locked KMJ theme.
- **Local first / zero cost:** use existing PostgreSQL, scheduler and agent,
  not another paid licensing SaaS, API, database or VPS. Prefer one public
  origin `kmjtechno.com`.

## GitHub technology evaluation, 28 Oct 2026

| Repo | Use | Decision |
|---|---|---|
| [quteam/license-manager](https://github.com/quteam/license-manager) (MIT) | **Closest workflow model:** application onboarding, bulk keys, status filters, self-service device unbind/cooldown, audit, SDK examples | Study business rules and tests; its Cloudflare Workers/D1 architecture must **not** become a second KMJ licensing authority |
| [alvarorg14/openlicensd](https://github.com/alvarorg14/openlicensd) (Apache 2.0) | Single-binary license admin, machine release, activation caps and hashed keys | Useful interface/API reference; narrower than offline signed leases, reseller billing and customer portal; avoid another server |
| [tabloy/keygate](https://github.com/tabloy/keygate) (AGPL-3.0 plus additional terms) | License lifecycle, floating seats, customer portal, offline verification and auditing | **Reference only**; AGPL obligations and required UI attribution conflict with blindly embedding it in proprietary white-labelled KMJ UI |
| [keyzori/keyzori](https://github.com/keyzori/keyzori) (Apache 2.0) | Device/IP caps, expiry and metering | Reference only; major V2 incompatibility and extra Bun/Redis process; not a KMJ drop-in |
| [keygen-sh/keygen-api](https://github.com/keygen-sh/keygen-api) | Device activation, key policies, signed offline examples | **Architecture reference only**; CE free self-host but Fair Core License has competing-use restrictions; do not vendor code or add a second authority |
| [keygen-sh/example-csharp-hybrid-online-offline-licensing](https://github.com/keygen-sh/example-csharp-hybrid-online-offline-licensing) | Ed25519/AEAD client testing patterns | Learn protocol/test concepts; check component licenses before copying |
| [spatie/laravel-permission](https://github.com/spatie/laravel-permission) (MIT) | Team/account roles | Evaluate against existing KMJ policies; not a licensing engine |
| [laravel/sanctum](https://github.com/laravel/sanctum) (MIT) | Browser/API token authentication | Optional; reuse if installed, no forced auth rewrite |
| [laravel/fortify](https://github.com/laravel/fortify) (MIT) | Sign-in/recovery/MFA backend flows | Optional; preserve existing account UX |
| [php-casbin/php-casbin](https://github.com/php-casbin/php-casbin) (Apache 2.0) | Scoped reseller/admin policy rules | Optional library; compare to Laravel Gates/KSLP authorization |
| [openfga/openfga](https://github.com/openfga/openfga) (Apache 2.0) | Fine-grained global access graph | **Do not deploy a new service now**; avoid resource cost and competing authority |

No external repo is equivalent to copying the old AuthSP workflow. Use
reference code only after compatible licensing/security review. These
upstream projects' README feature claims are not independent production
security audits; never install them directly on the customer VPS or
replace existing KSLP/payment authority without isolated benchmarking.

## Implement/validate in this order

1. Lock complete old-action-to-new-page/API mapping in a test fixture.
   Preserve labels/task order for Create App, Generate Licenses,
   Import/Export, Manage Users, Reset HWID, Reseller Balance.
2. First customer-safe parity: Developer Apps -> Key batches -> license
   directory -> activation -> Release Device Seat / Reset HWID -> renew.
3. Add seller quotas, customer panel and payment/upgrade continuity.
4. Prove crypto/SDK cross-language interoperability and offline/revoke
   negative vectors. Perform PostgreSQL migrations on disposable data,
   audit legacy mapping with redacted test fixtures.
5. Compare actual authenticated desktop/mobile owner/customer/reseller
   task recordings against the old flow. Require non-owner denial checks.
6. Release only through exact SHA CI, staging readback, independent backup
   restore, signed approval and guarded production deployment.

**Deployment state:** This document is a reference lock, **not a deployed
feature or a license issuance authorization**. Do not import the ZIP, its
private data, secrets or test database into production.
