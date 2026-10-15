<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\Kslp\KslpDeveloperKeys;
use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class KslpDeveloperAppsTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        // Inertia response tests do not require compiled browser assets.
        // The standalone frontend release gate separately verifies Vite.
        $this->withoutVite();
        config()->set('services.kmj_developer_licensing.enabled', true);
    }

    /** @return array{User, string} */
    private function owner(string $name = 'Developer Company'): array
    {
        $owner = User::factory()->create();
        $this->actingAs($owner)->post('/organizations', ['name' => $name]);
        $orgId = (string) DB::table('organization_memberships')
            ->where('user_id', $owner->id)
            ->value('organization_id');

        return [$owner, $orgId];
    }

    private function enroll(string $organizationId): void
    {
        app(KslpIssuerSubscriptionAuthority::class)
            ->subscribe($organizationId, 'professional', 3, 50);
    }

    public function test_guest_cannot_open_developer_console(): void
    {
        $this->get('/developer/apps')->assertRedirect(route('login'));
    }

    public function test_owner_can_register_app_and_generate_one_time_random_key(): void
    {
        [$owner, $org] = $this->owner();
        $this->enroll($org);

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/apps', [
                'organization_id' => $org,
                'name' => 'Cinema Runtime',
                'product_code' => 'VENDOR.CINEMA',
            ])->assertRedirect(route('developer.apps.index'));

        $this->assertDatabaseHas('kslp_licensed_products', [
            'organization_id' => $org,
            'product_code' => 'VENDOR.CINEMA',
        ]);

        $issued = $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/keys', [
                'organization_id' => $org,
                'product_code' => 'VENDOR.CINEMA',
                'customer_id' => 'customer-123',
                'plan' => 'trial',
            ]);
        $issued->assertRedirect(route('developer.apps.index'));
        $issued->assertSessionHas('developer_license_key.key');
        $plain = session('developer_license_key.key');
        self::assertIsString($plain);
        self::assertMatchesRegularExpression('/^KMJ1-[A-Za-z0-9_-]{43}$/D', $plain);

        self::assertSame(
            hash('sha256', $plain),
            DB::table('kslp_license_keys')->value('key_digest'),
        );
        self::assertNotSame($plain, DB::table('kslp_license_keys')->value('display_prefix'));
        self::assertSame(
            'VENDOR.CINEMA',
            app(KslpDeveloperKeys::class)->resolve($plain)['product_code'],
        );

        $this->get('/developer/apps')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('developer-apps')
                ->has('applications', 1)
                ->has('keys', 1)
                ->where('canIssueKeys', true)
                ->where('newKey.key', $plain));

        $this->get('/developer/apps')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('developer-apps')
                ->where('newKey', null));
    }

    public function test_duplicate_application_code_returns_validation_error_without_duplicate_record(): void
    {
        [$owner, $org] = $this->owner('Developer Duplicate Code');
        $this->enroll($org);

        $request = [
            'organization_id' => $org,
            'name' => 'First App',
            'product_code' => 'VENDOR.DUPLICATE',
        ];

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/apps', $request)
            ->assertRedirect(route('developer.apps.index'));

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/apps', array_replace($request, ['name' => 'Second App']))
            ->assertSessionHasErrors('product_code');

        $this->assertDatabaseCount('kslp_licensed_products', 1);
    }

    public function test_app_registration_requires_active_issuer_subscription(): void
    {
        [$owner, $org] = $this->owner('Unsubscribed Developer');

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/apps', [
                'organization_id' => $org,
                'name' => 'Not Authorized',
                'product_code' => 'UNAPPROVED.APP',
            ])->assertSessionHasErrors('product_code');

        $this->assertDatabaseCount('kslp_licensed_products', 0);
    }

    public function test_other_organization_cannot_create_apps_or_keys(): void
    {
        [, $victimOrg] = $this->owner('Victim Developer');
        $attacker = User::factory()->create();

        $this->actingAs($attacker)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/apps', [
                'organization_id' => $victimOrg,
                'name' => 'Hijacked',
                'product_code' => 'ATTACKER.APP',
            ])->assertForbidden();

        $this->actingAs($attacker)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/keys', [
                'organization_id' => $victimOrg,
                'product_code' => 'VENDOR.CINEMA',
                'customer_id' => 'attacker',
                'plan' => 'trial',
            ])->assertForbidden();
    }

    public function test_default_off_flag_blocks_mutations_without_disabling_read_only_view(): void
    {
        [$owner, $org] = $this->owner();
        config()->set('services.kmj_developer_licensing.enabled', false);

        $this->actingAs($owner)->get('/developer/apps')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('developer-apps')
                ->where('canIssueKeys', false));

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/apps', [
                'organization_id' => $org,
                'name' => 'Blocked Application',
                'product_code' => 'BLOCKED.APP',
            ])->assertStatus(503);
    }

    public function test_self_service_paid_issuance_is_denied_without_verified_payment(): void
    {
        [$owner, $org] = $this->owner('Paid Entitlement Gate');
        $this->enroll($org);
        app(KslpIssuerSubscriptionAuthority::class)->registerProduct($org, 'VENDOR.PAID', 'Paid App');

        try {
            app(KslpDeveloperKeys::class)->issue(
                $org, 'VENDOR.PAID', 'unpaid-customer', 'enterprise', (string) $owner->id,
            );
            self::fail('Developer issuer subscription must not authorize an unpaid commercial plan.');
        } catch (DomainException $exception) {
            self::assertSame('KSLP_PAID_ENTITLEMENT_REQUIRED', $exception->getMessage());
        }

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/keys', [
                'organization_id' => $org,
                'product_code' => 'VENDOR.PAID',
                'customer_id' => 'unpaid-customer',
                'plan' => 'professional',
            ])->assertSessionHasErrors('plan');

        $this->assertDatabaseCount('kslp_license_keys', 0);
        $this->assertDatabaseCount('kslp_licenses', 0);
    }

    public function test_revoked_developer_key_cannot_be_resolved(): void
    {
        [$owner, $org] = $this->owner();
        $authority = app(KslpIssuerSubscriptionAuthority::class);
        $this->enroll($org);
        $authority->registerProduct($org, 'VENDOR.APP', 'Vendor App');

        $issued = app(KslpDeveloperKeys::class)->issue(
            $org, 'VENDOR.APP', 'customer-123', 'trial', (string) $owner->id,
        );
        DB::table('kslp_license_keys')->where('license_id', $issued['license_id'])
            ->update(['revoked_at' => now()]);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('KSLP_LICENSE_KEY_INVALID');
        app(KslpDeveloperKeys::class)->resolve($issued['key']);
    }

    public function test_license_key_cannot_activate_before_its_validity_start(): void
    {
        [$owner, $org] = $this->owner('Future License Guard');
        $this->enroll($org);
        app(KslpIssuerSubscriptionAuthority::class)->registerProduct($org, 'VENDOR.FUTURE', 'Future License');

        $issued = app(KslpDeveloperKeys::class)->issue(
            $org, 'VENDOR.FUTURE', 'customer-future', 'trial', (string) $owner->id,
        );
        DB::table('kslp_licenses')->where('id', $issued['license_id'])
            ->update(['starts_at' => now()->addDay()]);

        $this->expectExceptionMessage('KSLP_LICENSE_KEY_INVALID');
        app(KslpDeveloperKeys::class)->resolve($issued['key']);
    }

    public function test_unsigned_or_guessed_key_is_rejected(): void
    {
        $this->expectExceptionMessage('KSLP_LICENSE_KEY_INVALID');
        app(KslpDeveloperKeys::class)->resolve('KMJ1-'.str_repeat('A', 43));
    }

    public function test_authorized_developer_can_revoke_key_and_audit_license(): void
    {
        [$owner, $org] = $this->owner();
        $this->enroll($org);
        app(KslpIssuerSubscriptionAuthority::class)
            ->registerProduct($org, 'VENDOR.REVOKE', 'Revoke Test');
        $issued = app(KslpDeveloperKeys::class)->issue(
            $org, 'VENDOR.REVOKE', 'customer-revoke', 'trial', (string) $owner->id,
        );
        $keyId = DB::table('kslp_license_keys')->where('license_id', $issued['license_id'])->value('id');

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/keys/'.$keyId.'/revoke', [
                'reason' => 'Customer requested cancellation',
            ])->assertRedirect(route('developer.apps.index'));

        self::assertNotNull(DB::table('kslp_license_keys')->where('id', $keyId)->value('revoked_at'));
        $this->assertDatabaseHas('kslp_licenses', [
            'id' => $issued['license_id'],
            'status' => 'revoked',
        ]);
        $this->assertDatabaseHas('kslp_license_events', [
            'license_id' => $issued['license_id'],
            'action' => 'revoked',
        ]);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('KSLP_LICENSE_KEY_INVALID');
        app(KslpDeveloperKeys::class)->resolve($issued['key']);
    }

    public function test_unrelated_user_cannot_revoke_another_tenants_key(): void
    {
        [$owner, $org] = $this->owner();
        $this->enroll($org);
        app(KslpIssuerSubscriptionAuthority::class)
            ->registerProduct($org, 'VENDOR.SECURE', 'Secure App');
        $issued = app(KslpDeveloperKeys::class)->issue(
            $org, 'VENDOR.SECURE', 'customer-one', 'trial', (string) $owner->id,
        );
        $keyId = DB::table('kslp_license_keys')->where('license_id', $issued['license_id'])->value('id');
        $attacker = User::factory()->create();

        $this->actingAs($attacker)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/keys/'.$keyId.'/revoke', [
                'reason' => 'Unapproved deletion attempt',
            ])->assertForbidden();

        self::assertNull(DB::table('kslp_license_keys')->where('id', $keyId)->value('revoked_at'));
    }

    /** @return array{User, string, string, string, string} */
    private function issuedDeviceSeat(): array
    {
        [$owner, $org] = $this->owner('Device Seat Lab');
        $this->enroll($org);
        app(KslpIssuerSubscriptionAuthority::class)
            ->registerProduct($org, 'SEATS.APP', 'Seat Lab');
        $issued = app(KslpDeveloperKeys::class)->issue(
            $org, 'SEATS.APP', 'seat-customer', 'trial', (string) $owner->id,
        );
        $keyId = (string) DB::table('kslp_license_keys')
            ->where('license_id', $issued['license_id'])->value('id');
        $deviceId = (string) Str::uuid();
        $now = now();

        // Direct fixture for already-proven PoP activation. This test never
        // fabricates a client entitlement or skips proof in the HTTP API.
        DB::table('kslp_activations')->insert([
            'id' => $deviceId,
            'license_id' => $issued['license_id'],
            'server_identity' => 'ed25519:'.rtrim(strtr(base64_encode(random_bytes(32)), '+/', '-_'), '='),
            'machine_identity_hash' => hash('sha256', 'test-device-only'),
            'idempotency_key' => (string) Str::uuid(),
            'activated_at' => $now,
            'created_at' => $now,
            'updated_at' => $now,
        ]);

        return [$owner, $org, $keyId, $issued['license_id'], $deviceId];
    }

    public function test_developer_product_id_cannot_exceed_persisted_license_column(): void
    {
        [$owner, $org] = $this->owner('Schema Length Guard');
        $this->enroll($org);
        $overlong = str_repeat('A', 65);

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/apps', [
                'organization_id' => $org,
                'name' => 'Oversized product code',
                'product_code' => $overlong,
            ])->assertSessionHasErrors('product_code');
        $this->assertDatabaseCount('kslp_licensed_products', 0);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('KSLP_PRODUCT_CODE_TOO_LONG');
        app(KslpDeveloperKeys::class)->issue(
            $org, $overlong, 'customer', 'trial', (string) $owner->id,
        );
    }

    public function test_license_directory_only_exposes_masked_scoped_active_seats(): void
    {
        [$owner, , , , $device] = $this->issuedDeviceSeat();

        $this->actingAs($owner)->get('/developer/apps')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('developer-apps')
                ->has('activeDevices', 1)
                ->where('activeDevices.0.id', $device)
                ->has('activeSeatCounts')
                ->has('recentEvents')
                ->missing('activeDevices.0.server_identity')
                ->missing('activeDevices.0.machine_identity_hash')
                ->missing('activeDevices.0.idempotency_key'));

        $stranger = User::factory()->create();
        $this->actingAs($stranger)->get('/developer/apps')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('developer-apps')
                ->has('activeDevices', 0)
                ->has('activeSeatCounts', 0)
                ->has('recentEvents', 0)
                ->has('keys', 0));
    }

    public function test_authorized_developer_can_release_a_seat_with_reason_and_audit_exactly_once(): void
    {
        [$owner, , $key, $license, $device] = $this->issuedDeviceSeat();
        $before = (int) DB::table('kslp_licenses')->where('id', $license)->value('sequence');
        $uri = '/developer/keys/'.$key.'/devices/'.$device.'/release';

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post($uri, ['reason' => 'Customer replaced laptop'])
            ->assertRedirect(route('developer.apps.index'));

        self::assertNotNull(DB::table('kslp_activations')->where('id', $device)->value('deactivated_at'));
        self::assertSame($before + 1, (int) DB::table('kslp_licenses')->where('id', $license)->value('sequence'));
        $this->assertDatabaseHas('kslp_license_events', [
            'license_id' => $license,
            'action' => 'developer_device_released',
            'reason' => 'Customer replaced laptop',
        ]);

        // Idempotent retry: no sequence increment and no duplicate audit.
        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post($uri, ['reason' => 'Customer replaced laptop'])
            ->assertRedirect(route('developer.apps.index'));
        self::assertSame($before + 1, (int) DB::table('kslp_licenses')->where('id', $license)->value('sequence'));
        self::assertSame(1, DB::table('kslp_license_events')
            ->where('license_id', $license)
            ->where('action', 'developer_device_released')->count());
    }

    public function test_device_release_fails_closed_for_unrelated_user_and_unknown_activation(): void
    {
        [$owner, , $key, , $device] = $this->issuedDeviceSeat();
        $uri = '/developer/keys/'.$key.'/devices/'.$device.'/release';
        $stranger = User::factory()->create();

        $this->actingAs($stranger)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post($uri, ['reason' => 'Attempt unauthorized release'])
            ->assertForbidden();

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/keys/'.$key.'/devices/'.Str::uuid().'/release', [
                'reason' => 'Different customer device',
            ])->assertNotFound();

        self::assertNull(DB::table('kslp_activations')->where('id', $device)->value('deactivated_at'));
    }

    public function test_license_directory_uses_server_expiry_and_grace_not_browser_guess(): void
    {
        [$owner, , , $license] = $this->issuedDeviceSeat();
        DB::table('kslp_licenses')->where('id', $license)->update([
            'expires_at' => now()->subDay(),
            'grace_until' => now()->addDay(),
        ]);
        $this->actingAs($owner)->get('/developer/apps')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('developer-apps')
                ->where('keys.0.display_state', 'GRACE')
                ->missing('keys.0.license_revoked_at'));

        DB::table('kslp_licenses')->where('id', $license)
            ->update(['grace_until' => now()->subDay()]);
        $this->actingAs($owner)->get('/developer/apps')
            ->assertInertia(fn (Assert $page) => $page
                ->component('developer-apps')
                ->where('keys.0.display_state', 'RESTRICTED'));

        DB::table('kslp_licenses')->where('id', $license)
            ->update(['revoked_at' => now(), 'status' => 'revoked']);
        $this->actingAs($owner)->get('/developer/apps')
            ->assertInertia(fn (Assert $page) => $page
                ->component('developer-apps')
                ->where('keys.0.display_state', 'REVOKED_OR_SUSPENDED'));
    }

    public function test_seat_release_cannot_target_another_license_in_same_organization(): void
    {
        [$owner, $org, $key, $license, $device] = $this->issuedDeviceSeat();
        $another = app(KslpDeveloperKeys::class)->issue(
            $org, 'SEATS.APP', 'different-customer', 'trial', (string) $owner->id,
        );
        $otherDeviceId = (string) Str::uuid();
        $now = now();
        DB::table('kslp_activations')->insert([
            'id' => $otherDeviceId,
            'license_id' => $another['license_id'],
            'server_identity' => 'ed25519:'.rtrim(strtr(base64_encode(random_bytes(32)), '+/', '-_'), '='),
            'machine_identity_hash' => hash('sha256', 'unrelated-device'),
            'idempotency_key' => (string) Str::uuid(),
            'activated_at' => $now,
            'created_at' => $now,
            'updated_at' => $now,
        ]);

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/keys/'.$key.'/devices/'.$otherDeviceId.'/release', [
                'reason' => 'Wrong device should stay registered',
            ])->assertNotFound();

        self::assertNull(DB::table('kslp_activations')->where('id', $otherDeviceId)->value('deactivated_at'));
        self::assertNull(DB::table('kslp_activations')->where('id', $device)->value('deactivated_at'));
        self::assertSame(1, (int) DB::table('kslp_licenses')->where('id', $license)->value('sequence'));
    }

    public function test_invalid_device_release_route_ids_fail_before_postgresql_cast(): void
    {
        [$owner, , $key, , $device] = $this->issuedDeviceSeat();
        foreach ([
            '/developer/keys/not-a-uuid/devices/'.$device.'/release',
            '/developer/keys/'.$key.'/devices/not-a-uuid/release',
        ] as $uri) {
            $this->actingAs($owner)
                ->withSession(['auth.password_confirmed_at' => time()])
                ->post($uri, ['reason' => 'Invalid identity must fail closed'])
                ->assertNotFound();
        }
        self::assertNull(
            DB::table('kslp_activations')->where('id', $device)->value('deactivated_at'),
        );
    }

    public function test_device_release_requires_reason_and_enabled_flag(): void
    {
        [$owner, , $key, , $device] = $this->issuedDeviceSeat();
        $uri = '/developer/keys/'.$key.'/devices/'.$device.'/release';

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post($uri, ['reason' => ''])
            ->assertSessionHasErrors('reason');
        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post($uri, ['reason' => '   '])
            ->assertSessionHasErrors('reason');
        self::assertNull(DB::table('kslp_activations')->where('id', $device)->value('deactivated_at'));

        config()->set('services.kmj_developer_licensing.enabled', false);
        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post($uri, ['reason' => 'Device was replaced'])
            ->assertStatus(503);
        self::assertNull(DB::table('kslp_activations')->where('id', $device)->value('deactivated_at'));
    }
}
