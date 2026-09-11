<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class AuthorityDashboardTest extends TestCase
{
    use RefreshDatabase;

    public function test_authenticated_user_can_create_first_authority_chain(): void
    {
        $user = User::factory()->create();

        $response = $this
            ->actingAs($user)
            ->post('/organizations', [
                'name' => 'KMJ Product Lab',
            ]);

        $response->assertRedirect(route('dashboard'));

        $this->assertDatabaseHas('organizations', [
            'name' => 'KMJ Product Lab',
        ]);
        $this->assertDatabaseHas('organization_memberships', [
            'user_id' => $user->id,
            'role' => 'owner',
        ]);
        $this->assertDatabaseHas('products', [
            'slug' => 'kmj-main-platform-sandbox',
            'status' => 'sandbox',
        ]);
        $this->assertDatabaseHas('entitlement_policies', [
            'code' => 'main-platform.sandbox.default',
            'capability' => 'sandbox.product.access',
            'status' => 'active',
        ]);
        $this->assertDatabaseHas('entitlements', [
            'capability' => 'sandbox.product.access',
            'status' => 'active',
        ]);
        $this->assertDatabaseCount('entitlement_ledger', 1);
    }

    public function test_dashboard_returns_only_the_authenticated_users_authority_records(): void
    {
        $user = User::factory()->create();
        $otherUser = User::factory()->create();

        $this->actingAs($user)->post('/organizations', ['name' => 'Visible Organization']);
        $this->actingAs($otherUser)->post('/organizations', ['name' => 'Hidden Organization']);

        $response = $this->actingAs($user)->get(route('dashboard'));

        $response->assertOk();
        $response->assertInertia(fn (Assert $page) => $page
            ->component('dashboard')
            ->has('organizations', 1)
            ->where('organizations.0.name', 'Visible Organization')
            ->where('organizations.0.role', 'owner')
            ->has('organizations.0.entitlements', 1)
            ->where('organizations.0.entitlements.0.product_name', 'KMJ Main Platform Sandbox')
            ->where('organizations.0.entitlements.0.product_slug', 'kmj-main-platform-sandbox')
            ->where('organizations.0.entitlements.0.capability', 'sandbox.product.access')
            ->where('organizations.0.entitlements.0.status', 'active'));
    }
}
