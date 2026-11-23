<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\Kslp\KslpCustomerWorkspaceQuery;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class KslpCustomerWorkspaceTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_guest_cannot_open_customer_licensing_hub(): void
    {
        $this->get('/licensing')->assertRedirect('/login');
    }

    public function test_unverified_customer_cannot_open_licensing_records(): void
    {
        $user = User::factory()->create(['email_verified_at' => null]);
        $this->actingAs($user)->get('/licensing')
            ->assertRedirect(route('verification.notice'));
    }

    public function test_customer_sees_only_exact_own_license_and_no_sensitive_device_data(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);
        $other = User::factory()->create(['email_verified_at' => now()]);
        $control = app(KslpLicenseControlPlane::class);
        $mine = $control->issue((string) $user->id, 'trial', 'test-owner', 'Customer trial');
        $notMine = $control->issue((string) $other->id, 'professional', 'test-owner', 'Other customer');

        $activationId = (string) Str::uuid();
        DB::table('kslp_activations')->insert([
            'id' => $activationId,
            'license_id' => $mine['id'],
            'server_identity' => 'do-not-leak-ed25519-device-public-key',
            'machine_identity_hash' => str_repeat('a', 64),
            'idempotency_key' => 'secret-idempotency-token',
            'activated_at' => now(),
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $response = $this->actingAs($user)->get('/licensing?customer_id='.$other->id);
        $response->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('licensing-hub')
                ->where('authorization_source', 'authenticated_verified_membership')
                ->where('license_count', 1)
                ->has('licenses', 1)
                ->where('licenses.0.id', $mine['id'])
                ->where('licenses.0.recorded_devices', 1)
                ->where('licenses.0.non_deactivated_devices', 1)
                ->where('licenses.0.online_status', 'not_verified')
                ->where('licenses.0.device_recovery_available', false)
                ->where('licenses.0.signed_download_verified', false)
                ->where('device_reset_enabled', false)
                ->where('paid_issuance_enabled', false));

        $cacheControl = strtolower((string) $response->headers->get('Cache-Control'));
        self::assertStringContainsString('private', $cacheControl);
        self::assertStringContainsString('no-store', $cacheControl);

        $json = $response->getContent();
        self::assertIsString($json);
        self::assertStringNotContainsString($notMine['id'], $json);
        self::assertStringNotContainsString('do-not-leak-ed25519-device-public-key', $json);
        self::assertStringNotContainsString('secret-idempotency-token', $json);
        self::assertStringNotContainsString(str_repeat('a', 64), $json);
    }

    public function test_verified_member_can_read_only_own_organization_license(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);
        $other = User::factory()->create(['email_verified_at' => now()]);

        $this->actingAs($user)->post('/organizations', ['name' => 'Licensed Member Organization']);
        $memberOrg = (string) DB::table('organization_memberships')
            ->where('user_id', $user->id)->value('organization_id');

        $this->actingAs($other)->post('/organizations', ['name' => 'Unrelated Organization']);
        $otherOrg = (string) DB::table('organization_memberships')
            ->where('user_id', $other->id)->value('organization_id');

        $control = app(KslpLicenseControlPlane::class);
        $mine = $control->issue($memberOrg, 'trial', 'test-owner', 'Org trial');
        $notMine = $control->issue($otherOrg, 'professional', 'test-owner', 'Other org');

        $this->actingAs($user)->get('/licensing')->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('licensing-hub')
                ->where('license_count', 1)
                ->has('licenses', 1)
                ->where('licenses.0.id', $mine['id'])
                ->where('licenses.0.subject_label', 'Licensed Member Organization')
                ->has('organizations', 1));

        $response = $this->actingAs($user)->get('/licensing');
        self::assertStringNotContainsString($notMine['id'], (string) $response->getContent());
        self::assertStringNotContainsString($otherOrg, (string) $response->getContent());
    }

    public function test_owner_level_mutations_are_not_exposed_on_customer_hub(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);
        $response = $this->actingAs($user)->get('/licensing');
        $response->assertInertia(fn (Assert $page) => $page
            ->where('device_reset_enabled', false)
            ->where('paid_issuance_enabled', false)
            ->where('trusted_download_source', '/dashboard'));

        $this->actingAs($user)->post('/licensing/device/transfer', [
            'license_id' => (string) Str::uuid(),
            'confirm' => 'FORCE_RELEASE',
        ])->assertNotFound();
    }

    public function test_license_state_changes_are_read_only_and_not_fabricated(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);
        $control = app(KslpLicenseControlPlane::class);
        $mine = $control->issue((string) $user->id, 'trial', 'test-owner', 'Trial');
        $control->revoke($mine['id'], 'test-owner', 'Explicit owner revocation');

        $this->actingAs($user)->get('/licensing')
            ->assertInertia(fn (Assert $page) => $page
                ->where('license_count', 1)
                ->where('licenses.0.state', 'REVOKED')
                ->where('licenses.0.non_deactivated_devices', 0));

        $this->assertDatabaseHas('kslp_licenses', [
            'id' => $mine['id'],
            'status' => 'revoked',
        ]);
    }

    public function test_customer_renewal_states_are_derived_only_from_verified_kslp_dates(): void
    {
        $now = Carbon::parse('2026-11-23 12:00:00', 'UTC');
        $license = [
            'status' => 'active',
            'starts_at' => '2026-11-01 00:00:00',
            'expires_at' => '2026-12-10 00:00:00',
            'grace_until' => '2026-12-20 00:00:00',
            'revoked_at' => null,
        ];

        self::assertSame('ACTIVE', KslpCustomerWorkspaceQuery::state($license, $now));
        self::assertSame('RENEWAL_DUE', KslpCustomerWorkspaceQuery::state([
            ...$license,
            'expires_at' => '2026-11-27 12:00:00',
        ], $now));
        self::assertSame('GRACE', KslpCustomerWorkspaceQuery::state([
            ...$license,
            'expires_at' => '2026-11-22 12:00:00',
            'grace_until' => '2026-11-30 00:00:00',
        ], $now));
        self::assertSame('RESTRICTED', KslpCustomerWorkspaceQuery::state([
            ...$license,
            'expires_at' => '2026-11-22 12:00:00',
            'grace_until' => '2026-11-22 20:00:00',
        ], $now));
        self::assertSame('NOT_STARTED', KslpCustomerWorkspaceQuery::state([
            ...$license,
            'starts_at' => '2026-11-24 00:00:00',
        ], $now));
        self::assertSame('REVOKED', KslpCustomerWorkspaceQuery::state([
            ...$license,
            'revoked_at' => '2026-11-20 00:00:00',
        ], $now));
        self::assertSame('RESTRICTED', KslpCustomerWorkspaceQuery::state([
            ...$license,
            'status' => 'suspended',
        ], $now));
        self::assertSame('RESTRICTED', KslpCustomerWorkspaceQuery::state([
            ...$license,
            'expires_at' => '',
        ], $now));
    }
}
