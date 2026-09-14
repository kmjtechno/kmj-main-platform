<?php

namespace Tests\Feature;

use App\Models\User;
use App\Services\Commerce\CommercialProductPublisher;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Catalog\Services\ProductCatalog;
use KMJ\MainPlatform\Commerce\Models\CommercialOrder;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class ManualSalesFlowTest extends TestCase
{
    use RefreshDatabase;

    public function test_organization_owner_can_idempotently_request_active_product(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);
        $organization = app(OrganizationCreator::class)->create('Buyer Org', $user->id);
        $product = app(CommercialProductPublisher::class)->publish('buyer-product', 'Buyer Product');
        $payload = [
            'organization_id' => $organization->getKey(),
            'product_id' => $product->getKey(),
            'idempotency_key' => 'purchase-request-1',
        ];

        $this->actingAs($user)
            ->post('/purchase/orders', $payload)
            ->assertRedirect('/purchase');

        $this->actingAs($user)
            ->post('/purchase/orders', $payload)
            ->assertRedirect('/purchase');

        $this->assertSame(1, CommercialOrder::query()->count());
        $this->assertDatabaseHas('commerce_orders', [
            'organization_id' => $organization->getKey(),
            'product_id' => $product->getKey(),
            'requester_user_id' => $user->id,
            'status' => 'requested',
            'idempotency_key' => 'purchase-request-1',
        ]);
    }

    public function test_non_member_cannot_request_purchase_for_another_organization(): void
    {
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $outsider = User::factory()->create(['email_verified_at' => now()]);
        $organization = app(OrganizationCreator::class)->create('Protected Org', $owner->id);
        $product = app(CommercialProductPublisher::class)->publish('protected-product', 'Protected Product');

        $this->actingAs($outsider)
            ->post('/purchase/orders', [
                'organization_id' => $organization->getKey(),
                'product_id' => $product->getKey(),
                'idempotency_key' => 'outsider-attempt',
            ])
            ->assertForbidden();

        $this->assertDatabaseCount('commerce_orders', 0);
    }

    public function test_platform_owner_can_activate_commercial_product_with_fulfillment_policy(): void
    {
        $operator = $this->createPasskeyOwner();

        $this->actingAs($operator)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/products', [
                'name' => 'KMJ Revenue Product',
                'slug' => 'kmj-revenue-product',
            ])
            ->assertRedirect('/operator');

        $product = app(ProductCatalog::class)
            ->ensureCommercialProduct('kmj-revenue-product', 'KMJ Revenue Product');

        $this->assertDatabaseHas('products', [
            'id' => $product->getKey(),
            'slug' => 'kmj-revenue-product',
            'name' => 'KMJ Revenue Product',
            'status' => 'active',
        ]);
        $this->assertDatabaseHas('entitlement_policies', [
            'product_id' => $product->getKey(),
            'code' => 'commercial.'.$product->getKey().'.default',
            'capability' => 'product.access',
            'status' => 'active',
        ]);
    }

    public function test_payment_confirmation_does_not_grant_access_until_explicit_fulfillment(): void
    {
        $customer = User::factory()->create(['email_verified_at' => now()]);
        $operator = $this->createPasskeyOwner();
        $organization = app(OrganizationCreator::class)->create('Paid Buyer', $customer->id);
        $product = app(CommercialProductPublisher::class)->publish('paid-product', 'Paid Product');
        $order = app(CommercialOrderService::class)->request(
            $organization->getKey(),
            $product->getKey(),
            $customer->id,
            'paid-order-1',
        );

        $this->actingAs($operator)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/orders/'.$order->getKey().'/confirm', [
                'currency' => 'INR',
                'amount_minor' => 499900,
                'confirmation_reference' => 'UTR-FAST-EARNING-001',
            ])
            ->assertRedirect('/operator');

        $this->assertDatabaseHas('commerce_orders', [
            'id' => $order->getKey(),
            'status' => 'confirmed',
            'currency' => 'INR',
            'amount_minor' => 499900,
            'confirmation_reference' => 'UTR-FAST-EARNING-001',
        ]);
        $this->assertSame(0, Entitlement::query()->count());

        $this->actingAs($operator)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/orders/'.$order->getKey().'/fulfill')
            ->assertRedirect('/operator');

        $this->assertDatabaseHas('entitlements', [
            'organization_id' => $organization->getKey(),
            'product_id' => $product->getKey(),
            'status' => 'active',
            'idempotency_key' => 'commercial-order:'.$order->getKey(),
        ]);
    }

    public function test_regular_user_cannot_confirm_payment(): void
    {
        $customer = User::factory()->create(['email_verified_at' => now()]);
        $organization = app(OrganizationCreator::class)->create('Customer Org', $customer->id);
        $product = app(CommercialProductPublisher::class)->publish('customer-product', 'Customer Product');
        $order = app(CommercialOrderService::class)->request(
            $organization->getKey(),
            $product->getKey(),
            $customer->id,
            'customer-order-1',
        );

        $this->actingAs($customer)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/orders/'.$order->getKey().'/confirm', [
                'currency' => 'INR',
                'amount_minor' => 10000,
                'confirmation_reference' => 'FORBIDDEN-CONFIRM',
            ])
            ->assertForbidden();

        $this->assertDatabaseHas('commerce_orders', [
            'id' => $order->getKey(),
            'status' => 'requested',
        ]);
    }

    private function createPasskeyOwner(): User
    {
        $user = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);

        DB::table('passkeys')->insert([
            'user_id' => $user->id,
            'name' => 'Revenue owner passkey',
            'credential_id' => 'manual-sales-owner-'.$user->id,
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $user;
    }
}
