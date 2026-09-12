<?php

use App\Models\LicenseAuditEvent;
use App\Models\User;
use App\Services\AuthorityBootstrapper;
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

Route::inertia('/', 'welcome')->name('home');

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

    Route::get('operator', function (Request $request, PlatformOwnerAccess $access) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        $access->require($user);

        $recentOrders = CommercialOrder::query()
            ->latest('created_at')
            ->limit(20)
            ->get(['id', 'organization_id', 'product_id', 'status', 'currency', 'amount_minor', 'created_at'])
            ->map(function (CommercialOrder $order): array {
                $organizationId = (string) $order->getAttribute('organization_id');
                $productId = (string) $order->getAttribute('product_id');
                $hasActiveEntitlement = Entitlement::query()
                    ->where('organization_id', $organizationId)
                    ->where('product_id', $productId)
                    ->where('status', 'active')
                    ->exists();
                $hasActivePolicy = EntitlementPolicy::query()
                    ->where('product_id', $productId)
                    ->where('status', 'active')
                    ->exists();
                $fulfillmentState = match (true) {
                    $order->getAttribute('status') !== 'confirmed' => 'awaiting_confirmation',
                    $hasActiveEntitlement => 'entitled',
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
