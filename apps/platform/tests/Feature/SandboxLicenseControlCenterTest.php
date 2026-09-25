<?php

namespace Tests\Feature;

use App\Models\DomainOutboxMessage;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class SandboxLicenseControlCenterTest extends TestCase
{
    use RefreshDatabase;

    public function test_owner_can_issue_validate_and_revoke_sandbox_license_from_control_surface(): void
    {
        $user = User::factory()->create();

        $this->actingAs($user)->post('/organizations', [
            'name' => 'KMJ License Lab',
        ])->assertRedirect(route('dashboard'));

        $entitlement = DB::table('entitlements')->first();
        self::assertNotNull($entitlement);

        $issueResponse = $this->actingAs($user)->post('/sandbox-licenses', [
            'organization_id' => $entitlement->organization_id,
            'entitlement_id' => $entitlement->id,
        ]);

        $issueResponse->assertRedirect(route('sandbox-licenses.index'));
        $issueResponse->assertSessionHas('sandbox_license.validation.valid', true);
        $this->assertDatabaseHas('license_audit_events', [
            'actor_id' => $user->id,
            'organization_id' => $entitlement->organization_id,
            'action' => 'sandbox_license.issued',
            'status' => 'success',
        ]);

        $license = session('sandbox_license.token');
        self::assertIsString($license);
        self::assertNotSame('', $license);

        $validateResponse = $this->actingAs($user)->post('/sandbox-licenses/validate', [
            'organization_id' => $entitlement->organization_id,
            'license' => $license,
        ]);

        $validateResponse->assertRedirect(route('sandbox-licenses.index'));
        $validateResponse->assertSessionHas('sandbox_license_validation.valid', true);
        $this->assertDatabaseHas('license_audit_events', [
            'actor_id' => $user->id,
            'organization_id' => $entitlement->organization_id,
            'action' => 'sandbox_license.validated',
            'status' => 'valid',
        ]);

        $revokeResponse = $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/sandbox-licenses/revoke', [
                'organization_id' => $entitlement->organization_id,
                'license' => $license,
                'reason' => 'control-center-test',
            ]);

        $revokeResponse->assertRedirect(route('sandbox-licenses.index'));
        $revokeResponse->assertSessionHas('sandbox_license_validation.valid', false);
        $revokeResponse->assertSessionHas('sandbox_license_validation.reason', 'revoked');
        $this->assertDatabaseCount('license_revocations', 1);
        $this->assertDatabaseHas('license_audit_events', [
            'actor_id' => $user->id,
            'organization_id' => $entitlement->organization_id,
            'action' => 'sandbox_license.revoked',
            'status' => 'revoked',
        ]);
        $this->assertDatabaseCount('license_audit_events', 3);
        self::assertSame(3, DomainOutboxMessage::query()->count());
    }

    public function test_license_audit_history_is_visible_only_for_managed_organizations(): void
    {
        $owner = User::factory()->create();
        $otherUser = User::factory()->create();

        $this->actingAs($owner)->post('/organizations', ['name' => 'Owner Organization']);
        $ownerEntitlement = DB::table('entitlements')->first();
        self::assertNotNull($ownerEntitlement);
        $this->actingAs($owner)->post('/sandbox-licenses', [
            'organization_id' => $ownerEntitlement->organization_id,
            'entitlement_id' => $ownerEntitlement->id,
        ]);

        $this->actingAs($otherUser)->post('/organizations', ['name' => 'Other Organization']);
        $otherEntitlement = DB::table('entitlements')
            ->where('organization_id', '!=', $ownerEntitlement->organization_id)
            ->first();
        self::assertNotNull($otherEntitlement);
        $this->actingAs($otherUser)->post('/sandbox-licenses', [
            'organization_id' => $otherEntitlement->organization_id,
            'entitlement_id' => $otherEntitlement->id,
        ]);

        $this->actingAs($owner)->get('/sandbox-licenses')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('sandbox-licenses')
                ->where('validationEngine', 'php')
                ->has('auditEvents', 1)
                ->where('auditEvents.0.organization_id', $ownerEntitlement->organization_id)
                ->where('auditEvents.0.action', 'sandbox_license.issued'));
    }

    public function test_admin_capability_can_manage_sandbox_license_without_owner_role(): void
    {
        $owner = User::factory()->create();
        $admin = User::factory()->create();

        $this->actingAs($owner)->post('/organizations', [
            'name' => 'Capability Organization',
        ]);

        $entitlement = DB::table('entitlements')->first();
        self::assertNotNull($entitlement);

        DB::table('organization_memberships')->insert([
            'id' => (string) Str::uuid(),
            'organization_id' => $entitlement->organization_id,
            'user_id' => $admin->id,
            'role' => 'admin',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $this->actingAs($admin)->post('/sandbox-licenses', [
            'organization_id' => $entitlement->organization_id,
            'entitlement_id' => $entitlement->id,
        ])->assertRedirect(route('sandbox-licenses.index'));

        $this->assertDatabaseHas('license_audit_events', [
            'actor_id' => $admin->id,
            'organization_id' => $entitlement->organization_id,
            'action' => 'sandbox_license.issued',
            'status' => 'success',
        ]);
    }

    public function test_user_cannot_issue_license_for_another_organization(): void
    {
        $owner = User::factory()->create();
        $otherUser = User::factory()->create();

        $this->actingAs($owner)->post('/organizations', [
            'name' => 'Owner Organization',
        ]);

        $entitlement = DB::table('entitlements')->first();
        self::assertNotNull($entitlement);

        $this->actingAs($otherUser)->post('/sandbox-licenses', [
            'organization_id' => $entitlement->organization_id,
            'entitlement_id' => $entitlement->id,
        ])->assertForbidden();

        $this->assertDatabaseCount('license_audit_events', 0);
    }

    public function test_revocation_requires_recent_step_up_confirmation(): void
    {
        $user = User::factory()->create();

        $this->actingAs($user)->post('/organizations', [
            'name' => 'Step Up Organization',
        ]);

        $entitlement = DB::table('entitlements')->first();
        self::assertNotNull($entitlement);

        $issueResponse = $this->actingAs($user)->post('/sandbox-licenses', [
            'organization_id' => $entitlement->organization_id,
            'entitlement_id' => $entitlement->id,
        ]);
        $license = session('sandbox_license.token');
        self::assertIsString($license);

        $this->actingAs($user)->post('/sandbox-licenses/revoke', [
            'license' => $license,
            'reason' => 'step-up-required',
        ])->assertRedirect(route('password.confirm'));

        $this->assertDatabaseCount('license_revocations', 0);
    }

    public function test_license_actions_fail_closed_when_selected_tenant_does_not_match_token(): void
    {
        $user = User::factory()->create();

        $this->actingAs($user)->post('/organizations', ['name' => 'Tenant One']);
        $firstEntitlement = DB::table('entitlements')->first();
        self::assertNotNull($firstEntitlement);

        $this->actingAs($user)->post('/organizations', ['name' => 'Tenant Two']);
        $secondEntitlement = DB::table('entitlements')
            ->where('organization_id', '!=', $firstEntitlement->organization_id)
            ->first();
        self::assertNotNull($secondEntitlement);

        $this->actingAs($user)->post('/sandbox-licenses', [
            'organization_id' => $firstEntitlement->organization_id,
            'entitlement_id' => $firstEntitlement->id,
        ]);
        $license = session('sandbox_license.token');
        self::assertIsString($license);

        $this->actingAs($user)->post('/sandbox-licenses/validate', [
            'organization_id' => $secondEntitlement->organization_id,
            'license' => $license,
        ])->assertUnprocessable();

        $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/sandbox-licenses/revoke', [
                'organization_id' => $secondEntitlement->organization_id,
                'license' => $license,
                'reason' => 'tenant-mismatch',
            ])->assertUnprocessable();

        $this->assertDatabaseCount('license_revocations', 0);
    }

    public function test_user_cannot_validate_or_revoke_another_organizations_license(): void
    {
        $owner = User::factory()->create();
        $otherUser = User::factory()->create();

        $this->actingAs($owner)->post('/organizations', [
            'name' => 'Owner Organization',
        ]);

        $entitlement = DB::table('entitlements')->first();
        self::assertNotNull($entitlement);

        $issueResponse = $this->actingAs($owner)->post('/sandbox-licenses', [
            'organization_id' => $entitlement->organization_id,
            'entitlement_id' => $entitlement->id,
        ]);
        $issueResponse->assertRedirect(route('sandbox-licenses.index'));

        $license = session('sandbox_license.token');
        self::assertIsString($license);

        $this->actingAs($otherUser)->post('/sandbox-licenses/validate', [
            'organization_id' => $entitlement->organization_id,
            'license' => $license,
        ])->assertForbidden();

        $this->actingAs($otherUser)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/sandbox-licenses/revoke', [
                'organization_id' => $entitlement->organization_id,
                'license' => $license,
                'reason' => 'unauthorized-attempt',
            ])->assertForbidden();

        $this->assertDatabaseCount('license_revocations', 0);
        $this->assertDatabaseCount('license_audit_events', 1);
    }
}
