export type DeliveryState = 'verified' | 'active' | 'blocked' | 'queued';

export type DeliveryMilestone = {
    id: string;
    title: string;
    state: DeliveryState;
    detail: string;
    evidence?: string;
};

export const deliveryMilestones: DeliveryMilestone[] = [
    {
        id: 'codebridge-license-renewal',
        title: 'CodeBridge license renewal',
        state: 'active',
        detail: 'Signed device leases, proof-bound enrollment, authenticated credential rotation/revocation, and real-database concurrency gates are implemented; production exposure and signing configuration remain pending',
        evidence:
            'PR #247 signed renewal + PR #248 hash-only enrollment + PR #249 authenticated credential management and PostgreSQL concurrency verification merged with exact-head CI green',
    },
    {
        id: 'locked-landing-product-portfolio',
        title: 'Locked landing product portfolio',
        state: 'verified',
        detail: 'The locked black-and-red landing now receives the complete governed product portfolio, including OmniDesk and CodeBridge, with canonical product-detail routing; public commercial actions remain lifecycle-gated',
        evidence:
            'PR #258 merged as 606ecf279172; staging promotion, exact-SHA deploy, desktop/mobile browser QA and authenticated surface smoke all passed; CodeBridge remains non-commercial until hosted identity, packaging and production security gates pass',
    },
    {
        id: 'admin-product-authority',
        title: 'Admin product authority',
        state: 'active',
        detail: 'Platform-owner product management now binds lifecycle, public visibility, artwork, purchase/licensing controls and deterministic drag-and-drop ordering to the locked public landing while commercial state fails closed',
        evidence:
            'PR #263 implementation + regression coverage for public-beta lifecycle, complete-catalog ordering, landing-order propagation and non-available purchase rejection; exact-head CI pending',
    },
    {
        id: 'authority-foundation',
        title: 'Authority foundation',
        state: 'verified',
        detail: 'Architecture + authority chain with audited, idempotent entitlement issuance and revocation',
        evidence:
            'Foundation verification + PR #174 entitlement revocation exact-head evidence',
    },
    {
        id: 'staging-delivery',
        title: 'Staging delivery',
        state: 'verified',
        detail: 'CI + promotion + deploy + HTTP health',
        evidence: 'Exact-SHA deployment evidence',
    },
    {
        id: 'frontend-live-sync',
        title: 'Frontend live sync',
        state: 'verified',
        detail: 'Rendered public platform + deterministic build + evidence-backed multi-product portfolio',
        evidence:
            'PR #71 + rendered UI check + PR #187 public product surface + PR #199 expanded roadmap portfolio under CI',
    },
    {
        id: 'public-trust-center',
        title: 'Public trust center',
        state: 'verified',
        detail: 'Evidence-backed public Trust Center with governed access, licensing, security-boundary and authentic product-evidence policy is merged and staging-approved',
        evidence:
            'PR #201 + Verify Foundation #1222 + Platform Runtime CI #380 + staging-approved a55934ee9830',
    },
    {
        id: 'public-locale-foundation',
        title: 'Public English/Hindi locale foundation',
        state: 'verified',
        detail: 'Validated en/hi locale selection, persisted public preference and shared Inertia language-switch state are merged without claiming full catalog translation',
        evidence:
            'PR #202 + Verify Foundation #1225 + Platform Runtime CI #382 + Staging Promotion Gate #163 + staging-approved 26738902ca37',
    },
    {
        id: 'public-seo-foundation',
        title: 'Public SEO metadata foundation',
        state: 'active',
        detail: 'Canonical metadata, truthful JSON-LD, public Company/Capabilities surfaces, canonical sitemap, and fail-closed indexing controls are implemented while hreflang remains gated on real translated URLs',
        evidence:
            'PR #203 SEO foundation + PR #211 corporate surfaces, sitemap and fail-closed indexing verification',
    },
    {
        id: 'transactional-outbox-foundation',
        title: 'Transactional outbox foundation',
        state: 'verified',
        detail: 'Durable domain-event outbox persistence, producer idempotency enforcement, rollback-safe consumer receipts, retry scheduling/backoff, bounded attempts and transactional licensing audit publication are implemented and verified',
        evidence:
            'PR #212 merged + current OutboxDispatcherTest, OutboxBatchWorkerTest and DomainEventAtomicityTest green on main; stale PR #213 closed as superseded',
    },
    {
        id: 'registration-onboarding',
        title: 'Registration onboarding',
        state: 'verified',
        detail: 'Owner organization created on signup',
        evidence: 'PR #62',
    },
    {
        id: 'commerce-ledger',
        title: 'Commerce order ledger',
        state: 'verified',
        detail: 'Governed provider-neutral order authority',
        evidence: 'PR #67',
    },
    {
        id: 'payment-reconciliation',
        title: 'Payment reconciliation',
        state: 'verified',
        detail: 'Provider-neutral reconciliation boundary',
        evidence: 'PR #74',
    },
    {
        id: 'desktop-commander-commercial-control-plane',
        title: 'Desktop Commander commercial control plane',
        state: 'active',
        detail: 'Main Platform-authoritative local-first licensing with a cacheable public-beta bootstrap, seven-day signed entitlement cadence, offline Ed25519 verification contract, refresh jitter and no idle licensing heartbeat; billing remains disabled',
        evidence:
            'Clean current-main integration of PR #241 contract; exact-head CI required before merge',
    },
    {
        id: 'license-lifecycle',
        title: 'License lifecycle',
        state: 'verified',
        detail: 'Issue -> validate -> authoritative product + entitlement binding -> revoke operator flow',
        evidence: 'PR #68 + SandboxProductAuthorityValidationTest',
    },
    {
        id: 'license-claim-contract',
        title: 'License tenant claim hardening',
        state: 'verified',
        detail: 'Complete tenant/product/entitlement identity and coherent issue/expiry ordering are required before sandbox validation succeeds',
        evidence: 'PR #99',
    },
    {
        id: 'license-time-contract',
        title: 'License time-bound hardening',
        state: 'verified',
        detail: 'Fail closed on future-issued or overlong sandbox license tokens and cap issuance to the 30-minute sandbox contract',
        evidence: 'PR #103',
    },
    {
        id: 'rust-license-claims-contract',
        title: 'Rust license claim parity',
        state: 'verified',
        detail: 'Fail closed when a Rust-valid response omits the complete sandbox tenant/product/entitlement/time claim contract',
        evidence: 'PR #105',
    },
    {
        id: 'rust-license-time-contract',
        title: 'Rust license time parity',
        state: 'verified',
        detail: 'Independently enforce issue-time skew, maximum lifetime and expiry in the PHP orchestration boundary even when Rust reports valid',
        evidence: 'PR #106',
    },
    {
        id: 'rust-verifier-response-contract',
        title: 'Rust verifier response contract',
        state: 'verified',
        detail: 'Fail closed when the Rust verifier returns semantically inconsistent valid/reason/claims combinations',
        evidence: 'PR #107',
    },
    {
        id: 'rust-invalid-claims-contract',
        title: 'Rust invalid-response claim isolation',
        state: 'verified',
        detail: 'Reject invalid Rust verifier responses that still carry claims so failure paths cannot leak or propagate stale license identity data',
        evidence: 'PR #108',
    },
    {
        id: 'rust-runner-envelope-contract',
        title: 'Rust verifier runner envelope',
        state: 'verified',
        detail: 'Fail closed when the verifier transport envelope omits or mistypes exit_code/output before response parsing begins',
        evidence: 'PR #109',
    },
    {
        id: 'rust-license-input-contract',
        title: 'Rust verifier input contract',
        state: 'verified',
        detail: 'Reject empty sandbox license input before invoking the Rust verifier so malformed requests fail closed deterministically',
        evidence: 'PR #110',
    },
    {
        id: 'rust-nonblank-identity-contract',
        title: 'Rust non-blank identity contract',
        state: 'verified',
        detail: 'Reject whitespace-only JTI and tenant/product/entitlement identity claims before Rust-authoritative sandbox validation can succeed',
        evidence: 'PR #111',
    },
    {
        id: 'php-nonblank-identity-contract',
        title: 'PHP non-blank identity contract',
        state: 'verified',
        detail: 'Reject whitespace-only JTI and tenant/product/entitlement identity claims in the PHP validator so PHP, cross-check and Rust authority paths share the same identity contract',
        evidence: 'PR #112',
    },
    {
        id: 'php-object-payload-contract',
        title: 'PHP license payload object contract',
        state: 'verified',
        detail: 'Reject signed scalar JSON payloads before claim access so the PHP validator only accepts object/map license claims and fails closed deterministically',
        evidence: 'PR #113',
    },
    {
        id: 'php-map-payload-contract',
        title: 'PHP license payload map contract',
        state: 'verified',
        detail: 'Reject signed JSON list payloads so only associative claim maps can enter the PHP license validation authority path',
        evidence: 'PR #114',
    },
    {
        id: 'sandbox-issuer-identity-contract',
        title: 'Sandbox issuer identity contract',
        state: 'verified',
        detail: 'Reject blank organization/product/entitlement identities before signing so the issuer cannot create a token that its own validators must reject',
        evidence: 'PR #115',
    },
    {
        id: 'sandbox-signing-secret-contract',
        title: 'Sandbox signing secret contract',
        state: 'verified',
        detail: 'Reject whitespace-only signing secrets before sandbox token issuance so minimum byte length cannot be satisfied by blank key material',
        evidence: 'PR #116',
    },
    {
        id: 'php-validator-secret-contract',
        title: 'PHP validator secret contract',
        state: 'verified',
        detail: 'Fail closed when the PHP sandbox validator is configured with blank or sub-32-byte key material so validation cannot operate with a weaker secret contract than issuance',
        evidence: 'PR #117',
    },
    {
        id: 'canonical-license-identities',
        title: 'Canonical license identity contract',
        state: 'verified',
        detail: 'Reject surrounding whitespace in sandbox tenant/product/entitlement identities at issuance and reject non-canonical signed identities at validation so authority and revocation comparisons stay deterministic',
        evidence: 'PR #118',
    },
    {
        id: 'positive-license-lifetime',
        title: 'Positive sandbox license lifetime',
        state: 'verified',
        detail: 'Reject zero-length or reversed issued-at/expiry intervals so signed sandbox licenses always represent a strictly positive validity window',
        evidence: 'PR #119',
    },
    {
        id: 'issuer-positive-license-lifetime',
        title: 'Issuer positive lifetime parity',
        state: 'verified',
        detail: 'Reject same-second expiry before signing so the sandbox issuer cannot create a token that the validator must immediately reject',
        evidence: 'PR #120',
    },
    {
        id: 'manual-sales-earning-lane',
        title: 'Manual sales earning lane',
        state: 'verified',
        detail: 'Customer Purchase Center + commercial product activation + owner-confirmed external payment evidence before governed entitlement/license fulfillment',
        evidence:
            'PR #126 + ManualSalesFlowTest + authenticated Purchase Center staging smoke',
    },
    {
        id: 'organization-capabilities',
        title: 'Organization capabilities',
        state: 'verified',
        detail: 'Tenant capability + selected-org binding enforced',
        evidence: 'PR #77 / #80 / #82',
    },
    {
        id: 'license-audit-governance',
        title: 'License audit governance',
        state: 'verified',
        detail: 'Capability-scope privileged audit visibility',
        evidence: 'PR #85',
    },
    {
        id: 'passkey-first-auth',
        title: 'Passkey-first auth path',
        state: 'verified',
        detail: 'Passkey preferred login + enrollment guidance',
        evidence: 'PR #78 / #79',
    },
    {
        id: 'session-device-visibility',
        title: 'Session/device visibility',
        state: 'verified',
        detail: 'Password-confirmed session inventory + sign-out-other-sessions control',
        evidence: 'PR #89',
    },
    {
        id: 'step-up-revocation',
        title: 'Step-up revocation',
        state: 'verified',
        detail: 'Sensitive license revocation requires step-up',
        evidence: 'PR #81',
    },
    {
        id: 'guarded-worker-runtime',
        title: 'Guarded worker runtime',
        state: 'verified',
        detail: 'Push + safe-issue wake-up, five-minute no-idle dispatch, bounded task capacity, parallel verification, bounded explicit PHP platform context, explicitly declared new-file creation context, and owner-gate constraint classification that preserves real privileged-action blocking',
        evidence:
            'PR #72 + PR #127 worker reliability + PR #157 scoped PHP context under CI + PR #165 no-idle continuity + PR #166 negative-constraint classification under CI + PR #169 direct untouched-constraint classification + PR #171 comma-list negative-constraint classification + PR #186 declared new-file context support under CI',
    },
    {
        id: 'verified-free-ai-route',
        title: 'Verified-free AI route',
        state: 'verified',
        detail: 'Free-cloud task completion and worker patch safeguards are verified with bounded file context, scoped patches, fail-closed zero-cost routing, public-only anonymous provider isolation, key-detected provider federation, and a local classification-aware verified-free gateway for additional public-safe capacity',
        evidence:
            'PR #140 + Verify Foundation run 34918844470 success; PR #149 + Verify Foundation run 35064856704 success + Platform Runtime CI run 35064856695 success; PR #204 merged after Verify Foundation #1231 + Platform Runtime CI #385; PR #205 merged after Verify Foundation #1235 + Platform Runtime CI #388; PR #207 exact-head verification in progress',
    },
    {
        id: 'revenue-working-phase',
        title: 'Revenue working phase',
        state: 'verified',
        detail: 'Confirmed order -> entitlement -> governed sandbox license handoff is staging-approved',
        evidence: 'PR #90 / #91 / #93 + staging-approved 81137e0617c9',
    },
    {
        id: 'staging-live-monitor',
        title: 'Staging live operations monitor',
        state: 'verified',
        detail: 'Live public platform verified with exact deployed commit and rendered browser checks; public operations monitoring is removed from the customer surface and operator telemetry remains behind authenticated owner controls',
        evidence:
            'PR #129 + deploy run 34909642182 (5e25dfdfc033) + PR #187 public-monitor removal under CI',
    },
    {
        id: 'ops-readiness-evidence',
        title: 'Ops readiness evidence',
        state: 'verified',
        detail: 'Backup freshness + worker/AI posture + authenticated smoke; the staging control panel now has a tested shared-VPS publisher for worker, runner, task, PR/CI and deployment evidence, refreshed by the five-minute watchdog and worker lifecycle; the native Main Platform staging-home cutover away from the legacy mirror is tracked under CI without changing milestone state',
        evidence:
            'PR #132 + deploy 34912567459 + authenticated smoke 34912692783 + PR #148 control panel + PR #154 live-evidence publisher under CI + PR #159 Purchase Center authenticated smoke under CI + PR #164 stale delivery evidence preservation under CI + PR #170 native staging-home cutover + PR #179 post-worker delivery finalizer + finalizer run 35210616307 + authenticated smoke run 35210726834',
    },
    {
        id: 'sandbox-v1-product-contract',
        title: 'Sandbox v1 product contract',
        state: 'verified',
        detail: 'Product-specific capability profiles, fail-closed purchase boundaries, and the shared versioned PHP/Rust kmj.sandbox.v1 contract are merged with product-side integration evidence',
        evidence:
            'Main Platform PR #190 merged + KMJ CloudOS adapter PR #4 merged after 6/6 verifier tests + KMJ Calibration Pro adapter PR #9 merged after Debug 7/7 and Release 7/7 tests',
    },
    {
        id: 'omnidesk-licensing-contract',
        title: 'KMJ OmniDesk licensing contract',
        state: 'active',
        detail: 'Dedicated omnidesk.remote_access authority, KSLP-v1 identity, signed-entitlement claims, device activation, renewable lease, offline grace, revocation and versioned API boundaries are contract-locked; Main Platform is explicitly limited to OmniDesk billing/licensing and cannot become its session, signaling, relay or media runtime; production Ed25519 signing remains KMS/HSM-gated',
        evidence:
            'PR #246 contract + ProductLicenseProfileRegistry dedicated capability + OmniDeskLicenseContractTest; production signer intentionally not enabled',
    },
    {
        id: 'production-hardening',
        title: 'Production hardening',
        state: 'verified',
        detail: 'Ops Command Center + owner-gated production readiness',
        evidence:
            'PR #97 + PR #98 + completed issue #95 + OperatorOpsConsoleTest',
    },
];

export const verifiedDeliveryMilestones = deliveryMilestones.filter(
    (milestone) => milestone.state === 'verified',
).length;

export const deliveryProgress = Math.round(
    (verifiedDeliveryMilestones / deliveryMilestones.length) * 100,
);

export const deliveryProgressMeta = {
    label: 'Revenue-capable working phase',
    note: 'Evidence-based delivery milestones, not total product completion.',
    refreshed: '2026-09-30',
} as const;
