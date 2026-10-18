<?php

namespace Tests\Feature;

use App\Models\User;
use App\Services\Commerce\AdminProductManager;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use KMJ\MainPlatform\Catalog\Models\Product;
use Tests\TestCase;

final class OwnerProductManagementWorkspaceTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_dedicated_catalog_is_owner_only_and_requires_recent_confirmation(): void
    {
        $this->get('/operator/products')->assertRedirect('/login');

        $customer = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($customer)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/products')->assertForbidden();

        $owner = $this->owner();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/products')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('operator-products')
                ->has('products', 0));
    }

    public function test_owner_can_create_and_edit_categorized_products_without_auto_licensing(): void
    {
        $owner = $this->owner();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()]);
        $this->post('/operator/products', [
            'slug' => 'kmj-new-test-product',
            'name' => 'KMJ New Test Product',
            'category' => 'developer',
            'lifecycle' => 'planned',
            'is_public' => false,
            'purchase_enabled' => false,
            'licensing_enabled' => false,
        ])->assertRedirect();

        $product = Product::query()->where('slug', 'kmj-new-test-product')->firstOrFail();
        self::assertSame('developer', $product->category);
        self::assertFalse((bool) $product->purchase_enabled);

        $this->put('/operator/products/'.$product->getKey(), [
            'name' => 'KMJ Updated Test Product',
            'category' => 'industrial',
            'lifecycle' => 'preview',
        ])->assertRedirect();

        $product->refresh();
        self::assertSame('industrial', $product->category);
        self::assertSame('KMJ Updated Test Product', $product->name);
        self::assertFalse((bool) $product->licensing_enabled);

        $this->get('/operator/products')->assertInertia(fn (Assert $page) => $page
            ->component('operator-products')
            ->has('products', 1)
            ->where('products.0.category', 'industrial'));
    }

    public function test_invalid_category_and_premature_purchase_fail_without_mutation(): void
    {
        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()]);
        $this->post('/operator/products', [
            'slug' => 'unsafe-category',
            'name' => 'Unsafe category',
            'category' => 'arbitrary-category',
            'lifecycle' => 'available',
            'is_public' => false,
            'purchase_enabled' => false,
            'licensing_enabled' => false,
        ])->assertSessionHasErrors('category');
        self::assertSame(0, Product::query()->count());

        $product = app(AdminProductManager::class)->create([
            'slug' => 'kmj-safe-product',
            'name' => 'KMJ Safe Product',
            'category' => 'other',
            'lifecycle' => 'planned',
            'purchase_enabled' => false,
        ]);
        $this->put('/operator/products/'.$product->getKey(), [
            'lifecycle' => 'planned',
            'purchase_enabled' => true,
        ])->assertSessionHasErrors();
        self::assertFalse((bool) $product->refresh()->purchase_enabled);
    }

    public function test_owner_can_show_hide_change_lifecycle_and_reorder_complete_catalog_over_http(): void
    {
        $manager = app(AdminProductManager::class);
        $first = $manager->create([
            'slug' => 'kmj-first-acceptance',
            'name' => 'KMJ First Acceptance',
            'category' => 'developer',
            'lifecycle' => 'planned',
            'is_public' => false,
            'purchase_enabled' => false,
            'licensing_enabled' => false,
        ]);
        $second = $manager->create([
            'slug' => 'kmj-second-acceptance',
            'name' => 'KMJ Second Acceptance',
            'category' => 'business',
            'lifecycle' => 'planned',
            'is_public' => false,
            'purchase_enabled' => false,
            'licensing_enabled' => false,
        ]);

        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()]);

        $this->put('/operator/products/'.$first->getKey(), [
            'lifecycle' => 'preview',
            'is_public' => true,
        ])->assertRedirect();
        self::assertSame('preview', $first->refresh()->lifecycle);
        self::assertTrue((bool) $first->is_public);
        self::assertFalse((bool) $first->purchase_enabled);

        $this->put('/operator/products/'.$first->getKey(), [
            'is_public' => false,
        ])->assertRedirect();
        self::assertFalse((bool) $first->refresh()->is_public);

        $ids = [(string) $second->getKey(), (string) $first->getKey()];
        $this->post('/operator/products/reorder', ['ids' => $ids])->assertRedirect();
        self::assertSame(10, (int) $second->refresh()->sort_order);
        self::assertSame(20, (int) $first->refresh()->sort_order);

        $this->get('/operator/products')->assertInertia(fn (Assert $page) => $page
            ->component('operator-products')
            ->has('products', 2)
            ->where('products.0.id', (string) $second->getKey())
            ->where('products.1.id', (string) $first->getKey()));

        $this->post('/operator/products/reorder', [
            'ids' => [(string) $first->getKey()],
        ])->assertSessionHasErrors('ids');
        self::assertSame(10, (int) $second->refresh()->sort_order);
        self::assertSame(20, (int) $first->refresh()->sort_order);
    }

    public function test_guest_and_verified_nonowner_cannot_mutate_products_or_sort_order(): void
    {
        $product = app(AdminProductManager::class)->create([
            'slug' => 'kmj-guard-acceptance',
            'name' => 'KMJ Guard Acceptance',
            'lifecycle' => 'planned',
            'is_public' => false,
            'purchase_enabled' => false,
        ]);
        $id = (string) $product->getKey();

        $this->post('/operator/products', [
            'slug' => 'kmj-unauthorized-guest',
            'name' => 'Unauthorized guest',
            'lifecycle' => 'planned',
            'is_public' => false,
            'purchase_enabled' => false,
            'licensing_enabled' => false,
        ])->assertRedirect('/login');

        $this->actingAs(User::factory()->create(['email_verified_at' => now()]))
            ->withSession(['auth.password_confirmed_at' => time()])
            ->put('/operator/products/'.$id, ['is_public' => true])
            ->assertForbidden();
        $this->post('/operator/products/reorder', ['ids' => [$id]])->assertForbidden();

        self::assertFalse((bool) $product->refresh()->is_public);
        self::assertSame(10, (int) $product->sort_order);
        self::assertSame(1, Product::query()->count());
    }

    public function test_owner_product_writes_require_recent_password_confirmation(): void
    {
        $product = app(AdminProductManager::class)->create([
            'slug' => 'kmj-confirm-acceptance',
            'name' => 'KMJ Confirm Acceptance',
            'lifecycle' => 'planned',
            'is_public' => false,
            'purchase_enabled' => false,
        ]);
        $this->actingAs($this->owner());

        $this->put('/operator/products/'.$product->getKey(), [
            'is_public' => true,
        ])->assertRedirect('/user/confirm-password');

        self::assertFalse((bool) $product->refresh()->is_public);
    }

    private function owner(): User
    {
        $owner = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        DB::table('passkeys')->insert([
            'user_id' => $owner->id,
            'name' => 'Product owner passkey',
            'credential_id' => 'product-owner-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $owner;
    }
}
