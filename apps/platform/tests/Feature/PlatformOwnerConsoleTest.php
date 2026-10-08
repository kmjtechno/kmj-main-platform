<?php

namespace Tests\Feature;

use App\Models\LicenseAuditEvent;
use App\Models\User;
use App\Services\Commerce\CloudOSProductCatalog;
use App\Services\Commerce\KmjProductCatalog;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Inertia\Testing\AssertableInertia as Assert;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class PlatformOwnerConsoleTest extends TestCase
{
    use RefreshDatabase;

    public function test_super_admin_development_profile_requires_verified_owner_passkey(): void
    {
        $url = '/operator/super-admin/development-profile';

        $this->getJson($url)->assertUnauthorized();

        $regular = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($regular)->withSession(['auth.password_confirmed_at' => time()])
            ->getJson($url)->assertForbidden();

        $owner = $this->createPasskeyOwner();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->getJson($url)->assertForbidden();

        $owner->forceFill([
            'email' => 'kmjtechno.net@gmail.com',
            'email_verified_at' => null,
        ])->save();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->getJson($url)->assertForbidden();

        $owner->forceFill(['email_verified_at' => now()])->save();
        app(KmjProductCatalog::class)->syncAll();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->getJson($url)
            ->assertOk()
            ->assertJsonPath('profile', 'kmj.super-admin.hyperspeed')
            ->assertJsonPath('subject.email', $owner->email)
            ->assertJsonPath('scope.logical_task_backlog', 'unmetered')
            ->assertJsonPath('execution.max_parallel_jobs', 'signed-entitlement-and-current-resources')
            ->assertJsonPath('cost.unapproved_spend_inr_minor', 0)
            ->assertJsonPath('cost.automatic_paid_fallback_enabled', false)
            ->assertJsonPath('grants_product_license', false)
            ->assertJsonPath('changes_entitlements', false)
            ->assertJsonCount(15, 'scope.registered_product_slugs');
    }

    public function test_confirmed_super_admin_email_does_not_grant_owner_access(): void
    {
        $user = User::factory()->create([
            'email' => 'kmjtechno.net@gmail.com',
            'email_verified_at' => now(),
            'is_platform_owner' => false,
        ]);

        $this->actingAs($user)->withSession(['auth.password_confirmed_at' => time()])
            ->getJson('/operator/super-admin/development-profile')
            ->assertForbidden();

        $user->forceFill([
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ])->save();

        // Even an owner with the exact confirmed email needs a registered passkey.
        $this->actingAs($user)->withSession(['auth.password_confirmed_at' => time()])
            ->getJson('/operator/super-admin/development-profile')
            ->assertForbidden();
    }

    public function test_other_verified_platform_owner_cannot_open_single_account_super_admin_profile(): void
    {
        $other = $this->createPasskeyOwner();
        $this->actingAs($other)->withSession(['auth.password_confirmed_at' => time()])
            ->getJson('/operator/super-admin/development-profile')
            ->assertForbidden();
    }

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

    public function test_operator_console_exposes_canonical_product_and_licensing_matrix(): void
    {
        $user = $this->createPasskeyOwner();
        app(KmjProductCatalog::class)->syncAll();

        $response = $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator');

        $response->assertOk();
        $response->assertInertia(fn (Assert $page) => $page
            ->component('operator')
            ->has('catalogProducts', 15)
            ->where('catalogProducts.0.active_policy_count', 1)
            ->where('catalogProducts.0.active_entitlement_count', 0));
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
            ->where('recentOrders.0.fulfillment_state', 'ready')
            ->where('recentOrders.0.entitlement_id', null)
            ->where('recentOrders.0.can_manage_license', false));
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
        $entitlement = Entitlement::query()->firstOrFail();

        $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator')
            ->assertInertia(fn (Assert $page) => $page
                ->where('recentOrders.0.id', $order->getKey())
                ->where('recentOrders.0.fulfillment_state', 'entitled')
                ->where('recentOrders.0.entitlement_id', $entitlement->getKey())
                ->where('recentOrders.0.can_manage_license', true));
    }

    public function test_passkey_owner_can_issue_sandbox_license_from_entitled_order(): void
    {
        $user = $this->createPasskeyOwner();
        [$order] = $this->createReadyOrder($user);

        $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/orders/'.$order->getKey().'/fulfill')
            ->assertRedirect('/operator');

        $response = $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/orders/'.$order->getKey().'/sandbox-license');

        $response->assertRedirect('/sandbox-licenses');
        $response->assertSessionHas('sandbox_license.token');
        $response->assertSessionHas('sandbox_license.validation.valid', true);

        $this->assertDatabaseHas('license_audit_events', [
            'action' => 'sandbox_license.issued',
            'status' => 'success',
        ]);
        $event = LicenseAuditEvent::query()->latest('id')->firstOrFail();
        $this->assertSame('operator_handoff', $event->getAttribute('metadata')['source'] ?? null);
        $this->assertSame($order->getKey(), $event->getAttribute('metadata')['commercial_order_id'] ?? null);
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
        $products = app(KmjProductCatalog::class)->syncAll();
        $product = $products[CloudOSProductCatalog::SLUG];
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
