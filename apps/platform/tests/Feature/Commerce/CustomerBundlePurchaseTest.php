<?php

namespace Tests\Feature\Commerce;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class CustomerBundlePurchaseTest extends TestCase
{
    use RefreshDatabase;

    public function test_customer_requests_multiple_products_once_without_activating_access(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);
        $organization = app(OrganizationCreator::class)->create('Customer Bundle', $user->id);
        $first = $this->commercialProduct('bundle-codebridge');
        $second = $this->commercialProduct('bundle-cloudos');
        $key = (string) Str::uuid();
        $payload = [
            'organization_id' => $organization->getKey(),
            'product_ids' => [$second->getKey(), $first->getKey()],
            'idempotency_key' => $key,
        ];

        $this->actingAs($user)->post('/purchase/bundles', $payload)->assertRedirect('/purchase');
        $this->assertDatabaseCount('commerce_orders', 2);
        $this->assertDatabaseCount('commerce_ledger', 2);
        $this->assertDatabaseCount('entitlements', 0);
        $this->assertDatabaseHas('commerce_orders', [
            'organization_id' => $organization->getKey(),
            'product_id' => $first->getKey(),
            'status' => 'requested',
            'idempotency_key' => 'bundle:'.$key.':'.$first->getKey(),
        ]);
        $this->assertDatabaseHas('commerce_orders', [
            'organization_id' => $organization->getKey(),
            'product_id' => $second->getKey(),
            'status' => 'requested',
            'idempotency_key' => 'bundle:'.$key.':'.$second->getKey(),
        ]);

        $this->actingAs($user)->post('/purchase/bundles', $payload)->assertRedirect('/purchase');
        $this->assertDatabaseCount('commerce_orders', 2);
        $this->assertDatabaseCount('commerce_ledger', 2);

        $this->actingAs($user)->post('/purchase/bundles', [
            ...$payload,
            'product_ids' => [$first->getKey()],
        ])->assertStatus(409);
        $this->assertDatabaseCount('commerce_orders', 2);
    }

    public function test_bundle_requires_distinct_products_and_active_fulfillment_policies(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);
        $organization = app(OrganizationCreator::class)->create('Governed Purchase', $user->id);
        $first = $this->commercialProduct('bundle-valid-product');
        $unavailable = Product::query()->create([
            'slug' => 'bundle-no-policy',
            'name' => 'Unavailable Product',
            'status' => 'active',
        ]);
        $payload = [
            'organization_id' => $organization->getKey(),
            'idempotency_key' => (string) Str::uuid(),
        ];

        $this->actingAs($user)->post('/purchase/bundles', [
            ...$payload,
            'product_ids' => [$first->getKey(), $first->getKey()],
        ])->assertSessionHasErrors('product_ids.1');

        $this->actingAs($user)->post('/purchase/bundles', [
            ...$payload,
            'product_ids' => [$first->getKey(), $unavailable->getKey()],
        ])->assertNotFound();
        $this->assertDatabaseCount('commerce_orders', 0);
    }

    public function test_bundle_cannot_cross_organization_permissions(): void
    {
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $intruder = User::factory()->create(['email_verified_at' => now()]);
        $organization = app(OrganizationCreator::class)->create('Private Customer', $owner->id);
        $product = $this->commercialProduct('bundle-private-product');

        $this->actingAs($intruder)->post('/purchase/bundles', [
            'organization_id' => $organization->getKey(),
            'product_ids' => [$product->getKey()],
            'idempotency_key' => (string) Str::uuid(),
        ])->assertForbidden();
        $this->assertDatabaseCount('commerce_orders', 0);
    }

    private function commercialProduct(string $slug): Product
    {
        $product = Product::query()->create([
            'slug' => $slug,
            'name' => $slug,
            'status' => 'active',
        ]);
        EntitlementPolicy::query()->create([
            'product_id' => $product->getKey(),
            'code' => 'request.'.$slug,
            'capability' => 'service.access',
            'status' => 'active',
        ]);

        return $product;
    }
}
