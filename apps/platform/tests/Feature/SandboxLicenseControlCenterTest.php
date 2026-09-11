<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
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

        $revokeResponse = $this->actingAs($user)->post('/sandbox-licenses/revoke', [
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
            'license' => $license,
        ])->assertForbidden();

        $this->actingAs($otherUser)->post('/sandbox-licenses/revoke', [
            'license' => $license,
            'reason' => 'unauthorized-attempt',
        ])->assertForbidden();

        $this->assertDatabaseCount('license_revocations', 0);
        $this->assertDatabaseCount('license_audit_events', 1);
    }
}
