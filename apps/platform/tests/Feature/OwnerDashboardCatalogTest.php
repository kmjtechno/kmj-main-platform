<?php

namespace Tests\Feature;

use App\Models\User;
use App\Services\AuthorityBootstrapper;
use App\Services\Commerce\AdminProductManager;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Inertia\Testing\AssertableInertia as Assert;
use KMJ\MainPlatform\Catalog\Models\Product;
use Tests\TestCase;

final class OwnerDashboardCatalogTest extends TestCase
{
    use RefreshDatabase;

    public function test_platform_owner_sees_every_catalog_product_even_without_an_entitlement(): void
    {
        $this->product('kmj-owner-view-a', 'Owner View A', true);
        $this->product('kmj-owner-view-b', 'Owner View B', false);
        $owner = $this->platformOwner();
        app(AuthorityBootstrapper::class)->createOrganizationWithSandboxAccess('Owner Org', $owner->id);

        $expected = Product::query()->count();

        $this->actingAs($owner)
            ->get('/dashboard')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('dashboard')
                ->has('ownerProducts', $expected)
                ->where('ownerProducts', fn ($products): bool => collect($products)->pluck('slug')->contains('kmj-owner-view-a')
                    && collect($products)->pluck('slug')->contains('kmj-owner-view-b'))
                ->where('ownerProducts', fn ($products): bool => collect($products)
                    ->every(fn (array $product): bool => $product['active_entitlements'] >= 0
                        && array_key_exists('purchase_enabled', $product)
                        && array_key_exists('licensing_enabled', $product)
                        && array_key_exists('is_public', $product))));
    }

    public function test_customers_never_receive_the_owner_product_list(): void
    {
        $this->product('kmj-owner-only-listing', 'Owner Only Listing', true);
        $customer = User::factory()->create(['email_verified_at' => now()]);
        app(AuthorityBootstrapper::class)->createOrganizationWithSandboxAccess('Customer Org', $customer->id);

        $this->actingAs($customer)
            ->get('/dashboard')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('dashboard')
                ->where('ownerProducts', null)
                ->where('canManageCodeBridgeOwnerPlan', false));
    }

    public function test_owner_flag_without_a_passkey_is_not_enough(): void
    {
        $this->product('kmj-owner-no-passkey', 'Owner No Passkey', true);
        $user = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);

        $this->actingAs($user)
            ->get('/dashboard')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page->where('ownerProducts', null));
    }

    private function product(string $slug, string $name, bool $public): void
    {
        app(AdminProductManager::class)->create([
            'slug' => $slug,
            'name' => $name,
            'status' => 'sandbox',
            'lifecycle' => 'planned',
            'is_public' => $public,
            'purchase_enabled' => false,
            'licensing_enabled' => false,
        ]);
    }

    private function platformOwner(): User
    {
        $user = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);

        DB::table('passkeys')->insert([
            'user_id' => $user->id,
            'name' => 'Owner dashboard test passkey',
            'credential_id' => 'owner-dashboard-test-credential',
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $user;
    }
}
