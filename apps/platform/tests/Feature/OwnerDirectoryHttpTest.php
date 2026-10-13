<?php

declare(strict_types=1);

namespace Tests\Feature;

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

    public function test_passkey_owner_can_edit_customer_name_without_changing_email_or_roles(): void
    {
        $owner = $this->owner();
        $customer = User::factory()->create([
            'name' => 'Original Customer',
            'email' => 'customer-before@example.org',
            'is_platform_owner' => false,
        ]);

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->patch('/operator/directory/users/'.$customer->id, [
                'name' => 'Updated Customer',
                'email' => 'attempted-takeover@example.org',
                'is_platform_owner' => true,
            ])->assertRedirect();

        $customer->refresh();
        $this->assertSame('Updated Customer', $customer->name);
        $this->assertSame('customer-before@example.org', $customer->email);
        $this->assertFalse((bool) $customer->getAttribute('is_platform_owner'));
        $this->assertDatabaseHas('operator_action_audits', [
            'actor_user_id' => $owner->id,
            'action' => 'customer.profile_name_updated',
            'outcome' => 'success',
        ]);
    }

    public function test_passkey_owner_can_edit_organization_name_without_changing_memberships(): void
    {
        $owner = $this->owner();
        $organization = app(OrganizationCreator::class)->create('Before Name', $owner->id);
        $organizationId = (string) $organization->getKey();

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->patch('/operator/directory/organizations/'.$organizationId, [
                'name' => 'After Name',
                'memberships_count' => 1000,
            ])->assertRedirect();

        $this->assertDatabaseHas('organizations', [
            'id' => $organizationId,
            'name' => 'After Name',
        ]);
        $this->assertDatabaseHas('operator_action_audits', [
            'actor_user_id' => $owner->id,
            'action' => 'customer.organization_name_updated',
            'outcome' => 'success',
        ]);
    }

    public function test_non_owner_and_guest_cannot_edit_any_customer(): void
    {
        $owner = $this->owner();
        $customer = User::factory()->create(['name' => 'Protected Customer']);
        $organization = app(OrganizationCreator::class)->create('Protected Organization', $owner->id);

        $this->patch('/operator/directory/users/'.$customer->id, [
            'name' => 'Unauthorized Rename',
        ])->assertRedirect('/login');

        $other = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($other)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->patch('/operator/directory/users/'.$customer->id, [
                'name' => 'Unauthorized Rename',
            ])->assertForbidden();
        $this->actingAs($other)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->patch('/operator/directory/organizations/'.$organization->getKey(), [
                'name' => 'Unauthorized Organization',
            ])->assertForbidden();

        $this->assertSame('Protected Customer', $customer->fresh()->name);
        $this->assertDatabaseHas('organizations', [
            'id' => (string) $organization->getKey(),
            'name' => 'Protected Organization',
        ]);
    }

    public function test_invalid_edits_reject_unknown_users_and_bad_names(): void
    {
        $owner = $this->owner();
        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->patch('/operator/directory/users/99999999', [
                'name' => 'Never Found',
            ])->assertNotFound();

        $customer = User::factory()->create(['name' => 'Protected Customer']);
        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->patch('/operator/directory/users/'.$customer->id, [
                'name' => 'x',
            ])->assertSessionHasErrors('name');
        $this->assertSame('Protected Customer', $customer->fresh()->name);
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
