<?php

use App\Models\User;
use App\Services\Commerce\CommercialProductPublisher;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Str;
use Inertia\Inertia;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Models\CommercialOrder;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

Route::middleware(['auth', 'verified'])->group(function (): void {
    Route::get('purchase', function (
        Request $request,
        OrganizationDirectory $organizations,
        OrganizationCapabilityContext $capabilities,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $organizationItems = collect($organizations->forUser($user->id))
            ->filter(fn (array $organization): bool => $capabilities->allows(
                $user->id,
                $organization['id'],
                'commerce.purchase',
            ))
            ->values();
        $authorizedOrganizationIds = $organizationItems
            ->pluck('id')
            ->map(static fn (mixed $id): string => (string) $id)
            ->all();

        $fulfillableProductIds = EntitlementPolicy::query()
            ->where('status', 'active')
            ->pluck('product_id')
            ->unique()
            ->values()
            ->all();

        $products = Product::query()
            ->where('status', 'active')
            ->whereIn('id', $fulfillableProductIds)
            ->orderBy('name')
            ->get(['id', 'slug', 'name', 'status']);

        $organizationNames = $organizationItems
            ->mapWithKeys(fn (array $organization): array => [$organization['id'] => $organization['name']])
            ->all();
        $productNames = $products
            ->mapWithKeys(fn (Product $product): array => [
                (string) $product->getKey() => (string) $product->getAttribute('name'),
            ])
            ->all();

        $recentOrders = CommercialOrder::query()
            ->where('requester_user_id', $user->id)
            ->whereIn('organization_id', $authorizedOrganizationIds)
            ->latest('created_at')
            ->limit(20)
            ->get(['id', 'organization_id', 'product_id', 'status', 'currency', 'amount_minor', 'created_at'])
            ->map(function (CommercialOrder $order) use ($organizationNames, $productNames): array {
                $organizationId = (string) $order->getAttribute('organization_id');
                $productId = (string) $order->getAttribute('product_id');

                return [
                    'id' => (string) $order->getKey(),
                    'organization_id' => $organizationId,
                    'organization_name' => $organizationNames[$organizationId] ?? $organizationId,
                    'product_id' => $productId,
                    'product_name' => $productNames[$productId] ?? $productId,
                    'status' => (string) $order->getAttribute('status'),
                    'currency' => $order->getAttribute('currency'),
                    'amount_minor' => $order->getAttribute('amount_minor'),
                    'created_at' => $order->getAttribute('created_at')?->toISOString(),
                ];
            })
            ->all();

        return Inertia::render('purchase', [
            'organizations' => $organizationItems->all(),
            'products' => $products
                ->map(fn (Product $product): array => [
                    'id' => (string) $product->getKey(),
                    'slug' => (string) $product->getAttribute('slug'),
                    'name' => (string) $product->getAttribute('name'),
                ])
                ->all(),
            'recentOrders' => $recentOrders,
            'requestKey' => (string) Str::uuid(),
            'requestedProductSlug' => is_string($request->query('product'))
                ? $request->query('product')
                : '',
        ]);
    })->name('purchase.index');

    Route::post('purchase/orders', function (
        Request $request,
        OrganizationCapabilityContext $capabilities,
        CommercialOrderService $orders,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $validated = $request->validate([
            'organization_id' => ['required', 'uuid'],
            'product_id' => ['required', 'uuid'],
            'idempotency_key' => ['required', 'string', 'max:160'],
        ]);

        abort_unless(
            $capabilities->allows($user->id, $validated['organization_id'], 'commerce.purchase'),
            403,
        );

        Product::query()
            ->whereKey($validated['product_id'])
            ->where('status', 'active')
            ->firstOrFail();

        abort_unless(
            EntitlementPolicy::query()
                ->where('product_id', $validated['product_id'])
                ->where('status', 'active')
                ->exists(),
            404,
        );

        $orders->request(
            $validated['organization_id'],
            $validated['product_id'],
            $user->id,
            $validated['idempotency_key'],
        );

        return redirect()
            ->route('purchase.index')
            ->with('success', 'Purchase request submitted for operator confirmation.');
    })->name('purchase.orders.store');

    Route::post('purchase/bundles', function (
        Request $request,
        OrganizationCapabilityContext $capabilities,
        CommercialOrderService $orders,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $validated = $request->validate([
            'organization_id' => ['required', 'uuid'],
            'product_ids' => ['required', 'array', 'min:1', 'max:10'],
            'product_ids.*' => ['required', 'uuid', 'distinct'],
            'idempotency_key' => ['required', 'uuid'],
        ]);
        abort_unless(
            $capabilities->allows($user->id, $validated['organization_id'], 'commerce.purchase'),
            403,
        );

        $productIds = collect($validated['product_ids'])->sort()->values()->all();
        $availableProducts = Product::query()
            ->whereIn('id', $productIds)
            ->where('status', 'active')
            ->pluck('id');
        abort_unless($availableProducts->count() === count($productIds), 404);

        $fulfillableIds = EntitlementPolicy::query()
            ->whereIn('product_id', $productIds)
            ->where('status', 'active')
            ->pluck('product_id')
            ->unique();
        abort_unless($fulfillableIds->count() === count($productIds), 404);

        DB::transaction(function () use ($validated, $productIds, $orders, $user): void {
            // Serialize requests for this organization to keep a bundle key
            // idempotent even when the same browser retries concurrently.
            $organization = DB::table('organizations')
                ->where('id', $validated['organization_id'])
                ->lockForUpdate()
                ->first();
            abort_unless($organization !== null, 404);

            $prefix = 'bundle:'.$validated['idempotency_key'].':';
            $previous = DB::table('commerce_orders')
                ->where('idempotency_key', 'like', $prefix.'%')
                ->get(['organization_id', 'requester_user_id', 'product_id'])
                ->all();
            if ($previous !== []) {
                $previousIds = collect($previous)->pluck('product_id')->sort()->values()->all();
                abort_unless(
                    $previousIds === $productIds &&
                    collect($previous)->every(fn ($row): bool =>
                        $row->organization_id === $validated['organization_id'] &&
                        (int) $row->requester_user_id === $user->id),
                    409,
                    'This bundle request key was already used for a different selection.',
                );
            }

            foreach ($productIds as $productId) {
                $orders->request(
                    $validated['organization_id'],
                    $productId,
                    $user->id,
                    $prefix.$productId,
                );
            }
        }, 3);

        return redirect()
            ->route('purchase.index')
            ->with('success', 'Bundle request submitted. Each product awaits operator confirmation and entitlement fulfillment.');
    })->name('purchase.bundles.store');
});

Route::middleware(['auth', 'verified', 'password.confirm'])
    ->prefix('operator')
    ->name('operator.')
    ->group(function (): void {
        Route::post('products', function (
            Request $request,
            PlatformOwnerAccess $access,
            CommercialProductPublisher $products,
        ) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);

            $validated = $request->validate([
                'slug' => ['required', 'string', 'max:96', 'regex:/^[a-z0-9]+(?:-[a-z0-9]+)*$/'],
                'name' => ['required', 'string', 'min:2', 'max:160'],
            ]);

            $products->publish($validated['slug'], $validated['name']);

            return redirect()
                ->route('operator.index')
                ->with('success', 'Commercial product and entitlement policy are active for purchase requests.');
        })->name('products.store');

        Route::post('orders/{order}/confirm', function (
            Request $request,
            string $order,
            PlatformOwnerAccess $access,
            CommercialOrderService $orders,
        ) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);

            $validated = $request->validate([
                'currency' => ['required', 'string', 'size:3', 'regex:/^[A-Za-z]{3}$/'],
                'amount_minor' => ['required', 'integer', 'min:1'],
                'confirmation_reference' => ['required', 'string', 'max:160'],
            ]);

            $orders->confirm(
                $order,
                $user->id,
                $validated['currency'],
                $validated['amount_minor'],
                $validated['confirmation_reference'],
            );

            return redirect()
                ->route('operator.index')
                ->with('success', 'Payment evidence confirmed. Entitlement still requires explicit fulfillment.');
        })->name('orders.confirm');
    });
