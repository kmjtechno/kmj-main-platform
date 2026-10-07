<?php

namespace Tests\Feature;

use App\Models\User;
use App\Services\AuthorityBootstrapper;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Inertia\Testing\AssertableInertia as Assert;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use Tests\TestCase;

final class CustomerServiceManagementTest extends TestCase
{
    use RefreshDatabase;

    public function test_authorized_customer_can_manage_own_product_without_invented_release(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);
        $organization = app(AuthorityBootstrapper::class)
            ->createOrganizationWithSandboxAccess('My KMJ Company', $user->id);
        $entitlement = Entitlement::query()
            ->where('organization_id', $organization->getKey())
            ->firstOrFail();

        $this->actingAs($user)
            ->get('/services/entitlements/'.$entitlement->getKey())
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('services/show')
                ->where('organization.name', 'My KMJ Company')
                ->where('entitlement.id', (string) $entitlement->getKey())
                ->where('entitlement.status', 'active')
                ->where('entitlement.product_slug', 'kmj-main-platform-sandbox')
                ->where('release', null)
                ->etc());
    }

    public function test_private_service_details_never_expose_another_organizations_entitlement(): void
    {
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $intruder = User::factory()->create(['email_verified_at' => now()]);
        $organization = app(AuthorityBootstrapper::class)
            ->createOrganizationWithSandboxAccess('Private KMJ Org', $owner->id);
        $entitlement = Entitlement::query()
            ->where('organization_id', $organization->getKey())
            ->firstOrFail();

        $this->get('/services/entitlements/'.$entitlement->getKey())
            ->assertRedirect(route('login'));

        $this->actingAs($intruder)
            ->get('/services/entitlements/'.$entitlement->getKey())
            ->assertNotFound();

        $this->actingAs($intruder)
            ->get('/services/entitlements/unknown-entitlement')
            ->assertNotFound();
    }
}
