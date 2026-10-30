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
        id: 'codebridge-ai-workspace',
        title: 'CodeBridge AI workflow workspace',
        state: 'blocked',
        detail: 'The workspace shows authorized devices, projects and admitted free models, and stores per-project conversations answered by a zero-spend admitted model, with durable inference events, cancel and retry. Malformed conversation ids now return a clean 404, and every unfit provider state is refused with a specific code before any request. Approved named device tool requests (git status, inspect, one configured quality gate) have a durable queue with idempotent enqueue, cancel, expiry and event timeline, but are switched off by default and no device agent consumes the queue yet, so no request can run today.',
        evidence:
            'Code and tests are under review; the queue, device API and tests exist as source only. Hosted CI, a device agent round-trip, authenticated acceptance against a real free provider and guarded production publication remain required; this entry does not claim a live working chat.',
    },
    {
        id: 'codebridge-single-control-center',
        title: 'One canonical CodeBridge Control Center',
        state: 'active',
        detail: 'The customer Control Center at /services/kmj-codebridge is the only place that offers computer connection, pairing approval and client setup. The owner fleet page now links to it instead of repeating install and pairing actions (its Linux download name had drifted). The header link pointed at a non-existent /services/codebridge route; that legacy path now redirects to the canonical page behind the same sign-in. Deep links such as #codebridge-device-control previously opened the Overview section, where no device controls exist; they now open and scroll to the matching section from a fixed allow-list.',
        evidence:
            'Source-only on a separate UI branch. A new node contract test passes, vp check is clean and a real Chromium run against a synthetic fixture confirmed the device deep link at 390 and 1280 px with no console errors or horizontal overflow. The new HTTP redirect test, exact-head CI, deployment and logged-in owner QA remain pending; production still serves an older release and nothing here changes runtime, Supervisor or device authorization.',
    },
    {
        id: 'codebridge-github-authority-proxy',
        title: 'Main Platform authorizes CodeBridge GitHub operations',
        state: 'active',
        detail: 'PR #677 closes the shared GitHub proxy authority gaps from #675. Merge requests are denied; content writes and branch creation require exact repository-scoped operator grants for codebridge/ development branches. Workflow, local-action and common CI entry-point writes are denied. Repository default and protected branch metadata is independently verified before mutation. Duplicate query and body keys are rejected, and only validated query values are forwarded.',
        evidence:
            'Source-only. 26 focused unit/HTTP tests pass locally, including unauthorized write/merge denials and query ambiguity regressions. Exact-head CI and guarded runtime deployment are separate; no production approval or proxy credential configuration is claimed. Claude recovery/readiness work from merged PR #676 is preserved.',
    },
    {
        id: 'prompt-first-catalog-editor',
        title: 'Short description to populated product/service editor',
        state: 'active',
        detail: 'PR #627 makes one public short description the primary input. A bounded structured cloud response infers name, category and offering type and fills copy, features, FAQs and artwork prompts. The saved draft opens the real editor; a blank duplicate create form is hidden. Request receipts make unchanged retries idempotent. Provider 429 responses now drive a shared text-generation countdown; repeated cloud requests pause while explicit offline drafts and manual editing remain available. No automatic inference retry or provider-limit bypass is introduced; this cooldown follow-up remains source-only pending CI and deployment.',
        evidence:
            'PRs #629, #632 and #633 are merged, with the authenticated zero-cost receipt verification from PR #633 staged at 9d15e14. An owner screenshot on 27 October still shows intermittent provider HTTP 404 for the short interactive-wall-projection brief. This follow-up provides a visibly labeled, explicitly selected OFFLINE deterministic template button: no AI inference, no cloud call, no invented capabilities, private planned catalog record only, owner review required. The existing verified-free AI path stays fail-closed for rate, pricing and billing errors. This is source-only until exact-head CI, staging activation and owner editor save/reopen QA pass; no production mutation. Merged PR #636 improves the explicit offline fallback name hint with PHPUnit regression tests. Consolidated PR #668 adds offline label-prefixed and multiline product name parsing, generic heading exclusions, and numeric version preservation (e.g. CineCore 2.1), with 15 PHPUnit regressions against the latest security-patched main. Follow-up PR #670 covers pasted forms with an empty Product name/Name/Title label followed by a separate value line, including CRLF blank spacers, and refuses to treat a Description field as the name; four additional PHPUnit regressions are proposed. This remains source-only pending exact-head CI and logged-in owner Product Studio Save/Reopen QA. Neither this deterministic offline draft nor the cloud AI path is production deployed or owner-accepted.',
    },
    {
        id: 'one-click-ai-product-service',
        title: 'One-click AI product and service drafts',
        state: 'active',
        detail: 'PR #624 adds owner-only AI fill and add: title and public facts become a complete private planned catalog draft. Slug, generated copy, FAQs, artwork prompts and alt text are filled automatically. Existing GEO/SEO gains service identity, visible FAQ structured data and custom-artwork metadata. Publishing and commercial controls stay with the owner.',
        evidence:
            'Test-first PostgreSQL CI reproduced the missing creation route and service metadata. Implementation CI and staging activation remain pending. Image AI is not configured: existing brand artwork is explicitly labeled as a fallback, and original artwork upload is available.',
    },
    {
        id: 'product-cloud-complete-structured-draft',
        title: 'Complete structured product drafts',
        state: 'verified',
        detail: 'A real zero-cost cloud response stopped at the token limit and produced invalid JSON. PR #622 aligns a concise bounded product schema with an 8000-token budget, requests strict structured output, and refuses any non-stop completion before parsing or applying it. Generated content remains reviewable and unsaved; manual editing limits are preserved.',
        evidence:
            'Owner execution on exact staging source fe4045acd08d50a7438dbfc6fee0610b02e1df50 confirms both HTTP200, usage cost ZERO, finish_reason=stop and PASS_COMPLETE_VALIDATED_ZERO_COST_UNSAVED. All 10 PR checks and staging promotion passed. No product write or production change occurred.',
    },
    {
        id: 'product-free-cloud-quota-feedback',
        title: 'Free cloud quota and explicit owner feedback',
        state: 'blocked',
        detail: 'Staging completed one validated zero-cost unsaved cloud draft, then a real generation request returned HTTP 429 while catalog discovery returned 200. PR #619 preserves the strict free-only gate and reports an explicit rate-limit response with bounded Retry-After instead of a generic unavailable error. It never retries automatically or enables paid fallback.',
        evidence:
            'Owner-provided sanitized diagnostics confirm CLOUD_KEY_PRESENT=YES, CLOUD_CONFIG_ENABLED=YES and provider completion HTTP429. Current account daily-quota versus upstream capacity needs provider metadata confirmation. P520 owner grant exists but gateway registration is still missing; production redemption configuration remains a separate blocker.',
    },
    {
        id: 'product-studio-verified-free-cloud-policy',
        title: 'Cloud-only verified-zero product drafting',
        state: 'active',
        detail: 'PR #617 removes the product studio local LLM dependency and follows ADR-004 cloud-only policy. An official OpenRouter free route requires fresh zero-price catalog evidence, hard zero-price provider caps, bounded requests and a verified-zero response. Paid and unknown-price routes fail closed; manual editing and artwork upload remain available. Existing GEO/SEO is preserved.',
        evidence:
            'The account connection doctor reports P520 missing its current account grant; P720 is intentionally not a dependency. The owner configured a private staging-only cloud key; the fe4045 staging execution verified a complete zero-cost unsaved draft. Production AI configuration remains unchanged.',
    },
    {
        id: 'owner-product-content-artwork-studio',
        title: 'Owner product content and artwork studio',
        state: 'active',
        detail: 'PR #612 extends the guarded product manager with full descriptions, features, FAQs, photo and banner upload, editable generation prompts, explicit unsaved local AI drafts and an Add Product deep link. Existing Main Platform PublicSeo, canonical URLs, sitemap and llms.txt consume the reviewed public catalog; no legacy SEO engine or paid AI fallback is imported.',
        evidence:
            'Acceptance tests first failed for the missing draft/media routes and content persistence. The implementation passed the full PostgreSQL 18 feature suite. Exact-head quality checks, schema-aware staging deployment, local-engine configuration and real owner acceptance remain required. Configured local engines are never presented as verified live connections.',
    },
    {
        id: 'owner-expanded-dashboard-visual-lock',
        title: 'Locked theme for expanded dashboard controls',
        state: 'active',
        detail: 'The actual owner dashboard now scopes its advanced workspace cards and commercial-order surfaces to the locked Command OS palette, borders and compact cards. Hero, Kristi artwork, payment confirmation and license authorization are preserved.',
        evidence:
            'Responsive browser QA now renders the real Operator page rather than only its upper Command OS component. Before the styling fix, expanded-card checks failed at all six widths while other application gates passed. Fresh exact-head verification and private owner acceptance remain required.',
    },
    {
        id: 'owner-locked-shell-account-developer-brand-contrast',
        title: 'Locked owner shell across account and developer pages',
        state: 'active',
        detail: 'Shared AppLayout selects the locked owner shell only when the server-provided PlatformOwnerAccess result is enabled. Account and developer pages keep their existing forms and authorization. Owner theme tokens are scoped independently of customer appearance. The original KMJ emblem receives a light contrast backplate in a versioned browser favicon without changing its geometry.',
        evidence:
            'Source regression checks cover owner-only layout selection, scoped dark tokens and versioned contrast favicon. Exact-head CI and fresh private owner visual acceptance are required before deployment.',
    },
    {
        id: 'owner-shared-device-controls-workspace',
        title: 'Shared owner workspace and CodeBridge device controls',
        state: 'active',
        detail: 'PR #577 integrates the existing device control center into the guarded owner CodeBridge page and applies the compact locked Command OS presentation to owner modules. Registered device metadata is limited to organizations the owner manages. Active-license checks, password-confirmed disconnect and pending-only project assignment remain authoritative. PR #672 makes GitHub repository metadata optional so local-only project requests can be saved through Main Platform; device grants and filesystem access still require separately approved local setup. This is a source candidate, not a deployed feature. Empty organizations never auto-provision a license, and registration never implies an online agent. Screenshot follow-up routes reconnect actions by the registered device OS: Windows connector, Linux/VPS setup or explicit platform choice. Recovery guidance targets the listed machine and registration ID clues distinguish same-name devices; no grants or connectivity states are changed. Exact-head CI and runtime deployment remain separate.',
        evidence:
            'HTTP regressions cover tenant exclusion, credential omission, empty-state non-provisioning and expired-license controls. The PostgreSQL release gate passed after implementation. Responsive QA is being expanded to the actual CodeBridge component at six widths with sandboxed Chromium. Final exact-head CI, fresh candidate owner review and production deployment remain pending.',
    },
    {
        id: 'p0-owner-default-dashboard-command-os-route',
        title: 'Owner default dashboard to protected Enterprise Command OS',
        state: 'active',
        detail: 'PR #570 changes only the default authenticated /dashboard response for users verified by PlatformOwnerAccess to redirect to the existing named /super-admin Command OS. Customer users and owner-flag accounts without a valid passkey still receive the customer dashboard. The destination retains password confirmation, server-side owner policy, real catalog data and locked styling. This is source integration, not an approved or deployed production change.',
        evidence:
            'PR #570 includes scoped dashboard routing, owner/customer/no-passkey regression assertions and a staging smoke that validates the exact owner redirect then directly exercises the protected /super-admin Inertia surface. Exact-head CI, real authenticated owner visual QA, immutable candidate rebuild, protected release approval and post-cutover verification remain pending.',
    },
    {
        id: 'codebridge-first-party-windows-dashboard-connection',
        title: 'CodeBridge first-party Windows one-click dashboard connector',
        state: 'active',
        detail: 'Candidate Main Platform CodeBridge Dashboard now provides a KMJ-hosted Windows connector download and device-specific reconnect guidance, replacing GitHub website onboarding links. The downloaded CMD pins SHA-256 of a first-party PowerShell bootstrap; its runtime source is pinned to an exact previously green CodeBridge commit, owner folders are preserved and new grants still require browser approval. Local Windows execution, active gateway heartbeat, production rollout and full customer browser acceptance are not yet verified.',
        evidence:
            'Candidate PR #539 adds Windows download routes and SHA verification, a pinned script that validates Git/Node24 and source HEAD, first-party dashboard connect/reconnect buttons, PHP regression tests and dashboard truth checks. Exact-head Main Platform CI and verified production deploy remain release gates; neither registered devices nor first-party download imply the agent is online.',
    },
    {
        id: 'unverified-customer-hygiene-readonly-audit',
        title: 'Pre-release customer database hygiene and IST/UTC operations',
        state: 'active',
        detail: 'An additive, read-only Laravel command inventories non-owner unverified accounts by age and selected linked sessions/passkeys/OAuth records without exposing PII or modifying database state. KMJ-elite system clock is verified Asia/Kolkata with active NTP, while persistent token/payment timestamps deliberately remain UTC. A stopped Windows Time service and guarded Main Platform production release-pointer drift are unresolved.',
        evidence:
            'PR #538 adds kmj:users:audit-unverified and no-write regression coverage. Production DB counts, restorable backup verification, licensing/customer identity reconciliation, actual cleanup, exact-head CI and deployment are not yet verified.',
    },
    {
        id: 'codebridge-public-agent-origin-separation',
        title: 'CodeBridge Home Office pairing gateway repair',
        state: 'active',
        detail: 'Main Platform source now separates the private MCP upstream and public HTTPS agent origin (PR #537), blocks unsafe approval if the public origin is invalid (PR #547), and guides existing-device recovery without silently revoking credentials (PR #548). After a Home Office pairing request started on 24 October, the actual old live release rejected redemption with CODEBRIDGE_GATEWAY_UNAVAILABLE; the owner PC remains gateway offline. A read-only operator origin doctor in PR #549 checks public origin and anonymous 401. PR #560 adds the missing effective enrollment API feature-gate check after the 25 October Home Office pairing reached ENROLLMENT_UNAVAILABLE before a browser code. The 25 October Home Office owner pairing again failed with CODEBRIDGE_GATEWAY_UNAVAILABLE, and CodeBridge reports a device grant but GATEWAY_REGISTRATION_MISSING rather than an online agent. This candidate adds a credential-free protocol-v2 pairing-configuration readiness GET for compatible Windows installers; it is not a deployed public route or proof that a device can redeem its grant. The protected release approval remains mismatched and production activation has not occurred. The latest P0 source patch makes enrollment approval and credential redemption reuse the strict first-party HTTPS APP_URL readiness check; mismatched external/credential-bearing origins fail before credential issuance, and transient configuration drift cannot consume an approved verifier-bound grant. This is source-only; owner pairing and live rollout remain unverified.',
        evidence:
            'Live production pointer still reported platform-8070dad72c55 (old source SHA 8070dad...) with expected guard pointer platform-54142f844c0b and readyToActivate=false. The old deployed code uses services.codebridge_gateway.url for agent redemption, while merged source uses agent_public_url. The Windows enrollment logged PUBLIC_AGENT_AUTH_CHALLENGE=PASS, ENROLLMENT_STAGE=REQUEST_CREATED, then CODEBRIDGE_GATEWAY_UNAVAILABLE; no local persisted credential or authenticated Home Office heartbeat is verified. Source PR #549 adds isolated fake-HTTP doctor regression; draft PR #560 checks CODEBRIDGE_LICENSE_API_ENABLED in effective config and adds fail-closed tests. The 25 October later Windows pairing received an official browser approval URL but redemption failed CODEBRIDGE_GATEWAY_UNAVAILABLE and left GATEWAY_REGISTRATION_MISSING; no private config or authenticated heartbeat is verified. The latest source candidate adds an expiry-only owner-approved repair to the device credential replacement transaction; an old grant with a still-valid credential is never overwritten and no real P720 re-pair or production rollout has occurred. This branch adds CodeBridgeEnrollmentReadinessTest and a no-secret GET readiness endpoint, intentionally guarded by codebridge.enabled and canonical HTTPS public-agent origin. Follow-on draft PR #569 adds a tenant-scoped approved-unredeemed pairing state to the customer device dashboard, distinguishing a stranded server grant from actual device redemption and explaining password-confirmed single-device recovery. The new UI is not deployed and makes no online-connection claim. Its own CI, guarded rollout, password-confirmed reconciliation of only the orphan device and one fresh owner pairing remain pending.',
    },
    {
        id: 'omnidesk-production-licensing-boundary',
        title: 'OmniDesk production licensing boundary',
        state: 'active',
        detail: 'Current main hardens Ed25519 verification-key discovery for OmniDesk, enforces signing-key validity windows, verifies first-activation and domain-separated KMJ-OMNIDESK-RENEW-v1 device proofs across Rust/PHP, keeps the CloudOS signer from issuing OmniDesk leases, and persists durable tenant/entitlement/device/install activation binding with atomic JTI/sequence/server-nonce replay state. The OmniDesk-specific canonical payload issuer stays behind an external signer interface so a KMS/HSM implementation can plug in without exposing private key material. This branch adds a fail-closed private API boundary for tenant-scoped activation status, current-entitlement reads and audited deactivation behind a product-specific OmniDeskApiAuthorizer interface; cross-tenant activation lookups do not disclose the binding and an unbound production authorizer returns SERVER_UNAVAILABLE. Activation issuance/renewal adapters, production auth binding, KMS/HSM signing, live cross-service entitlement acceptance and protected deployment remain release gates.',
        evidence:
            'Main includes public key discovery, cross-language activation/renewal proof vectors, canonical entitlement issuance, durable activation binding and one-time renewal-nonce replay protection. This branch adds API-middleware routes, tenant/IDOR tests, manager-only audited deactivation and deterministic fail-closed validation while deliberately leaving the production authorizer interface unbound. No production private key, purchase enablement, activation/renewal signer endpoint or protected deployment is claimed.',
    },
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
        state: 'active',
        detail: 'Fail-closed public registration, verification resend and password-reset guards are implemented. The existing Brevo free SMTP provider accepted a real owner-authorized test on 21 October 2026, and the owner Gmail inbox received it with SPF, DKIM (aligned kmjtechno.com) and DMARC PASS. Candidate PR #519 adds official-logo HTML and plaintext designs wired to Laravel signed verification/reset notifications. Branded-template inbox rendering, Laravel production credentials, customer end-to-end flow and release promotion remain gated.',
        evidence:
            'SMTP auth PASS and Brevo acceptance PASS from KMJ-elite; owner Gmail original headers confirmed SPF=pass, DKIM=pass d=kmjtechno.com selector brevo2, and DMARC=pass for test ec1582c5674f. PR #519 is still under exact-head CI and NOT deployed. Direct VPS SMTP is rejected by Gmail with 550 5.7.1; no production mailer switch, customer signup deliverability, or protected release success has been claimed.',
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
        id: 'p0-locked-width-public-auth-super-admin-url',
        title: 'Locked width and public account entry / Super Admin route',
        state: 'active',
        detail: 'P0 code candidate caps the landing at 1280px while preserving locked artwork and responsive breakpoints, keeps both Login/Register visible on compact mobile, and exposes a named, owner-only password-confirmed /super-admin dashboard alias without removing legacy /operator. This is source work, not live production acceptance.',
        evidence:
            'Candidate P0 PR is under exact-head CI. Production still serves platform-8070dad72c55 and the protected release controller reports readyToActivate=false due to a stale expected-current release. Public registration remains correctly fail-closed until Laravel mail transport is actually activated; no permissions, billing or database changes were made.',
    },

    {
        id: 'p0-real-guest-locked-qa-canonical-owner-route',
        title: 'Guest Login/Register and canonical Super Admin browser acceptance',
        state: 'active',
        detail: 'Candidate PR #528 changes the local six-width browser preview to a signed-out guest for the public landing and a synthetic authorized owner for /super-admin. It checks actually visible and viewport-bounded Login/Register links, truthful registration-paused label, centered 1280px landing, bounded 1520px owner workspace, and the canonical owner route. Staging authenticated smoke also probes /super-admin while preserving /operator.',
        evidence:
            'This remains a source QA candidate pending exact-head checks, protected deployment approval for the actual running production release, external registration email proof, and post-cutover guest/owner live acceptance. No production files, users, payment records or secrets were changed.',
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
        detail: 'Canonical metadata, truthful JSON-LD, public Company/Capabilities surfaces, canonical sitemap, and fail-closed indexing are implemented. This candidate adds initial Blade HTML title, description, canonical and social metadata sourced from public Inertia page props without a separate SSR server. It preserves the locked UI, private noindex and staging indexing gate. Hreflang remains gated on real translated URLs. This is source-only, not proof of live crawler visibility or production deployment.',
        evidence:
            'PR #203 SEO foundation + PR #211 corporate surfaces + merged PR #593 public sitemap/robots parity. Candidate PR #597 adds public initial HTML metadata and isolated feature tests; exact-head CI, raw HTML and social crawler QA, guarded release approval and post-deploy verification remain required.',
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
        detail: 'Backup freshness + worker/AI posture + authenticated smoke; the staging control panel now has a tested shared-VPS publisher for worker, runner, task, PR/CI and deployment evidence, refreshed by the five-minute watchdog and worker lifecycle; the native Main Platform staging-home cutover away from the legacy mirror is tracked under CI without changing milestone state. Owner Ops telemetry now skips hidden-tab polling and refreshes on visibility return (PR #464 under review; live authenticated acceptance remains pending). PR #474 bounded inner storage archive validation, and PR #475 merged exact-PR-head adversarial archive-contract CI separately from synthetic merge-SHA recovery. PR #476 under review additionally prevents duplicate restore destinations hidden behind noncanonical tar paths. PR #655 adds a root-owned exact-SHA staging release-attestation parser under CI, but staging activation, fresh offsite restore and owner production approval remain unverified. Neither CI proves independent offsite download or a real production-database restore. Upload freshness and archive integrity do NOT prove independent offsite retrieval, successful database restore or recovered application acceptance.',
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
        detail: 'Dedicated omnidesk.remote_access authority, KSLP-v1 identity, signed-entitlement claims, device activation, renewable lease, offline grace, revocation and versioned API boundaries are contract-locked; first activation now has a cross-language Ed25519 device proof-of-possession verifier, while Main Platform remains limited to OmniDesk billing/licensing and production signing remains KMS/HSM-gated',
        evidence:
            'PR #246 contract + ProductLicenseProfileRegistry dedicated capability + OmniDeskLicenseContractTest; current activation-proof slice verifies the same KMJ-OMNIDESK-ACTIVATE-v1 golden vector in OmniDesk Rust and Main Platform PHP; production signer and private activation endpoints remain gated',
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
    refreshed: '2026-10-28',
} as const;
