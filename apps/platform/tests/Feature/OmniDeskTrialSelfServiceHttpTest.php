<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\OmniDesk\OmniDeskAutomaticTrialProvisioner;
use App\Services\Licensing\OmniDeskLicenseContract;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;
use Inertia\Testing\AssertableInertia as Assert;
use KMJ\MainPlatform\Catalog\Models\Plan;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class OmniDeskTrialSelfServiceHttpTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    /** @return array{user:User,organization_id:string} */
    private function ready(): array
    {
        config()->set('omnidesk-licensing.trial_self_service_enabled', true);
        $user = User::factory()->create(['email_verified_at' => now()]);
        $organization = app(OrganizationCreator::class)->create('Eligible trial organization', $user->id);
        $product = Product::query()->create([
            'slug' => OmniDeskLicenseContract::PRODUCT_SLUG,
            'name' => 'KMJ OmniDesk',
            'status' => 'active',
            'lifecycle' => 'public-beta',
            'is_public' => true,
            'purchase_enabled' => false,
            'licensing_enabled' => true,
        ]);
        Plan::query()->create([
            'product_id' => $product->getKey(),
            'code' => OmniDeskAutomaticTrialProvisioner::TRIAL_PLAN,
            'name' => 'First-party trial',
            'pricing_model' => 'trial',
            'billing_interval' => null,
            'currency' => null,
            'amount_minor' => null,
            'status' => 'active',
            'trial_days' => 14,
            'features' => [],
            'limits' => [],
        ]);
        EntitlementPolicy::query()->create([
            'product_id' => $product->getKey(),
            'code' => OmniDeskAutomaticTrialProvisioner::TRIAL_POLICY,
            'capability' => OmniDeskLicenseContract::CAPABILITY,
            'status' => 'active',
        ]);

        return ['user' => $user, 'organization_id' => (string) $organization->getKey()];
    }

    public function test_trial_self_service_route_uses_web_csrf_session_and_verified_guards(): void
    {
        $route = Route::getRoutes()->getByName('licensing.omnidesk.trial');
        self::assertNotNull($route);
        self::assertSame(['POST'], $route->methods());
        self::assertContains('web', $route->gatherMiddleware());
        self::assertContains('auth', $route->gatherMiddleware());
        self::assertContains('verified', $route->gatherMiddleware());
        self::assertContains('throttle:3,1', $route->gatherMiddleware());

        $this->post('/licensing/omnidesk/trial', [
            'organization_id' => '00000000-0000-4000-8000-000000000000',
        ])->assertRedirect('/login');
    }

    public function test_feature_flag_blocks_direct_posts_without_mutating_hub(): void
    {
        $f = $this->ready();
        config()->set('omnidesk-licensing.trial_self_service_enabled', false);
        $this->actingAs($f['user'])->post('/licensing/omnidesk/trial', [
            'organization_id' => $f['organization_id'],
        ])->assertStatus(503);
        $this->actingAs($f['user'])->get('/licensing')
            ->assertInertia(fn (Assert $page) => $page
                ->component('licensing-hub')
                ->where('omnidesk_trial_organizations', []));
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('entitlements', 0);
    }

    public function test_one_click_trial_from_verified_owner_is_idempotent_and_never_signs_device_rights(): void
    {
        $f = $this->ready();
        $this->actingAs($f['user'])->get('/licensing')
            ->assertInertia(fn (Assert $page) => $page
                ->component('licensing-hub')
                ->has('omnidesk_trial_organizations', 1)
                ->where('omnidesk_trial_organizations.0.organization_id', $f['organization_id'])
                ->where('omnidesk_trial_organizations.0.trial_days', 14));

        $this->actingAs($f['user'])->post('/licensing/omnidesk/trial', [
            'organization_id' => $f['organization_id'],
        ])->assertRedirect(route('licensing.hub'));
        $first = DB::table('kslp_licenses')->sole();
        $endsAt = (string) $first->expires_at;
        $this->assertDatabaseCount('kslp_licenses', 1);
        $this->assertDatabaseCount('entitlements', 1);
        $this->assertDatabaseCount('kslp_activations', 0);
        $this->assertDatabaseCount('omnidesk_activation_bindings', 0);
        $this->assertDatabaseCount('commerce_orders', 0);

        $this->actingAs($f['user'])->post('/licensing/omnidesk/trial', [
            'organization_id' => $f['organization_id'],
        ])->assertRedirect(route('licensing.hub'));
        $this->assertDatabaseCount('kslp_licenses', 1);
        $this->assertDatabaseCount('entitlements', 1);
        $this->assertDatabaseCount('kslp_license_events', 1);
        self::assertSame($endsAt, (string) DB::table('kslp_licenses')->value('expires_at'));

        // After a trial is consumed, its action vanishes; there is no repeat
        // onboarding button and no silently generated signed license.
        $this->actingAs($f['user'])->get('/licensing')
            ->assertInertia(fn (Assert $page) => $page
                ->where('omnidesk_trial_organizations', []));
    }

    public function test_unverified_account_is_rejected_even_when_flags_allow_trials(): void
    {
        $f = $this->ready();
        $f['user']->forceFill(['email_verified_at' => null])->save();
        $this->actingAs($f['user'])->post('/licensing/omnidesk/trial', [
            'organization_id' => $f['organization_id'],
        ])->assertRedirect(route('verification.notice'));
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('entitlements', 0);
    }

    public function test_foreign_organization_is_never_selected_by_post_data(): void
    {
        $f = $this->ready();
        $other = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($other)->post('/licensing/omnidesk/trial', [
            'organization_id' => $f['organization_id'],
        ])->assertForbidden();
        $this->actingAs($other)->get('/licensing')
            ->assertInertia(fn (Assert $page) => $page
                ->where('omnidesk_trial_organizations', []));
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('entitlements', 0);
    }

    public function test_member_role_downgrade_removes_button_and_trial_issue_authority(): void
    {
        $f = $this->ready();
        OrganizationMembership::query()
            ->where('organization_id', $f['organization_id'])
            ->where('user_id', $f['user']->getKey())
            ->update(['role' => 'member']);

        $this->actingAs($f['user'])->get('/licensing')
            ->assertInertia(fn (Assert $page) => $page
                ->where('omnidesk_trial_organizations', []));
        $this->actingAs($f['user'])->post('/licensing/omnidesk/trial', [
            'organization_id' => $f['organization_id'],
        ])->assertForbidden();
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('entitlements', 0);
    }

    public function test_pre_alpha_catalog_cannot_expose_or_issue_trial_after_manual_flag_override(): void
    {
        $f = $this->ready();
        Product::query()
            ->where('slug', OmniDeskLicenseContract::PRODUCT_SLUG)
            ->update(['lifecycle' => 'research']);
        $this->actingAs($f['user'])->get('/licensing')
            ->assertInertia(fn (Assert $page) => $page
                ->where('omnidesk_trial_organizations', []));
        $this->actingAs($f['user'])->post('/licensing/omnidesk/trial', [
            'organization_id' => $f['organization_id'],
        ])->assertSessionHasErrors('trial');
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('entitlements', 0);
    }

    public function test_invalid_org_argument_never_reaches_issuance(): void
    {
        $f = $this->ready();
        $this->actingAs($f['user'])->post('/licensing/omnidesk/trial', [
            'organization_id' => 'not-a-uuid',
        ])->assertSessionHasErrors('organization_id');
        $this->assertDatabaseCount('kslp_licenses', 0);
    }
}
