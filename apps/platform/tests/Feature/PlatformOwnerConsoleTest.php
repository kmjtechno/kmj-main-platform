<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Inertia\Testing\AssertableInertia as Assert;
use KMJ\MainPlatform\Catalog\Services\ProductCatalog;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Entitlements\Services\EntitlementPolicyRegistry;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class PlatformOwnerConsoleTest extends TestCase
{
    use RefreshDatabase;

    public function test_regular_user_cannot_open_operator_console(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);

        $response = $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator');

        $response->assertForbidden();
    }

    public function test_platform_owner_without_passkey_is_rejected(): void
    {
        $user = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);

        $response = $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator');

        $response->assertForbidden();
    }

    public function test_passkey_enabled_platform_owner_can_open_operator_console(): void
    {
        $user = $this->createPasskeyOwner();

        $response = $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator');

        $response->assertOk();
        $response->assertInertia(fn (Assert $page) => $page
            ->component('operator')
            ->where('metrics.users', 1)
            ->where('metrics.organizations', 0)
            ->where('metrics.entitlements', 0)
            ->where('metrics.orders', 0)
            ->where('metrics.confirmed_orders', 0)
            ->has('recentOrders', 0));
    }

    public function test_operator_console_exposes_ready_fulfillment_state_for_confirmed_order(): void
    {
        $user = $this->createPasskeyOwner();
        [$order] = $this->createReadyOrder($user);

        $response = $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator');

        $response->assertOk();
        $response->assertInertia(fn (Assert $page) => $page
            ->component('operator')
            ->where('metrics.orders', 1)
            ->where('metrics.confirmed_orders', 1)
            ->has('recentOrders', 1)
            ->where('recentOrders.0.id', $order->getKey())
            ->where('recentOrders.0.fulfillment_state', 'ready'));
    }

    public function test_passkey_owner_can_idempotently_fulfill_ready_order(): void
    {
        $user = $this->createPasskeyOwner();
        [$order, $organization, $product] = $this->createReadyOrder($user);
        $url = '/operator/orders/'.$order->getKey().'/fulfill';

        $response = $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post($url);

        $response->assertRedirect('/operator');
        $this->assertDatabaseHas('entitlements', [
            'organization_id' => $organization->getKey(),
            'product_id' => $product->getKey(),
            'status' => 'active',
            'idempotency_key' => 'commercial-order:'.$order->getKey(),
        ]);
        $this->assertDatabaseHas('entitlement_ledger', [
            'organization_id' => $organization->getKey(),
            'event_type' => 'entitlement.issued',
        ]);

        $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post($url)
            ->assertRedirect('/operator');

        $this->assertSame(1, Entitlement::query()->count());

        $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator')
            ->assertInertia(fn (Assert $page) => $page
                ->where('recentOrders.0.id', $order->getKey())
                ->where('recentOrders.0.fulfillment_state', 'entitled'));
    }

    public function test_regular_user_cannot_fulfill_ready_order(): void
    {
        $owner = $this->createPasskeyOwner();
        [$order] = $this->createReadyOrder($owner);
        $user = User::factory()->create(['email_verified_at' => now()]);

        $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/orders/'.$order->getKey().'/fulfill')
            ->assertForbidden();

        $this->assertDatabaseCount('entitlements', 0);
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
            'name' => 'Owner passkey',
            'credential_id' => 'owner-console-test-credential-'.$user->id,
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $user;
    }

    private function createReadyOrder(User $user): array
    {
        $organization = app(OrganizationCreator::class)->create('Fulfillment Org', $user->id);
        $product = app(ProductCatalog::class)->ensureSandboxProduct(
            'fulfillment-ready-product',
            'Fulfillment Ready Product',
        );
        app(EntitlementPolicyRegistry::class)->ensure(
            $product->getKey(),
            'fulfillment.ready.default',
            'product.access',
        );
        $orders = app(CommercialOrderService::class);
        $order = $orders->request(
            $organization->getKey(),
            $product->getKey(),
            $user->id,
            'operator-fulfillment-ready',
        );
        $orders->confirm($order->getKey(), $user->id, 'INR', 9900, 'operator-test-confirmation');

        return [$order, $organization, $product];
    }
}
