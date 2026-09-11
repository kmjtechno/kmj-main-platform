<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class FirstVerticalSliceAcceptanceTest extends TestCase
{
    use RefreshDatabase;

    public function test_authenticated_owner_completes_first_vertical_slice_end_to_end(): void
    {
        $user = User::factory()->create();

        $this->actingAs($user)->post('/organizations', [
            'name' => 'KMJ Vertical Slice Lab',
        ])->assertRedirect(route('dashboard'));

        $organization = DB::table('organizations')->first();
        self::assertNotNull($organization);

        $product = DB::table('products')
            ->where('slug', 'kmj-main-platform-sandbox')
            ->first();
        self::assertNotNull($product);

        $entitlement = DB::table('entitlements')
            ->where('organization_id', $organization->id)
            ->where('product_id', $product->id)
            ->where('status', 'active')
            ->first();
        self::assertNotNull($entitlement);

        $this->assertDatabaseHas('entitlement_ledger', [
            'entitlement_id' => $entitlement->id,
            'organization_id' => $organization->id,
            'event_type' => 'entitlement.issued',
        ]);

        $issue = $this->actingAs($user)->post('/sandbox-licenses', [
            'organization_id' => $organization->id,
            'entitlement_id' => $entitlement->id,
        ]);
        $issue->assertRedirect(route('sandbox-licenses.index'));
        $issue->assertSessionHas('sandbox_license.validation.valid', true);

        $license = session('sandbox_license.token');
        self::assertIsString($license);
        self::assertNotSame('', $license);

        $validate = $this->actingAs($user)->post('/sandbox-licenses/validate', [
            'license' => $license,
        ]);
        $validate->assertSessionHas('sandbox_license_validation.valid', true);

        $revoke = $this->actingAs($user)->post('/sandbox-licenses/revoke', [
            'license' => $license,
            'reason' => 'vertical-slice-acceptance',
        ]);
        $revoke->assertSessionHas('sandbox_license_validation.valid', false);
        $revoke->assertSessionHas('sandbox_license_validation.reason', 'revoked');

        $this->assertDatabaseCount('license_revocations', 1);
        $this->assertDatabaseHas('license_audit_events', [
            'actor_id' => $user->id,
            'organization_id' => $organization->id,
            'action' => 'sandbox_license.issued',
            'status' => 'success',
        ]);
        $this->assertDatabaseHas('license_audit_events', [
            'actor_id' => $user->id,
            'organization_id' => $organization->id,
            'action' => 'sandbox_license.validated',
            'status' => 'valid',
        ]);
        $this->assertDatabaseHas('license_audit_events', [
            'actor_id' => $user->id,
            'organization_id' => $organization->id,
            'action' => 'sandbox_license.revoked',
            'status' => 'revoked',
        ]);
    }
}
