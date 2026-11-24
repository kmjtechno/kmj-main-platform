<?php

namespace Tests\Feature;

use App\Models\User;
use App\Services\Commerce\AdminProductManager;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Catalog\Models\Product;
use Tests\TestCase;

final class OwnerProductRemovalTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_owner_removes_a_never_live_product_with_the_exact_slug_and_it_is_audited(): void
    {
        $product = $this->product('qa-removal-target');
        $owner = $this->owner();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->delete('/operator/products/'.$product->getKey(), ['confirm_slug' => 'qa-removal-target'])
            ->assertRedirect();

        $this->assertDatabaseMissing('products', ['id' => $product->getKey()]);
        $this->assertDatabaseHas('operator_action_audits', [
            'actor_user_id' => $owner->id,
            'action' => 'product.delete',
            'outcome' => 'deleted',
        ]);
    }

    public function test_wrong_or_missing_slug_confirmation_keeps_the_product(): void
    {
        $product = $this->product('qa-keep-me');
        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()]);

        $this->delete('/operator/products/'.$product->getKey(), ['confirm_slug' => 'something-else'])
            ->assertSessionHasErrors('confirm_slug');
        $this->delete('/operator/products/'.$product->getKey())
            ->assertSessionHasErrors('confirm_slug');

        $this->assertDatabaseHas('products', ['id' => $product->getKey()]);
    }

    public function test_public_purchasable_or_licensable_products_cannot_be_removed(): void
    {
        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()]);

        foreach ([
            'qa-public' => ['is_public' => true],
            'qa-licensing' => ['licensing_enabled' => true],
        ] as $slug => $flags) {
            $product = $this->product($slug, $flags);
            $this->delete('/operator/products/'.$product->getKey(), ['confirm_slug' => $slug])
                ->assertSessionHasErrors('confirm_slug');
            $this->assertDatabaseHas('products', ['id' => $product->getKey()]);
        }
    }

    public function test_a_product_referenced_by_a_plan_is_refused_instead_of_deleted(): void
    {
        $product = $this->product('qa-has-plan');
        $now = now();
        DB::table('plans')->insert([
            'id' => (string) Str::uuid(), 'product_id' => $product->getKey(), 'code' => 'qa.plan', 'name' => 'QA plan',
            'pricing_model' => 'license', 'status' => 'active', 'trial_days' => 0,
            'features' => json_encode(['read' => true]), 'limits' => json_encode(['devices' => 1]),
            'created_at' => $now, 'updated_at' => $now,
        ]);

        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()])
            ->delete('/operator/products/'.$product->getKey(), ['confirm_slug' => 'qa-has-plan'])
            ->assertSessionHasErrors('confirm_slug');

        $this->assertDatabaseHas('products', ['id' => $product->getKey()]);
        $this->assertDatabaseMissing('operator_action_audits', ['action' => 'product.delete']);
    }

    public function test_non_owner_cannot_remove_a_product(): void
    {
        $product = $this->product('qa-not-yours');
        $customer = User::factory()->create(['email_verified_at' => now()]);

        $this->actingAs($customer)->withSession(['auth.password_confirmed_at' => time()])
            ->delete('/operator/products/'.$product->getKey(), ['confirm_slug' => 'qa-not-yours'])
            ->assertForbidden();

        $this->assertDatabaseHas('products', ['id' => $product->getKey()]);
    }

    /** @param array<string, mixed> $flags */
    private function product(string $slug, array $flags = []): Product
    {
        return app(AdminProductManager::class)->create(array_merge([
            'slug' => $slug, 'name' => 'QA '.$slug, 'status' => 'sandbox', 'lifecycle' => 'planned',
            'is_public' => false, 'purchase_enabled' => false, 'licensing_enabled' => false,
        ], $flags));
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
