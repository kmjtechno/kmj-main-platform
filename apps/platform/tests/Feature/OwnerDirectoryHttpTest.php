<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AiProvider;
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

    public function test_owner_cannot_delete_shared_organization_or_their_own_account(): void
    {
        $owner = $this->owner();
        $target = User::factory()->create(['email_verified_at' => null]);
        $other = User::factory()->create(['email_verified_at' => now()]);
        $organization = app(OrganizationCreator::class)->create('Shared organization', $target->id);
        DB::table('organization_memberships')->insert([
            'id' => (string) Str::uuid(),
            'organization_id' => $organization->id,
            'user_id' => $other->id,
            'role' => 'member',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

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
        $this->assertDatabaseHas('users', ['id' => $other->id]);
        $this->assertDatabaseHas('users', ['id' => $owner->id]);
        $this->assertDatabaseHas('organizations', ['id' => $organization->id]);
        $this->assertDatabaseHas('organization_memberships', [
            'organization_id' => $organization->id, 'user_id' => $other->id,
        ]);
    }

    public function test_owner_deletes_customer_and_all_private_signup_data_atomically(): void
    {
        $owner = $this->owner();
        $target = User::factory()->create(['email_verified_at' => null]);
        $organization = app(OrganizationCreator::class)->create('Only signup organization', $target->id);
        CustomerProfile::query()->create([
            'user_id' => $target->id,
            'account_type' => 'individual',
            'phone' => '+91 2222222222',
            'country' => 'India',
        ]);
        DB::table('password_reset_tokens')->insert([
            'email' => $target->email,
            'token' => 'test-only-reset-token',
            'created_at' => now(),
        ]);

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/directory/users/'.$target->id.'/delete', [
                'confirmation' => 'DELETE_USER_'.$target->id,
            ])->assertRedirect('/operator/directory');

        $this->assertDatabaseMissing('users', ['id' => $target->id]);
        $this->assertDatabaseMissing('customer_profiles', ['user_id' => $target->id]);
        $this->assertDatabaseMissing('organization_memberships', [
            'organization_id' => $organization->id,
        ]);
        $this->assertDatabaseMissing('organizations', ['id' => $organization->id]);
        $this->assertDatabaseMissing('password_reset_tokens', ['email' => $target->email]);
        $this->assertDatabaseHas('users', ['id' => $owner->id]);
        $this->assertDatabaseHas('operator_action_audits', [
            'actor_user_id' => $owner->id,
            'action' => 'directory_customer_signup_graph_deleted',
        ]);
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
            'action' => 'directory_customer_signup_graph_deleted',
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

    public function test_owner_may_delete_three_distinct_empty_signup_organizations_sequentially(): void
    {
        $owner = $this->owner();
        $targets = [];
        foreach (range(1, 3) as $index) {
            $account = User::factory()->create(['email_verified_at' => null]);
            $organization = app(OrganizationCreator::class)->create(
                'Isolated customer '.$index,
                $account->id,
            );
            $targets[] = ['user' => $account->id, 'org' => $organization->id];
        }

        foreach ($targets as $target) {
            $this->actingAs($owner)
                ->withSession(['auth.password_confirmed_at' => time()])
                ->post('/operator/directory/users/'.$target['user'].'/delete', [
                    'confirmation' => 'DELETE_USER_'.$target['user'],
                ])->assertRedirect('/operator/directory');
            $this->assertDatabaseMissing('users', ['id' => $target['user']]);
            $this->assertDatabaseMissing('organizations', ['id' => $target['org']]);
        }

        $this->assertSame(3, DB::table('operator_action_audits')
            ->where('actor_user_id', $owner->id)
            ->where('action', 'directory_customer_signup_graph_deleted')->count());
        $this->assertDatabaseHas('users', ['id' => $owner->id]);
    }

    public function test_customer_with_business_organization_reference_is_never_cascade_deleted(): void
    {
        $owner = $this->owner();
        $target = User::factory()->create(['email_verified_at' => null]);
        $organization = app(OrganizationCreator::class)->create('Active organization', $target->id);
        AiProvider::query()->create([
            'organization_id' => $organization->id,
            'name' => 'Active provider',
            'preset' => 'github',
            'kind' => 'openai-compatible',
            'base_url' => 'https://models.github.ai/inference',
            'api_key' => 'test-only-key-123456789',
            'key_last4' => '6789',
            'enabled' => true,
            'free_only' => true,
        ]);

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/directory/users/'.$target->id.'/delete', [
                'confirmation' => 'DELETE_USER_'.$target->id,
            ])->assertSessionHasErrors('user');

        $this->assertDatabaseHas('users', ['id' => $target->id]);
        $this->assertDatabaseHas('organizations', ['id' => $organization->id]);
        $this->assertDatabaseHas('ai_providers', ['organization_id' => $organization->id]);
    }

    public function test_owner_bulk_deletes_only_two_explicitly_selected_private_signup_graphs(): void
    {
        $owner = $this->owner();
        $selected = [];
        $organizations = [];

        foreach (range(1, 2) as $index) {
            $account = User::factory()->create();
            $organization = app(OrganizationCreator::class)
                ->create('Selected signup '.$index, $account->id);
            CustomerProfile::query()->create([
                'user_id' => $account->id,
                'account_type' => 'individual',
                'phone' => '+91 1111111111',
                'country' => 'India',
            ]);
            $selected[] = $account->id;
            $organizations[] = $organization->id;
        }
        $notSelected = User::factory()->create();

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/directory/users/bulk-delete', [
                'user_ids' => $selected,
            ])->assertRedirect('/operator/directory');

        foreach ($selected as $id) {
            $this->assertDatabaseMissing('users', ['id' => $id]);
            $this->assertDatabaseMissing('customer_profiles', ['user_id' => $id]);
        }
        foreach ($organizations as $orgId) {
            $this->assertDatabaseMissing('organizations', ['id' => $orgId]);
        }
        $this->assertDatabaseHas('users', ['id' => $notSelected->id]);
        $this->assertSame(2, DB::table('operator_action_audits')
            ->where('actor_user_id', $owner->id)
            ->where('action', 'directory_customer_signup_graph_deleted')->count());
    }

    public function test_bulk_delete_is_all_or_nothing_when_one_customer_has_a_shared_org(): void
    {
        $owner = $this->owner();
        $safe = User::factory()->create();
        $safeOrg = app(OrganizationCreator::class)->create('Disposable signup', $safe->id);
        $blocked = User::factory()->create();
        $blockedOrg = app(OrganizationCreator::class)->create('Shared paid org', $blocked->id);
        $member = User::factory()->create();
        DB::table('organization_memberships')->insert([
            'id' => (string) Str::uuid(),
            'organization_id' => $blockedOrg->id,
            'user_id' => $member->id,
            'role' => 'member',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/directory/users/bulk-delete', [
                'user_ids' => [$safe->id, $blocked->id],
            ])->assertSessionHasErrors('user_ids');

        $this->assertDatabaseHas('users', ['id' => $safe->id]);
        $this->assertDatabaseHas('users', ['id' => $blocked->id]);
        $this->assertDatabaseHas('organizations', ['id' => $safeOrg->id]);
        $this->assertDatabaseHas('organizations', ['id' => $blockedOrg->id]);
        $this->assertSame(0, DB::table('operator_action_audits')
            ->where('actor_user_id', $owner->id)
            ->where('action', 'directory_customer_signup_graph_deleted')->count());
    }

    public function test_untrusted_account_cannot_bulk_delete_selected_users(): void
    {
        $customer = User::factory()->create(['email_verified_at' => now()]);
        $targets = User::factory()->count(2)->create();
        $this->actingAs($customer)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/directory/users/bulk-delete', [
                'user_ids' => $targets->pluck('id')->all(),
            ])->assertForbidden();

        foreach ($targets as $target) {
            $this->assertDatabaseHas('users', ['id' => $target->id]);
        }
    }

    public function test_bulk_delete_refuses_duplicate_overlimit_and_owner_ids_without_mutation(): void
    {
        $owner = $this->owner();
        $targets = User::factory()->count(16)->create();
        $ids = $targets->pluck('id')->all();

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/directory/users/bulk-delete', [
                'user_ids' => [$ids[0], $ids[0]],
            ])->assertSessionHasErrors('user_ids.1');

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/directory/users/bulk-delete', [
                'user_ids' => $ids,
            ])->assertSessionHasErrors('user_ids');

        // Two prior requests reach this endpoint's strict 2/minute throttle.
        // Test owner-target protection in its own request below.
        $this->assertSame(17, DB::table('users')->count());
        $this->assertSame(0, DB::table('operator_action_audits')
            ->where('action', 'directory_customer_signup_graph_deleted')->count());
    }

    public function test_bulk_delete_rejects_owner_account_before_any_mutation(): void
    {
        $owner = $this->owner();
        $target = User::factory()->create();
        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/directory/users/bulk-delete', [
                'user_ids' => [$target->id, $owner->id],
            ])->assertSessionHasErrors('user_ids');

        $this->assertDatabaseHas('users', ['id' => $target->id]);
        $this->assertDatabaseHas('users', ['id' => $owner->id]);
        $this->assertSame(0, DB::table('operator_action_audits')
            ->where('action', 'directory_customer_signup_graph_deleted')->count());
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
