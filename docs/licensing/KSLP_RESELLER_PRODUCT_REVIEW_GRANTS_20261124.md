# ONE Licensing Hub — reseller product review delegation

Source-only phase following merged #1104 and #1106. Owner release HOLD is unchanged.

The new internal review-grant authority distinguishes an explicitly delegated verified organization member from an organization administrator. A current platform owner with verified email and registered passkey may record a reason-bound, maximum-90-day grant for one active licensed product of an active issuer. Scope includes the precise membership ID, preventing an old grant from reviving when a user leaves and rejoins. A revocation is atomic with its audit event; repeat revocation is idempotent. Existing grants cannot be silently overwritten or renewed. Renewal/regrant policy remains a separate phase.

The only permission is funding_evidence_review. No existing organization role or license.manage capability changes. Expired grants, unverified users, missing/replaced memberships, paused products, expired/suspended issuers and foreign products deny review. The service is not exposed by an HTTP route and does not change existing ledger authorization. Future HTTP callers must enforce authenticated verified owner identity and recent password confirmation, and bind reads to this exact product scope.

The registry stores no funds, prices, payment proof, customer secrets, signing material or paid authorization. No checkout, issuance, entitlement, funding, paid license, production migration or deployment is activated. Actual reseller funding, spending and customer operations remain blocked pending approved merchant settlement/reversal evidence and further authorized integration.

Acceptance: negative and lifecycle feature tests, exact-head CI, disposable database migration/rollback, independent owner source review. Never infer live readiness from test success.
