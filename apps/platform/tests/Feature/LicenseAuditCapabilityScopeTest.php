<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class LicenseAuditCapabilityScopeTest extends TestCase
{
    use RefreshDatabase;

    public function test_member_without_license_manage_cannot_read_license_audit_history(): void
    {
        $owner = User::factory()->create();
        $member = User::factory()->create();

        $this->actingAs($owner)->post('/organizations', [
            'name' => 'Scoped Audit Organization',
        ]);

        $entitlement = DB::table('entitlements')->first();
        self::assertNotNull($entitlement);

        $this->actingAs($owner)->post('/sandbox-licenses', [
            'organization_id' => $entitlement->organization_id,
            'entitlement_id' => $entitlement->id,
        ])->assertRedirect(route('sandbox-licenses.index'));

        $this->assertDatabaseCount('license_audit_events', 1);

        DB::table('organization_memberships')->insert([
            'id' => (string) Str::uuid(),
            'organization_id' => $entitlement->organization_id,
            'user_id' => $member->id,
            'role' => 'member',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $this->actingAs($member)->get('/sandbox-licenses')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('sandbox-licenses')
                ->has('organizations', 1)
                ->where('organizations.0.id', $entitlement->organization_id)
                ->has('auditEvents', 0));
    }
}
