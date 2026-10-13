<?php

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Organizations\Models\Organization;
use Tests\TestCase;

final class OwnerLicensingCenterHttpTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_license_directory_remains_owner_and_step_up_only(): void
    {
        $this->get('/operator/kslp')->assertRedirect('/login');

        $customer = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($customer)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/kslp')->assertForbidden();
    }

    public function test_owner_can_find_any_license_customer_and_update_an_existing_plan_with_audit(): void
    {
        $owner = $this->owner();
        $customer = User::factory()->create([
            'name' => 'License Customer Alice',
            'email' => 'licensing-alice@example.test',
        ]);
        $control = app(KslpLicenseControlPlane::class);
        $target = $control->issue((string) $customer->id, 'trial', (string) $owner->id, 'owner issue');
        $control->issue('different-customer', 'business', (string) $owner->id, 'owner issue');

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/kslp?customer_q='.$customer->id.'&plan=trial')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('operator-kslp')
                ->where('matchingCount', 1)
                ->has('licenses', 1)
                ->where('licenses.0.customer_id', (string) $customer->id)
                ->where('filters.plan', 'trial')
                ->where('filters.customer_q', (string) $customer->id)
                ->where('customerOptions', fn ($users): bool => collect($users)
                    ->pluck('id')->contains((string) $customer->id)));

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/kslp?customer_q=licensing-alice%40example.test')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('operator-kslp')
                ->where('matchingCount', 1)
                ->where('licenses.0.id', $target['id']));

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/kslp/licenses/'.$target['id'].'/action', [
                'action' => 'change_plan',
                'plan' => 'professional',
                'reason' => 'Approved customer plan upgrade',
            ])->assertRedirect(route('operator.kslp'));

        $this->assertDatabaseHas('kslp_licenses', [
            'id' => $target['id'],
            'customer_id' => $customer->id,
            'plan' => 'professional',
        ]);
        $this->assertDatabaseHas('kslp_license_events', [
            'license_id' => $target['id'],
            'action' => 'plan_changed',
            'reason' => 'Approved customer plan upgrade',
        ]);
    }

    public function test_filters_are_bounded_and_cannot_mutate_licenses(): void
    {
        $owner = $this->owner();
        $license = app(KslpLicenseControlPlane::class)->issue('safe-subject', 'trial', (string) $owner->id);

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/kslp?customer_q='.str_repeat('a', 97))
            ->assertSessionHasErrors('customer_q');

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/kslp?plan=owner-unlimited')
            ->assertSessionHasErrors('plan');

        $this->assertDatabaseHas('kslp_licenses', [
            'id' => $license['id'],
            'plan' => 'trial',
        ]);
    }

    public function test_owner_can_view_other_product_entitlements_without_issuing_a_license(): void
    {
        $organization = Organization::query()->create(['name' => 'Cinema Customer Group']);
        $product = Product::query()->create([
            'slug' => 'kmj-cinema-test',
            'name' => 'KMJ Cinema Test',
            'status' => 'sandbox',
        ]);
        $policy = EntitlementPolicy::query()->create([
            'product_id' => $product->getKey(),
            'code' => 'cinema.test.access',
            'capability' => 'cinema.read',
            'status' => 'active',
        ]);
        $entitlement = Entitlement::query()->create([
            'organization_id' => $organization->getKey(),
            'product_id' => $product->getKey(),
            'policy_id' => $policy->getKey(),
            'capability' => 'cinema.read',
            'status' => 'active',
            'idempotency_key' => 'cinema-owner-read-test',
            'starts_at' => now(),
            'ends_at' => null,
        ]);

        $this->actingAs($this->owner())
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/kslp?customer_q=Cinema%20Customer%20Group')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('operator-kslp')
                ->has('productEntitlements', 1)
                ->where('productEntitlements.0.product_slug', 'kmj-cinema-test')
                ->where('productEntitlements.0.organization_name', 'Cinema Customer Group')
                ->where('productEntitlements.0.status', 'active'));

        $this->assertDatabaseHas('entitlements', [
            'id' => $entitlement->getKey(),
            'status' => 'active',
        ]);
        $this->assertDatabaseCount('kslp_licenses', 0);
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
            'name' => 'Licensing owner passkey',
            'credential_id' => 'licensing-owner-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $owner;
    }
}
