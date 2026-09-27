<?php

use App\Models\LicenseAuditEvent;
use App\Models\User;
use App\Services\AuthorityBootstrapper;
use App\Services\Commerce\PublicProductCatalog;
use App\Services\Licensing\LicenseAuditRecorder;
use App\Services\Licensing\SandboxLicenseLifecycle;
use App\Services\PlatformOwnerAccess;
use DateTimeImmutable as ImmutableDateTime;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Inertia\Inertia;
use KMJ\MainPlatform\Commerce\Models\CommercialOrder;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Entitlements\Services\EntitlementIssuer;
use KMJ\MainPlatform\Entitlements\Services\EntitlementReader;
use KMJ\MainPlatform\Organizations\Models\Organization;
use KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

Route::get('/', function (PublicProductCatalog $products) {
    return Inertia::render('welcome', [
        'products' => $products->all(),
    ]);
})->name('home');

Route::get('products', function (PublicProductCatalog $products) {
    return Inertia::render('products/index', [
        'products' => $products->all(),
    ]);
})->name('products.index');

Route::get('products/{slug}', function (string $slug, PublicProductCatalog $products) {
    $product = $products->find($slug);
    abort_if($product === null, 404);

    return Inertia::render('products/show', [
        'product' => $product,
    ]);
})->name('products.show');

Route::get('trust', fn () => Inertia::render('trust'))->name('trust');

$publicPages = [
    'company' => [
        'eyebrow' => 'KMJ TECHNO',
        'title' => 'Engineering products around clear system boundaries.',
        'description' => 'KMJ TECHNO develops cloud systems, calibration technology, immersive cinema software, secure connectivity and engineering products through a governed product ecosystem.',
        'sections' => [
            [
                'title' => 'What we build',
                'body' => 'Our portfolio spans cloud infrastructure, calibration, immersive presentation, software engineering automation and centralized licensing. Each product keeps a clear technical and release boundary.',
                'items' => ['Cloud and platform systems', 'Professional calibration workflows', 'Immersive cinema and 360° environments', 'Secure access and engineering automation'],
            ],
            [
                'title' => 'How we operate',
                'body' => 'Customer access, product entitlements and commercial rules are governed through the KMJ Main Platform while engineering products remain independently testable and releasable.',
                'items' => ['Evidence before public claims', 'Governed customer access', 'Product-specific lifecycle status', 'Automation with protected controls'],
            ],
        ],
        'primaryCta' => ['label' => 'Explore KMJ Products', 'href' => '/products'],
        'secondaryCta' => ['label' => 'View Trust Center', 'href' => '/trust'],
    ],
    'capabilities' => [
        'eyebrow' => 'CAPABILITIES',
        'title' => 'Systems designed to work together without losing control.',
        'description' => 'KMJ capabilities combine platform engineering, cloud infrastructure, calibration, immersive media, secure access and governed licensing around measurable product boundaries.',
        'sections' => [
            [
                'title' => 'Platform & cloud engineering',
                'body' => 'Build and operate product services with clear authority boundaries, structured access, entitlement-aware workflows and recoverable infrastructure.',
                'items' => ['Cloud platform architecture', 'Product entitlement flows', 'Customer and organization access', 'Release and recovery controls'],
            ],
            [
                'title' => 'Calibration & immersive systems',
                'body' => 'Develop workflows for projector-camera calibration, mapping, warping, blending and immersive playback across curved and multi-projector environments.',
                'items' => ['Projection alignment', 'Geometric mapping and warping', 'Blending workflows', 'Immersive playback environments'],
            ],
            [
                'title' => 'Engineering automation',
                'body' => 'Use bounded automation to accelerate software and operational workflows without silently bypassing protected actions or release evidence.',
                'items' => ['Structured engineering workflows', 'Controlled autonomous assistance', 'Audit-friendly operations', 'Human approval for sensitive actions'],
            ],
            [
                'title' => 'Licensing & governed access',
                'body' => 'Centralize product identity, entitlements and customer-facing access while allowing each product to keep its own lifecycle and commercial rules.',
                'items' => ['Central licensing authority', 'Product-specific access rules', 'Lifecycle-aware purchase paths', 'Verified entitlement delivery'],
            ],
        ],
        'primaryCta' => ['label' => 'Explore Products', 'href' => '/products'],
        'secondaryCta' => ['label' => 'Review Trust Principles', 'href' => '/trust'],
    ],
    'legal' => [
        'eyebrow' => 'LEGAL CENTER',
        'title' => 'Clear policies for access, use and customer relationships.',
        'description' => 'This legal center provides the current public policy framework for KMJ TECHNO services. Product-specific terms may apply where explicitly stated.',
        'sections' => [
            ['title' => 'Terms & conditions', 'body' => 'Use of KMJ services is subject to the applicable service terms, account rules, payment conditions and product-specific restrictions.', 'items' => ['Use only authorized accounts and access', 'Do not bypass licensing or security controls', 'Product availability follows the published lifecycle state']],
            ['title' => 'Privacy & data handling', 'body' => 'KMJ aims to minimize data collection, separate required operational data from optional telemetry, and apply access, retention and security controls appropriate to the service.', 'items' => ['Operational and optional telemetry are treated separately', 'Sensitive data should be minimized and protected', 'User rights and legal duties depend on the applicable jurisdiction']],
        ],
        'primaryCta' => ['label' => 'Privacy Policy', 'href' => '/privacy'],
        'secondaryCta' => ['label' => 'Terms & Conditions', 'href' => '/terms'],
    ],
    'terms' => [
        'eyebrow' => 'TERMS & CONDITIONS',
        'title' => 'Terms for using KMJ TECHNO services.',
        'description' => 'These terms establish the baseline rules for account access, product use, licensing, payment and acceptable conduct. Product-specific agreements may add or replace terms where expressly stated.',
        'sections' => [
            ['title' => 'Account & access', 'body' => 'Users are responsible for accurate account information and for protecting credentials, passkeys and other authentication methods associated with their account.', 'items' => ['Use only access granted to you or your organization', 'Do not share protected credentials improperly', 'Access may be limited when security or entitlement requirements are not met']],
            ['title' => 'Licensing & product use', 'body' => 'Software and digital products may require an active entitlement, license or approved access path. Availability depends on the product lifecycle and commercial state.', 'items' => ['Do not circumvent licensing or technical restrictions', 'Development and preview products are not represented as generally available', 'Rights not expressly granted remain reserved']],
            ['title' => 'Payments & refunds', 'body' => 'Where paid access is enabled, pricing, billing interval, taxes and refund eligibility are governed by the purchase flow and the applicable product or order terms.', 'items' => ['No purchase is implied where a product is not commercially enabled', 'Refund eligibility follows the published refund policy and applicable law']],
            ['title' => 'Changes & legal review', 'body' => 'Policies may evolve as products, providers and legal requirements change. Material changes should be published with an effective date. Legal obligations must be interpreted under applicable law and reviewed appropriately for launch jurisdictions.'],
        ],
    ],
    'privacy' => [
        'eyebrow' => 'PRIVACY POLICY',
        'title' => 'Privacy designed around purpose and control.',
        'description' => 'KMJ separates required product-operation data from optional telemetry and marketing consent, and aims to collect only what is necessary for defined purposes.',
        'sections' => [
            ['title' => 'Data we may process', 'body' => 'Depending on the service, data may include account details, organization membership, entitlement and license records, security events, support communications and operational logs.', 'items' => ['Account and authentication data', 'Organization and entitlement records', 'Security and audit events', 'Support and service-operation information']],
            ['title' => 'Purpose & retention', 'body' => 'Data should be processed for a defined service, security, legal or support purpose and retained only for as long as needed for that purpose, legal obligations or verified recovery requirements.'],
            ['title' => 'Optional telemetry', 'body' => 'Optional analytics or telemetry should be separated from required operational data and should not be enabled as a hidden condition of product access unless required for a specific service function.'],
            ['title' => 'Rights & requests', 'body' => 'Applicable privacy rights may include access, correction, deletion or export depending on jurisdiction and legal basis. Requests are subject to identity verification and lawful retention requirements.'],
        ],
    ],
    'refund-policy' => [
        'eyebrow' => 'REFUND POLICY',
        'title' => 'Refund decisions should match the product, order and applicable law.',
        'description' => 'Where paid access is enabled, refund eligibility is determined by the purchase terms, delivery state, license or entitlement usage, and mandatory consumer-law requirements that apply to the transaction.',
        'sections' => [
            ['title' => 'Before purchase', 'body' => 'Customers should review the product lifecycle, access requirements, pricing and delivery terms before completing an order. Research or Planned products should not expose a standard purchase flow unless approved for sale.'],
            ['title' => 'Digital delivery', 'body' => 'Once a digital license, entitlement, download or service has been delivered or materially used, refund eligibility may be limited where permitted by law and the applicable order terms.'],
            ['title' => 'Incorrect or failed delivery', 'body' => 'If KMJ confirms that an eligible paid order was not delivered as promised due to a KMJ-controlled failure, the appropriate remedy may include correction, replacement, credit or refund depending on the transaction and law.'],
            ['title' => 'Mandatory rights', 'body' => 'Nothing in this policy is intended to remove consumer rights that cannot legally be waived.'],
        ],
    ],
    'acceptable-use' => [
        'eyebrow' => 'ACCEPTABLE USE',
        'title' => 'Use KMJ systems lawfully and without harming others.',
        'description' => 'KMJ services may not be used to bypass security, interfere with systems, violate rights, distribute malicious software or obtain access beyond the authority granted to the user.',
        'sections' => [
            ['title' => 'Prohibited activity', 'body' => 'Do not use KMJ services for unauthorized access, credential theft, destructive interference, malware distribution, abuse, fraud or unlawful content.', 'items' => ['No bypass of authentication, licensing or access controls', 'No attacks on networks, services or other users', 'No use that violates applicable law or third-party rights']],
            ['title' => 'Operational protection', 'body' => 'KMJ may restrict or suspend access when necessary to investigate abuse, protect service integrity, comply with law or prevent material harm, subject to applicable contractual and legal requirements.'],
        ],
    ],
    'cookie-policy' => [
        'eyebrow' => 'COOKIE POLICY',
        'title' => 'Use essential storage only where it is needed.',
        'description' => 'KMJ may use essential browser storage or cookies for authentication, security, session continuity and user preferences. Optional analytics or marketing storage should require a separate lawful basis or consent where required.',
        'sections' => [
            ['title' => 'Essential storage', 'body' => 'Authentication, security and session features may require cookies or equivalent browser storage to function reliably and safely.'],
            ['title' => 'Optional analytics', 'body' => 'Optional analytics should be disclosed separately and should not be silently bundled into essential service storage. The current public site does not rely on a third-party analytics script unless one is explicitly enabled and disclosed.'],
        ],
    ],
];

foreach ($publicPages as $path => $page) {
    Route::get($path, fn () => Inertia::render('public-page', [
        ...$page,
        'path' => '/'.$path,
    ]))->name('public.'.$path);
}

Route::get('sitemap.xml', function (PublicProductCatalog $products) use ($publicPages) {
    $base = rtrim((string) config('app.url'), '/');
    $paths = collect(['/','/products','/trust'])
        ->merge(array_map(fn (string $path): string => '/'.$path, array_keys($publicPages)))
        ->merge(collect($products->all())->map(fn (array $product): string => '/products/'.$product['slug']))
        ->unique()
        ->values();

    $urls = $paths->map(function (string $path) use ($base): string {
        $loc = htmlspecialchars($base.($path === '/' ? '/' : $path), ENT_XML1 | ENT_QUOTES, 'UTF-8');

        return "  <url><loc>{$loc}</loc></url>";
    })->implode("\n");

    $xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        ."<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
        .$urls."\n</urlset>\n";

    return response($xml, 200, ['Content-Type' => 'application/xml; charset=UTF-8']);
})->name('sitemap');

Route::middleware(['auth', 'verified'])->group(function () {
    Route::get('dashboard', function (
        Request $request,
        OrganizationDirectory $organizations,
        EntitlementReader $entitlements,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $items = collect($organizations->forUser($user->id))
            ->map(function (array $organization) use ($entitlements): array {
                $organization['entitlements'] = $entitlements->forOrganization($organization['id']);

                return $organization;
            })
            ->values()
            ->all();

        return Inertia::render('dashboard', [
            'organizations' => $items,
            'hasPasskey' => $user->passkeys()->exists(),
        ]);
    })->name('dashboard');

    Route::get('operator', function (
        Request $request,
        PlatformOwnerAccess $access,
        OrganizationCapabilityContext $capabilities,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        $access->require($user);

        $recentOrders = CommercialOrder::query()
            ->latest('created_at')
            ->limit(20)
            ->get(['id', 'organization_id', 'product_id', 'status', 'currency', 'amount_minor', 'created_at'])
            ->map(function (CommercialOrder $order) use ($capabilities, $user): array {
                $organizationId = (string) $order->getAttribute('organization_id');
                $productId = (string) $order->getAttribute('product_id');
                $activeEntitlement = Entitlement::query()
                    ->where('organization_id', $organizationId)
                    ->where('product_id', $productId)
                    ->where('status', 'active')
                    ->oldest('created_at')
                    ->oldest('id')
                    ->first();
                $hasActivePolicy = EntitlementPolicy::query()
                    ->where('product_id', $productId)
                    ->where('status', 'active')
                    ->exists();
                $fulfillmentState = match (true) {
                    $order->getAttribute('status') !== 'confirmed' => 'awaiting_confirmation',
                    $activeEntitlement instanceof Entitlement => 'entitled',
                    $hasActivePolicy => 'ready',
                    default => 'blocked_no_policy',
                };

                return [
                    'id' => $order->getKey(),
                    'organization_id' => $organizationId,
                    'product_id' => $productId,
                    'status' => $order->getAttribute('status'),
                    'currency' => $order->getAttribute('currency'),
                    'amount_minor' => $order->getAttribute('amount_minor'),
                    'created_at' => $order->getAttribute('created_at')?->toISOString(),
                    'fulfillment_state' => $fulfillmentState,
                    'entitlement_id' => $activeEntitlement?->getKey(),
                    'can_manage_license' => $activeEntitlement instanceof Entitlement
                        && $capabilities->allows($user->id, $organizationId, 'license.manage'),
                ];
            })->all();

        return Inertia::render('operator', [
            'metrics' => [
                'users' => User::query()->count(),
                'organizations' => Organization::query()->count(),
                'entitlements' => Entitlement::query()->count(),
                'orders' => CommercialOrder::query()->count(),
                'confirmed_orders' => CommercialOrder::query()->where('status', 'confirmed')->count(),
            ],
            'recentOrders' => $recentOrders,
        ]);
    })->name('operator.index')->middleware('password.confirm');

    Route::post('operator/orders/{order}/fulfill', function (
        Request $request,
        string $order,
        PlatformOwnerAccess $access,
        EntitlementIssuer $issuer,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        $access->require($user);

        $commercialOrder = CommercialOrder::query()
            ->whereKey($order)
            ->where('status', 'confirmed')
            ->firstOrFail();
        $organizationId = (string) $commercialOrder->getAttribute('organization_id');
        $productId = (string) $commercialOrder->getAttribute('product_id');
        $idempotencyKey = 'commercial-order:'.$commercialOrder->getKey();

        $existing = Entitlement::query()
            ->where('idempotency_key', $idempotencyKey)
            ->first();

        if ($existing instanceof Entitlement) {
            abort_unless(
                $existing->getAttribute('organization_id') === $organizationId
                && $existing->getAttribute('product_id') === $productId,
                409,
            );

            return redirect()->route('operator.index');
        }

        abort_if(
            Entitlement::query()
                ->where('organization_id', $organizationId)
                ->where('product_id', $productId)
                ->where('status', 'active')
                ->exists(),
            409,
            'An active entitlement already exists for this organization and product.',
        );

        $policy = EntitlementPolicy::query()
            ->where('product_id', $productId)
            ->where('status', 'active')
            ->oldest('created_at')
            ->oldest('id')
            ->firstOrFail();

        $issuer->issue($organizationId, $policy, $idempotencyKey);

        return redirect()->route('operator.index');
    })->name('operator.orders.fulfill')->middleware('password.confirm');

    Route::post('operator/orders/{order}/sandbox-license', function (
        Request $request,
        string $order,
        PlatformOwnerAccess $access,
        OrganizationCapabilityContext $capabilities,
        SandboxLicenseLifecycle $licenses,
        LicenseAuditRecorder $audit,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        $access->require($user);

        $commercialOrder = CommercialOrder::query()
            ->whereKey($order)
            ->where('status', 'confirmed')
            ->firstOrFail();
        $organizationId = (string) $commercialOrder->getAttribute('organization_id');
        $productId = (string) $commercialOrder->getAttribute('product_id');

        abort_unless($capabilities->allows($user->id, $organizationId, 'license.manage'), 403);

        $entitlement = Entitlement::query()
            ->where('organization_id', $organizationId)
            ->where('product_id', $productId)
            ->where('status', 'active')
            ->oldest('created_at')
            ->oldest('id')
            ->firstOrFail();

        $license = $licenses->issue(
            $organizationId,
            $productId,
            $entitlement->getKey(),
            new ImmutableDateTime('+30 minutes'),
        );
        $validation = $licenses->validate($license);
        $claims = $validation['claims'];
        $jti = is_array($claims) ? ($claims['jti'] ?? null) : null;

        $audit->record(
            'sandbox_license.issued',
            $user->id,
            $organizationId,
            is_string($jti) ? $jti : null,
            'success',
            [
                'entitlement_id' => $entitlement->getKey(),
                'commercial_order_id' => $commercialOrder->getKey(),
                'source' => 'operator_handoff',
            ],
        );

        return redirect()
            ->route('sandbox-licenses.index')
            ->with('sandbox_license', [
                'token' => $license,
                'validation' => $validation,
            ]);
    })->name('operator.orders.sandbox-license')->middleware('password.confirm');

    Route::get('sandbox-licenses', function (
        Request $request,
        OrganizationDirectory $organizations,
        OrganizationCapabilityContext $capabilities,
        EntitlementReader $entitlements,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $items = collect($organizations->forUser($user->id))
            ->map(function (array $organization) use ($entitlements): array {
                $organization['entitlements'] = $entitlements->forOrganization($organization['id']);

                return $organization;
            })
            ->values()
            ->all();
        $organizationIds = collect($items)
            ->pluck('id')
            ->filter(fn (mixed $id): bool => is_string($id) && $capabilities->allows($user->id, $id, 'license.manage'))
            ->values()
            ->all();
        $auditEvents = $organizationIds === []
            ? []
            : LicenseAuditEvent::query()
                ->whereIn('organization_id', $organizationIds)
                ->latest('id')
                ->limit(20)
                ->get(['id', 'organization_id', 'action', 'status', 'jti', 'metadata', 'created_at'])
                ->map(fn (LicenseAuditEvent $event): array => [
                    'id' => $event->getKey(),
                    'organization_id' => $event->getAttribute('organization_id'),
                    'action' => $event->getAttribute('action'),
                    'status' => $event->getAttribute('status'),
                    'jti' => $event->getAttribute('jti'),
                    'metadata' => $event->getAttribute('metadata'),
                    'created_at' => $event->getAttribute('created_at')?->toISOString(),
                ])
                ->all();

        return Inertia::render('sandbox-licenses', [
            'organizations' => $items,
            'licenseResult' => $request->session()->get('sandbox_license'),
            'validationResult' => $request->session()->get('sandbox_license_validation'),
            'auditEvents' => $auditEvents,
            'validationEngine' => (string) config('services.kmj_sandbox_licensing.validation_engine', 'php'),
        ]);
    })->name('sandbox-licenses.index');

    Route::post('organizations', function (Request $request, AuthorityBootstrapper $bootstrapper) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $validated = $request->validate([
            'name' => ['required', 'string', 'min:2', 'max:160'],
        ]);

        $bootstrapper->createOrganizationWithSandboxAccess(
            $validated['name'],
            $user->id,
        );

        return redirect()->route('dashboard');
    })->name('organizations.store');

    Route::post('sandbox-licenses', function (
        Request $request,
        OrganizationCapabilityContext $capabilities,
        SandboxLicenseLifecycle $licenses,
        LicenseAuditRecorder $audit,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $validated = $request->validate([
            'organization_id' => ['required', 'uuid'],
            'entitlement_id' => ['required', 'uuid'],
        ]);

        abort_unless($capabilities->allows($user->id, $validated['organization_id'], 'license.manage'), 403);

        $entitlement = Entitlement::query()
            ->whereKey($validated['entitlement_id'])
            ->where('organization_id', $validated['organization_id'])
            ->where('status', 'active')
            ->firstOrFail();

        $license = $licenses->issue(
            (string) $entitlement->getAttribute('organization_id'),
            (string) $entitlement->getAttribute('product_id'),
            $entitlement->getKey(),
            new ImmutableDateTime('+30 minutes'),
        );
        $validation = $licenses->validate($license);
        $claims = $validation['claims'];
        $jti = is_array($claims) ? ($claims['jti'] ?? null) : null;

        $audit->record(
            'sandbox_license.issued',
            $user->id,
            $validated['organization_id'],
            is_string($jti) ? $jti : null,
            'success',
            ['entitlement_id' => $validated['entitlement_id']],
        );

        return redirect()
            ->route('sandbox-licenses.index')
            ->with('sandbox_license', [
                'token' => $license,
                'validation' => $validation,
            ]);
    })->name('sandbox-licenses.store');

    Route::post('sandbox-licenses/validate', function (
        Request $request,
        OrganizationCapabilityContext $capabilities,
        SandboxLicenseLifecycle $licenses,
        LicenseAuditRecorder $audit,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $validated = $request->validate([
            'organization_id' => ['required', 'uuid'],
            'license' => ['required', 'string', 'max:8192'],
        ]);

        abort_unless($capabilities->allows($user->id, $validated['organization_id'], 'license.manage'), 403);

        $result = $licenses->validate($validated['license']);
        $claims = $result['claims'];
        $organizationId = is_array($claims) ? ($claims['organization_id'] ?? null) : null;
        $jti = is_array($claims) ? ($claims['jti'] ?? null) : null;

        if (is_string($organizationId)) {
            abort_unless(hash_equals($validated['organization_id'], $organizationId), 422);
        }

        $audit->record(
            'sandbox_license.validated',
            $user->id,
            is_string($organizationId) ? $organizationId : null,
            is_string($jti) ? $jti : null,
            $result['valid'] ? 'valid' : 'invalid',
            ['reason' => $result['reason']],
        );

        return redirect()
            ->route('sandbox-licenses.index')
            ->with('sandbox_license_validation', $result);
    })->name('sandbox-licenses.validate');

    Route::post('sandbox-licenses/revoke', function (
        Request $request,
        OrganizationCapabilityContext $capabilities,
        SandboxLicenseLifecycle $licenses,
        LicenseAuditRecorder $audit,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $validated = $request->validate([
            'organization_id' => ['required', 'uuid'],
            'license' => ['required', 'string', 'max:8192'],
            'reason' => ['nullable', 'string', 'max:255'],
        ]);

        abort_unless($capabilities->allows($user->id, $validated['organization_id'], 'license.manage'), 403);

        $result = $licenses->validate($validated['license']);
        $claims = $result['claims'];
        $organizationId = is_array($claims) ? ($claims['organization_id'] ?? null) : null;
        $jti = is_array($claims) ? ($claims['jti'] ?? null) : null;

        abort_unless(is_string($organizationId) && is_string($jti), 422);
        abort_unless(hash_equals($validated['organization_id'], $organizationId), 422);

        $licenses->revoke($jti, $validated['reason'] ?? null);
        $audit->record(
            'sandbox_license.revoked',
            $user->id,
            $organizationId,
            $jti,
            'revoked',
            ['reason' => $validated['reason'] ?? null],
        );

        return redirect()
            ->route('sandbox-licenses.index')
            ->with('sandbox_license_validation', $licenses->validate($validated['license']));
    })->name('sandbox-licenses.revoke')->middleware('password.confirm');
});

require __DIR__.'/settings.php';
