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
                ->where('read_only', false)
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

    public function test_owner_can_filter_email_verified_and_unverified_customers(): void
    {
        $owner = $this->owner();
        User::factory()->create(['email_verified_at' => null]);
        User::factory()->create(['email_verified_at' => now()]);

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/directory?users_status=unverified')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('users.total', 1)
                ->where('filters.users_status', 'unverified'));

        $this->actingAs($owner)
            ->get('/operator/directory?users_status=verified')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('users.total', 2)
                ->where('filters.users_status', 'verified'));
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
                    ->where('read_only', false)
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

    public function test_owner_can_update_contact_but_cannot_set_verification_or_privileges(): void
    {
        $owner = $this->owner();
        $target = User::factory()->create([
            'email_verified_at' => null,
            'name' => 'Old User',
        ]);
        CustomerProfile::query()->create([
            'user_id' => $target->id,
            'account_type' => 'individual',
            'phone' => '+91 1234567890',
            'country' => 'India',
        ]);

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->patch('/operator/directory/users/'.$target->id.'/contact', [
                'name' => 'Updated User',
                'phone' => '+91 2222222222',
                'country' => 'India',
                'email_verified_at' => now()->toIso8601String(),
                'is_platform_owner' => true,
            ])->assertRedirect('/operator/directory');

        $this->assertDatabaseHas('users', [
            'id' => $target->id,
            'name' => 'Updated User',
            'email_verified_at' => null,
            'is_platform_owner' => false,
        ]);
        $this->assertDatabaseHas('customer_profiles', [
            'user_id' => $target->id, 'phone' => '+91 2222222222',
        ]);
        $this->assertDatabaseHas('operator_action_audits', [
            'actor_user_id' => $owner->id,
            'action' => 'directory_user_contact_updated',
        ]);
    }

    public function test_regular_user_cannot_modify_or_delete_other_accounts(): void
    {
        $target = User::factory()->create();
        $attacker = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($attacker)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->patch('/operator/directory/users/'.$target->id.'/contact', [
                'name' => 'Compromised',
            ])->assertForbidden();
        $this->actingAs($attacker)
            ->post('/operator/directory/users/'.$target->id.'/delete', [
                'confirmation' => 'DELETE_USER_'.$target->id,
            ])->assertForbidden();
        $this->assertDatabaseHas('users', ['id' => $target->id]);
    }

    public function test_owner_cannot_delete_account_with_an_organization_or_their_own_account(): void
    {
        $owner = $this->owner();
        $target = User::factory()->create(['email_verified_at' => null]);
        app(OrganizationCreator::class)->create('Paid or provisional org', $target->id);

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/directory/users/'.$target->id.'/delete', [
                'confirmation' => 'DELETE_USER_'.$target->id,
            ])->assertSessionHasErrors('user');
        $this->actingAs($owner)
            ->post('/operator/directory/users/'.$owner->id.'/delete', [
                'confirmation' => 'DELETE_USER_'.$owner->id,
            ])->assertSessionHasErrors('user');
        $this->assertDatabaseHas('users', ['id' => $target->id]);
        $this->assertDatabaseHas('users', ['id' => $owner->id]);
    }

    public function test_owner_may_delete_only_a_standalone_user_with_explicit_confirmation_and_audit(): void
    {
        $owner = $this->owner();
        $standalone = User::factory()->create(['email_verified_at' => null]);
        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/directory/users/'.$standalone->id.'/delete', [
                'confirmation' => 'DELETE_USER_'.$standalone->id,
            ])->assertRedirect('/operator/directory');
        $this->assertDatabaseMissing('users', ['id' => $standalone->id]);
        $this->assertDatabaseHas('operator_action_audits', [
            'actor_user_id' => $owner->id,
            'action' => 'directory_standalone_user_deleted',
        ]);
    }

    public function test_owner_cannot_save_whitespace_or_trimmed_short_name(): void
    {
        $owner = $this->owner();
        $target = User::factory()->create(['name' => 'Existing Name']);

        foreach (['   ', ' a '] as $invalidName) {
            $this->actingAs($owner)
                ->withSession(['auth.password_confirmed_at' => time()])
                ->patch('/operator/directory/users/'.$target->id.'/contact', [
                    'name' => $invalidName,
                ])->assertSessionHasErrors('name');
        }

        $this->assertDatabaseHas('users', [
            'id' => $target->id,
            'name' => 'Existing Name',
        ]);
    }

    public function test_owner_can_edit_legacy_user_without_a_contact_profile(): void
    {
        $owner = $this->owner();
        $legacy = User::factory()->create(['name' => 'Legacy Account']);

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->patch('/operator/directory/users/'.$legacy->id.'/contact', [
                'name' => 'Updated Legacy Account',
            ])->assertRedirect('/operator/directory');

        $this->assertDatabaseHas('users', [
            'id' => $legacy->id,
            'name' => 'Updated Legacy Account',
        ]);
        $this->assertDatabaseMissing('customer_profiles', ['user_id' => $legacy->id]);
    }

    public function test_owner_cannot_silently_clear_required_phone_or_country(): void
    {
        $owner = $this->owner();
        $target = User::factory()->create(['name' => 'Valid Contact']);
        CustomerProfile::query()->create([
            'user_id' => $target->id,
            'account_type' => 'individual',
            'phone' => '+91 1111111111',
            'country' => 'India',
        ]);

        foreach (['phone', 'country'] as $blankField) {
            $contact = ['phone' => '+91 1111111111', 'country' => 'India'];
            $contact[$blankField] = '';
            $this->actingAs($owner)
                ->withSession(['auth.password_confirmed_at' => time()])
                ->patch('/operator/directory/users/'.$target->id.'/contact', [
                    'name' => 'Changed Invalidly',
                    ...$contact,
                ])->assertSessionHasErrors($blankField);
        }

        $this->assertDatabaseHas('users', ['id' => $target->id, 'name' => 'Valid Contact']);
        $this->assertDatabaseHas('customer_profiles', [
            'user_id' => $target->id,
            'phone' => '+91 1111111111',
            'country' => 'India',
        ]);
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
