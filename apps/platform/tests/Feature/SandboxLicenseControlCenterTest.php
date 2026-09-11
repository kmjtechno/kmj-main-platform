<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class SandboxLicenseControlCenterTest extends TestCase
{
    use RefreshDatabase;

    public function test_owner_can_issue_and_revoke_sandbox_license_from_control_surface(): void
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

        $license = session('sandbox_license.token');
        self::assertIsString($license);
        self::assertNotSame('', $license);

        $revokeResponse = $this->actingAs($user)->post('/sandbox-licenses/revoke', [
            'license' => $license,
            'reason' => 'control-center-test',
        ]);

        $revokeResponse->assertRedirect(route('sandbox-licenses.index'));
        $revokeResponse->assertSessionHas('sandbox_license_validation.valid', false);
        $revokeResponse->assertSessionHas('sandbox_license_validation.reason', 'revoked');
        $this->assertDatabaseCount('license_revocations', 1);
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
    }
}
