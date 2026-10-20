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
        id: 'truthful-premium-product-imagery-p0',
        title: 'Product-identity-accurate media and responsive portfolio',
        state: 'active',
        detail: 'PRs #500 and #502 merged product image identity checks, removed unrelated hard-coded artwork aliases, added branded fallbacks and corrected category overlays across responsive layouts. Actual physical product image fidelity still needs authoritative artwork and owner visual acceptance.',
        evidence:
            'PR #500 and #502 each merged following 5/5 exact-head CI workflows including browser UI checks. No new physical product screenshots were approved or published; protected production release and live browser QA remain outstanding.',
    },
    {
        id: 'customer-context-progressive-registration',
        title: 'International customer registration contact and business context',
        state: 'active',
        detail: 'PR #499 merged an additive private customer profile schema and transaction-safe Fortify registration for account type, country, phone, conditional business organization and optional interest. PR #501 merged an owner-only searchable customer directory. Production mail delivery, backup, guarded migration and live onboarding remain unverified.',
        evidence:
            'PR #499 and #501 merged after 7/7 exact-head workflows each, covering isolated PostgreSQL and protected owner HTTP checks. No owner access is granted to customers; deployment, inbox verification and real authenticated production browser QA still require separate evidence.',
    },
    {
        id: 'legacy-desktop-commander-public-retirement',
        title: 'Retire Desktop Commander public catalog surface',
        state: 'active',
        detail: 'KMJ Desktop Commander is being retired from public landing, product details, sitemap and AI discovery, while existing product IDs, issued entitlements, historical orders and compatibility endpoints remain intact. Merged source exclusion, not proof that live public discovery has been removed.',
        evidence:
            'PR #497 merged following exact-head isolated CI; public listing, sitemap and detail exclusion are code-verified. A new protected production deployment and live anonymous QA are still required before declaring the old listing gone from kmjtechno.com.',
    },
    {
        id: 'registration-abuse-protection-p0',
        title: 'Public account registration abuse protection',
        state: 'active',
        detail: 'A code-reviewed candidate applies independent hashed-IP quotas of 6 POST /register attempts per minute and 30 per hour, with 429, route-scope and hourly-negative tests. This is not deployed or proof that any existing account is fraudulent.',
        evidence:
            'Registration throttle integration is under exact-head review; owner-approved deployment, abuse-metric review and customer-safe rate policy acceptance remain pending.',
    },
    {
        id: 'registration-email-delivery-p0',
        title: 'Registration email verification and password reset delivery',
        state: 'blocked',
        detail: 'Fail-closed registration, resend, and password-reset source checks are implemented. Public desktop/mobile Create account links are guarded by the merged PR #461. PR #470 under review additionally rejects malformed SMTP ports and requires an actual IPv4/IPv6 loopback listener before advertising attempt readiness. Live production outbound mail remains unverified until an authorized sender, independent inbox delivery, signed-link validation and guarded release acceptance all pass.',
        evidence:
            'Current main includes RegistrationMailReadiness and negative HTTP mail tests. PR #461 merged public header/HTTP availability contract with exact-head CI. PR #470 is a candidate mail configuration-readiness guard pending exact-head CI. A configured transport is not proof of successful SMTP delivery, domain/PTR authorization or inbox receipt.',
    },
    {
        id: 'codebridge-device-project-assignments',
        title: 'CodeBridge device project assignment requests',
        state: 'active',
        detail: 'Tenant-scoped Assign Project forms, durable pending local-setup requests, idempotence, and authorization checks are implemented for registered devices. Requests do not grant a new local root or claim online connectivity; operator-approved agent enrollment, server-side project grants, authenticated live browser acceptance and production deployment remain required.',
        evidence:
            'Candidate PR #456 adds a pending-only migration, customer dashboard UI, tenant-bound request endpoint and feature tests. Exact-head CI, production approval and real agent installation are still release gates; never treat a saved request as executable CodeBridge access.',
    },
    {
        id: 'codebridge-control-center-release-candidate',
        title: 'CodeBridge customer Control Center release candidate',
        state: 'active',
        detail: 'Tenant-scoped device management, password-confirmed disconnect, accessible dashboard workspaces, OAuth state handling and official CodeBridge branding have passed integrated source and real-browser testing. Production deployment, live agent presence and connected ChatGPT app metadata acceptance remain pending. PR #472 is under review to add fail-closed OAuth consent/PKCE/implicit-login regression checks to the existing frontend CI; static checks are not authenticated production OAuth evidence.',
        evidence:
            'Consolidated Main Platform RC PR #398 head 88182bb149f3001dcdedbd197ed7437d8acc14c6 is based on 81 integration commits across 42 changed files. Prior Claude PR #387 exact-head GitHub Actions Verify Foundation, Platform Runtime, Main Platform CI, License Contract and real-browser UI smoke all passed, as did CircleCI PHP tests, Pint, PHPStan and CodeBridge device-control. Main-target PR #398 found a missing delivery-progress synchronization record; this entry provides accurate ACTIVE status, not a deployed/verified claim. Final PR-head CI, independent auth/tenant review, staging deployment, customer-domain SHA and authenticated live acceptance are still required.',
    },
    {
        id: 'codebridge-hosted-client-onboarding',
        title: 'CodeBridge hosted client onboarding',
        state: 'active',
        detail: 'Native VS Code/Insiders one-click MCP install links are implemented for the customer portal behind CI review; real browser OAuth and production rollout remain unverified. A fail-closed Main Platform MCP proxy adapter now normalizes verified legacy HTTP 200 unauthorized tool errors into HTTP 401 OAuth challenges; production rollout and true IDE OAuth retest remain pending. A tenant-scoped customer device/project directory and one-click Copilot setup links are implemented behind review gates; gateway-sourced live heartbeat and multi-project local onboarding remain pending. Hosted OAuth account linking, browser/Claude client connectivity, pinned one-click Linux/VPS installer bootstrap, a credential-free ChatGPT Desktop marketplace setup download with bundled local OAuth bridge, customer-facing setup guidance, product-specific CodeBridge terms/privacy/support surfaces, a secure allowlisted GitHub bridge, a private Main Platform GitHub credential broker, authoritative pairing gateway discovery, account-authorized device/project grants, the current exact-head one-click runtime pin, guarded development-channel unattended updates, a bounded legacy /agent compatibility proxy for pre-fix enrollments, and a durable PKCE-only Claude public OAuth client that survives stale DCR registration loss are implemented; public Plugins Directory publication and live production rollout remain release gates',
        evidence:
            'Main Platform legacy-OAuth 401 adapter and adversarial proxy regressions are under review; customer-side success is not claimed until staging and production /mcp smoke pass. Customer device listing, tenant-isolated approved pairing counts, and no-GitHub-sign-in UI workflow are included in PR #344 clean successor; live heartbeat and additional local project grants require further implementation and production tests. CodeBridge exact-head commit ff8a64273ce4 passed CodeBridge CI after PR #94 and adds the guarded hourly development auto-update timer; Main Platform /install is pinned to that immutable runtime so fresh devices inherit the authoritative agent-gateway fix, current account/device diagnostics, and development auto-update path; PR #300 merged the authoritative pairing gateway contract and PR #302 merged account-authorized device/project grants; PR #304 adds a POST-only health/poll/result compatibility proxy; PR #308 adds a stable Claude public OAuth client; CodeBridge PR #104 merged the ChatGPT Desktop marketplace and bundled local OAuth bridge; CodeBridge PR #105 added a credential-free personal-marketplace fallback when Codex CLI is unavailable, and PR #106 corrected the personal marketplace path relative to ~/.agents/plugins; this branch syncs that corrected installer into the account dashboard while keeping public Plugins Directory publication as the universal customer one-click gate',
    },
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
        detail: 'The locked black-and-red landing receives the governed product portfolio including OmniDesk and CodeBridge, with canonical product-detail routing and lifecycle-gated actions. PR #469 under review adds an image-load-error fallback shared with the locked Super Admin product cards; original artwork and geometry are preserved for valid assets. Pixel-perfect owner visual signoff remains pending.',
        evidence:
            'PR #258 merged as 606ecf279172; staging promotion, exact-SHA deploy, desktop/mobile browser QA and authenticated surface smoke all passed; CodeBridge remains non-commercial until hosted identity, packaging and production security gates pass',
    },
    {
        id: 'admin-product-authority',
        title: 'Admin product authority',
        state: 'active',
        detail: 'Platform-owner product management now binds lifecycle, public visibility, artwork, purchase/licensing controls and deterministic drag-and-drop ordering to the locked public landing while commercial state fails closed',
        evidence:
            'PR #263 lifecycle/catalog ordering and non-available purchase regression; combined website + Super Admin source integration PR #338 at cdd47de with 12 frontend contract tests, isolated PHP Unit/Feature, PHPStan/Pint, fresh SQLite owner-policy seed and Chromium public guest QA 42/42 PASS; PR #449 exact source 121695ee13d002dfad06f2d716cd7ae69a16ed49 completed isolated production-build and ephemeral PostgreSQL 18 authenticated owner/nonowner browser smoke; six of seven free standard GitHub-hosted workflows passed after the public-repository rerun on 18 October 2026. Verify Foundation required this delivery-progress sync and must pass on the NEW exact head. Landing artwork still awaits visual signoff; candidate is NOT merged or deployed, and owner product-management lifecycle acceptance and protected release approval remain pending; no live owner grant claimed',
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
        state: 'active',
        detail: 'Promotion remains exact-SHA gated; the VPS systemd timer is now the sole deployment authority and GitHub-hosted verification waits for a staging-only exact-SHA response header before HTTP, rendered UI, and browser QA can pass',
        evidence:
            'PR #293 replaces the stale reusable SSH deploy-key path with timer convergence + X-KMJ-Deploy-SHA evidence and moves bounded recovery/authenticated route regression off the offline self-hosted runner; exact live rollout evidence is required before returning this milestone to verified',
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
        id: 'dependency-security-hardening',
        title: 'Production dependency security hardening',
        state: 'active',
        detail: 'Six reported GitHub Dependabot advisories are addressed in candidate npm/Composer lockfiles, including bounded tinypool 2.1.2 override without a Vite Plus major upgrade; hosted CI and production promotion remain gated',
        evidence:
            '2026-10-09 security patch candidate: shell-quote 1.12.0, source-map-js 1.2.2, tinypool 2.1.2, league/commonmark 2.10.3; npm audit reports 0 in isolated worktree and Composer reports no advisories; do not claim deployed until production verified',
    },
    {
        id: 'payment-reconciliation',
        title: 'Payment reconciliation',
        state: 'verified',
        detail: 'Provider-neutral reconciliation boundary',
        evidence: 'PR #74',
    },
    {
        id: 'razorpay-provider-authenticity',
        title: 'Razorpay payment gateway integration',
        state: 'active',
        detail: 'Server-side Razorpay raw webhook HMAC and fail-closed test-key-only Orders API client implemented without charging customers; Razorpay real sandbox checkout, captured-payment reconciliation, authenticated webhooks, customer billing and merchant cross-border activation remain gated',
        evidence:
            'PR #340: HMAC trust boundary. Follow-up RazorpaySandboxOrderClient branch: 4 mocked tests / 17 assertions and Pint PASS; test-key-only Orders API, no live keys or charge endpoints, no entitlement grants from raw payment callbacks',
    },
    {
        id: 'international-payment-gateways',
        title: 'Cashfree and Razorpay international gateway integration',
        state: 'active',
        detail: 'Cashfree sandbox credential-header control-byte and length rejection is under exact-head review in PR #462; it prevents malformed sandbox provider requests without changing merchant settings or enabling payments. Cashfree signed webhooks, sandbox-only server-created orders, provider-bound verification and read-only passkey-gated Super Admin payment readiness have source and regression coverage; merchant-approved accounts still need independently verified credentials, cross-border activation, payment settlement/reconciliation, subscriptions and refunds before live collection. PR #451 merges owner-only guided TEST credentials and opt-in sandbox connection probes; PR #465 merged the Razorpay config-key readiness check; PR #466 merged strict Razorpay sandbox key validation in the owner vault. PR #467 merged corrupt encrypted Cashfree/Razorpay ID and secret fail-closed validation. PR #468 under review ensures Super Admin sandbox readiness requires the same owner-vault keys the probe actually uses, rather than config-only environment credentials. No change verifies merchant settlement or enables live charging. New additive operator audit outcome migration is validated on disposable PostgreSQL, but production data migration, merchant settlement and live billing remain unverified and disabled',
        evidence:
            'PR #451 merged source (not deployed): one-place Razorpay/Cashfree sandbox onboarding, phone-gated Cashfree test order, encrypted TEST credentials and owner audit-only probe. PostgreSQL audit outcome VARCHAR(24) overflow found by PR #454 disposable migration/rollback QA; additive widening to 64 is under exact-head CI. Real hosted CI and merchant sandbox acceptance are still release gates. PR #347: verified Cashfree raw-body HMAC/webhook, sandbox-only server order, provider-bound signature router, password-confirmed owner-only payment readiness console, and Git-worktree deploy evidence. Isolated payment/admin PHPUnit 25 tests/112 assertions, full Feature suite exit 0 (1796 assertions), lint/type/build/PHPStan/Pint/Vite guard PASS. Real credentials, cross-border approval and captured-payment reconciliation remain NOT verified; no live charges or license issuance from raw webhooks',
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
        detail: 'Complete tenant/product/entitlement identity and coherent issue/expiry ordering are required before sandbox validation succeeds. PR #471 is separately under review for bounded canonical base64url parsing and issuer length parity; this is not a production license activation.',
        evidence: 'PR #99; PR #471 pending exact-head CI and review',
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
        detail: 'Backup freshness + worker/AI posture + authenticated smoke; the staging control panel now has a tested shared-VPS publisher for worker, runner, task, PR/CI and deployment evidence, refreshed by the five-minute watchdog and worker lifecycle; the native Main Platform staging-home cutover away from the legacy mirror is tracked under CI without changing milestone state. Owner Ops telemetry now skips hidden-tab polling and refreshes on visibility return (PR #464 under review; live authenticated acceptance remains pending). PR #474 bounded inner storage archive validation, and PR #475 merged exact-PR-head adversarial archive-contract CI separately from synthetic merge-SHA recovery. PR #476 under review additionally prevents duplicate restore destinations hidden behind noncanonical tar paths. Neither CI proves independent offsite download or a real production-database restore. Upload freshness and archive integrity do NOT prove independent offsite retrieval, successful database restore or recovered application acceptance.',
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
    refreshed: '2026-10-20',
} as const;
