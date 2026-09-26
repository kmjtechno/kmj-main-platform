<?php

namespace Tests\Feature;

use App\Models\User;
use App\Services\AuthorityBootstrapper;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class CustomerDashboardProductAccessTest extends TestCase
{
    use RefreshDatabase;

    public function test_customer_dashboard_only_exposes_the_authenticated_users_organizations_and_entitlements(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);
        $otherUser = User::factory()->create(['email_verified_at' => now()]);

        app(AuthorityBootstrapper::class)->createOrganizationWithSandboxAccess(
            'Customer One',
            $user->id,
        );
        app(AuthorityBootstrapper::class)->createOrganizationWithSandboxAccess(
            'Customer Two',
            $otherUser->id,
        );

        $this->actingAs($user)
            ->get('/dashboard')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('dashboard')
                ->has('organizations', 1)
                ->where('organizations.0.name', 'Customer One')
                ->has('organizations.0.entitlements', 1)
                ->where(
                    'organizations.0.entitlements.0.product_slug',
                    'kmj-main-platform-sandbox',
                )
                ->where('organizations.0.entitlements.0.status', 'active'));
    }
}
