<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\CustomerProfile;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class OwnerDirectoryHttpTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_guest_and_untrusted_users_cannot_list_customer_data(): void
    {
        $this->get('/operator/directory')->assertRedirect('/login');

        $regular = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($regular)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/directory')->assertForbidden();

        $untrustedOwner = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
        ]);
        $this->actingAs($untrustedOwner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/directory')->assertForbidden();
    }

    public function test_passkey_owner_searches_paginated_users_and_organizations_without_secrets(): void
    {
        $owner = $this->owner();
        $matching = User::factory()->create([
            'name' => 'UniqueDirectoryAlice',
            'email' => 'alice-directory-test@example.org',
            'email_verified_at' => now(),
        ]);
        CustomerProfile::query()->create([
            'user_id' => $matching->id,
            'account_type' => 'business',
            'phone' => '+44 20 7946 0123',
            'country' => 'United Kingdom',
            'company_name' => 'Unique World Cinema Ltd',
            'service_interest' => 'cinema',
        ]);
        User::factory()->create(['name' => 'UnrelatedDirectoryBob']);
        app(OrganizationCreator::class)->create('UniqueExampleOrg', $owner->id);
        app(OrganizationCreator::class)->create('AnotherOrg', $owner->id);

        $response = $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/directory?users_q=UniqueDirectoryAlice&orgs_q=UniqueExampleOrg');

        $response->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('operator-directory')
                ->where('read_only', true)
                ->where('users.total', 1)
                ->where('users.data.0.id', $matching->id)
                ->where('users.data.0.name', 'UniqueDirectoryAlice')
                ->where('users.data.0.customer_profile.account_type', 'business')
                ->where('users.data.0.customer_profile.phone', '+44 20 7946 0123')
                ->where('users.data.0.customer_profile.country', 'United Kingdom')
                ->where('users.data.0.customer_profile.company_name', 'Unique World Cinema Ltd')
                ->where('users.data.0.customer_profile.service_interest', 'cinema')
                ->where('organizations.total', 1)
                ->where('organizations.data.0.name', 'UniqueExampleOrg')
                ->where('organizations.data.0.memberships_count', 1)
                ->where('filters.users_q', 'UniqueDirectoryAlice'));
        $response->assertDontSee($matching->password);
        $response->assertDontSee('remember_token');
        $response->assertDontSee('two_factor_secret');
        $response->assertDontSee('credential_id');
    }

    public function test_user_directory_is_bounded_to_fifteen_per_page(): void
    {
        $owner = $this->owner();
        User::factory()->count(18)->create(['email_verified_at' => now()]);

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/directory')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('users.total', 19)
                ->has('users.data', 15)
                ->where('users.last_page', 2)
                ->where('organizations.total', 0));
    }

    public function test_directory_rejects_unbounded_filter_inputs(): void
    {
        $owner = $this->owner();

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/directory?users_q='.str_repeat('x', 81))
            ->assertSessionHasErrors('users_q');
    }

    public function test_owner_can_find_customer_by_company_or_contact_without_exposing_other_accounts(): void
    {
        $owner = $this->owner();
        $client = User::factory()->create([
            'name' => 'Account Holder',
            'email' => 'private-client@example.org',
        ]);
        CustomerProfile::query()->create([
            'user_id' => $client->id,
            'account_type' => 'business',
            'phone' => '+1 415 555 0134',
            'country' => 'United States',
            'company_name' => 'Acme Calibration Studio',
            'service_interest' => 'calibration',
        ]);
        User::factory()->create(['name' => 'Unrelated Account']);

        foreach (['Acme Calibration', '415 555 0134', 'United States'] as $term) {
            $this->actingAs($owner)
                ->withSession(['auth.password_confirmed_at' => time()])
                ->get('/operator/directory?users_q='.urlencode($term))
                ->assertOk()
                ->assertInertia(fn (Assert $page) => $page
                    ->where('read_only', true)
                    ->where('users.total', 1)
                    ->where('users.data.0.id', $client->id)
                    ->where('users.data.0.customer_profile.company_name', 'Acme Calibration Studio')
                    ->has('users.data', 1));
        }
    }

    public function test_directory_legacy_user_without_customer_profile_is_safe_and_nullable(): void
    {
        $owner = $this->owner();
        $legacy = User::factory()->create(['name' => 'LegacyNoProfile']);

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/directory?users_q=LegacyNoProfile')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('users.total', 1)
                ->where('users.data.0.id', $legacy->id)
                ->where('users.data.0.customer_profile', null));
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
            'name' => 'Directory owner passkey',
            'credential_id' => 'directory-owner-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $owner;
    }
}
