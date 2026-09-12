# ADR-008 — KMJ Identity & Access Platform

Status: Accepted
Date: 2026-09-12
Scope: Registration, authentication, organization access and privileged operator authentication

## Goal
Build a world-class KMJ identity experience that is safer, faster and more deeply integrated with KMJ authority boundaries than a generic hosted identity product, without inventing authentication or cryptographic primitives.

The target is not a marketing claim that KMJ is universally "better than Auth0". Superiority must be demonstrated by security, usability, reliability, cost/control and integration evidence.

## Standards baseline
Use vetted open standards and platform APIs:
- WebAuthn / FIDO2 passkeys
- OAuth 2.x / OpenID Connect for federation and product SSO
- SAML/SCIM adapters later when enterprise demand justifies them
- TLS, CSRF protection and secure server-side session controls

No custom cryptography, password hashing primitive, browser authenticator or proprietary lock-in protocol.

## Identity versus authority
Authentication proves who the subject is.
Authorization determines what the subject may do.
Commercial entitlement/license authority remains separate.

Canonical relationship:
`Account -> Organization Membership -> Role/Capability -> Subscription/Entitlement -> License/Device Right`

A successful login never implies product entitlement, billing status or license authority.

## Registration UX
Default consumer/self-service path should be simple and low-friction:
1. email/identifier entry
2. anti-abuse check only when risk requires it
3. verified email ownership
4. create a passkey immediately when supported
5. create the owner's initial organization atomically
6. present recovery setup and clear device/session status

Do not force organization/company fields that are not required to create a valid account.
Do not grant paid entitlements during registration.

Optional federation may include reputable social/enterprise identity providers through OIDC adapters. Federated identity must map into the same KMJ account/organization authority model.

## Login UX
Prefer identifier-first/passkey-first sign-in with conditional WebAuthn/autofill where supported.

Login should support:
- passkey as the preferred primary authenticator
- cross-device passkey sign-in
- password fallback only where still required
- enterprise SSO routing when organization policy requires it
- transparent locale/accessibility support
- no unnecessary CAPTCHA on every login

The system should progressively encourage password users to enroll passkeys after a successful trusted sign-in.

## Privileged owner/operator tier
Platform Owner/Super Admin access is a separate high-assurance tier.

Requirements:
- no password-only privileged access
- at least one phishing-resistant passkey
- strongly prefer a second device-bound/hardware security-key recovery authenticator
- step-up authentication before destructive, billing, DNS, signing-key or production actions
- short privileged session lifetime with re-authentication for critical changes
- explicit session/device inventory and remote revocation
- immutable audit of privilege changes and critical authentication events

Backend/database/service accounts must never be usable as public frontend login identities.

## Authorization model
Use organization-scoped roles plus explicit capabilities/policies.

Rules:
- every request resolves account + organization + membership + capability context
- tenant context cannot be selected solely from untrusted client data
- deny by default when membership/capability is absent or stale
- high-risk capabilities require step-up proof
- entitlement/license checks remain separate from administrative RBAC
- privileged role assignment/removal is audited and idempotent

Avoid a single permanent omnipotent flag as the long-term authorization architecture.

## Session security
- regenerate session after authentication and privilege elevation
- Secure, HttpOnly and appropriate SameSite cookies
- CSRF protection on browser state changes
- inactivity and absolute expiry policies by risk tier
- session/device list with last activity and revocation
- revoke other sessions after sensitive credential/recovery changes when appropriate
- prevent session fixation and token replay
- never place authoritative privileges in editable client storage

## Recovery
Recovery must not be weaker than the authentication it bypasses.

Design requirements:
- recovery codes are one-time, hashed at rest and regenerable
- verified recovery channels are explicit and user-visible
- privileged account recovery requires stronger evidence and step-up/review
- suspicious recovery/credential changes trigger notification and protective delay where justified
- old authenticators/sessions can be revoked after recovery
- support flow must not reveal account existence or bypass proof requirements

## Password fallback
Where passwords remain necessary:
- use Laravel-supported modern adaptive password hashing
- permit password managers and paste
- block known-compromised passwords when a privacy-preserving mechanism is available
- rate-limit and detect credential stuffing
- do not use arbitrary composition rules as the primary security control

## Adaptive risk and anti-abuse
Risk signals may make authentication stricter, never silently weaken controls.

Possible signals:
- unusual credential failures
- new device/session characteristics
- impossible or anomalous access patterns
- known automation/abuse indicators
- privileged action sensitivity

Responses may include:
- WebAuthn step-up
- additional verification
- temporary rate reduction
- Turnstile/anti-bot challenge
- owner/security notification

Risk scoring must be explainable enough for audit and must not become the sole source of authorization truth.

## Privacy and enumeration resistance
- minimize identity data collection
- keep biometric data on the authenticator/device; KMJ receives only WebAuthn assertions/public credential data
- use generic responses where account-existence disclosure would help attackers
- audit access to sensitive identity/security metadata
- define retention and deletion policy for authentication telemetry

## Federation and enterprise readiness
Keep federation behind provider adapters so KMJ can add OIDC/SAML enterprise connections without coupling domain logic to one vendor.

Enterprise extensions may include:
- organization domain discovery
- organization-specific login policy/branding
- OIDC/SAML SSO
- SCIM provisioning/deprovisioning
- invitation and just-in-time membership workflows
- machine-to-machine clients with least-privilege scopes

No federation provider may directly grant commercial entitlements or licenses.

## KMJ differentiation versus generic hosted identity
The intended advantage is integration and control, not invented cryptography.

KMJ can outperform a generic identity SaaS for its own products by:
- one authority model across account, organization, commerce, entitlement, license and devices
- no permanent dependency on one hosted IdP or pricing tier
- first-party audit/evidence tied to business actions
- direct step-up policy for KMJ-specific high-risk operations
- unified customer, product and operator experience
- explicit degraded modes and migration/exit path

These are architecture goals. Security or UX superiority must be proven by evidence, not marketing wording.

## Metrics and acceptance evidence
Track at minimum:
- registration completion rate
- passkey enrollment rate
- sign-in success and median completion time
- recovery success/support burden
- account-takeover/security-event rate
- false-positive challenge/lockout rate

Acceptance also requires:
- tenant-isolation tests
- authorization/policy tests
- replay/session fixation tests
- recovery abuse tests
- accessibility and mobile usability checks
- independent CI/security evidence before PASS claims

## Delivery order
1. Preserve current Laravel/Fortify registration/login while hardening it.
2. Complete organization membership + capability context.
3. Make passkey enrollment and passkey-first login production-ready.
4. Add secure session/device management and recovery.
5. Add Platform Owner/Operator step-up tier and audit.
6. Add adaptive anti-abuse/Turnstile where evidence warrants it.
7. Add OIDC enterprise federation; SAML/SCIM when customer demand justifies them.
8. Consider acting as an OIDC provider for independent KMJ products only after threat-model/review maturity.

## References
- FIDO Alliance passkeys and FIDO2/WebAuthn specifications
- NIST SP 800-63B Digital Identity Guidelines
- OWASP Authentication and Session Management Cheat Sheets
- Auth0 passkey and Organizations documentation used as current competitive/reference baseline

## Non-goals
- inventing a proprietary authentication standard
- forcing every customer through one external identity vendor
- treating login success as entitlement/license authority
- claiming universal superiority over Auth0 or another IdP without measured evidence
