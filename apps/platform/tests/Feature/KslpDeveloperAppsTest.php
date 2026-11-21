<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\Kslp\KslpDeveloperKeys;
use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
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

    public function test_developer_console_hides_owner_navigation_for_non_platform_owner(): void
    {
        [$developer] = $this->owner('Ordinary Developer');

        $this->actingAs($developer)->get('/developer/apps')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('developer-apps')
                ->where('canAccessOwnerHub', false));
    }

    public function test_passkey_verified_platform_owner_sees_owner_hub_navigation(): void
    {
        $platformOwner = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        DB::table('passkeys')->insert([
            'user_id' => $platformOwner->id,
            'name' => 'Owner developer navigation',
            'credential_id' => 'owner-dev-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $this->actingAs($platformOwner)->get('/developer/apps')
            ->assertRedirect('/operator/kslp#developer-workspace');
    }

    public function test_expired_issuer_does_not_appear_active_in_developer_workspace(): void
    {
        [$developer, $org] = $this->owner('Expired Developer');
        app(KslpIssuerSubscriptionAuthority::class)
            ->subscribe($org, 'business', 2, 8, now()->subDay());

        $this->actingAs($developer)->get('/developer/apps')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('developer-apps')
                ->where('organizations.0.issuer_status', 'expired')
                ->where('canAccessOwnerHub', false));

        $this->actingAs($developer)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/apps', [
                'organization_id' => $org,
                'product_code' => 'EXPIRED.APP',
                'name' => 'Expired App',
            ])->assertSessionHasErrors('product_code');
        $this->assertDatabaseCount('kslp_licensed_products', 0);
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

    public function test_application_rename_preserves_immutable_code_and_audits_once(): void
    {
        [$owner, $org] = $this->owner('Secure App Rename');
        $this->enroll($org);
        $product = app(KslpIssuerSubscriptionAuthority::class)
            ->registerProduct($org, 'VENDOR.RENAME', 'Old Application');
        $request = [
            'organization_id' => $org,
            'action' => 'rename',
            'name' => 'Updated Application',
            'reason' => 'Approved customer-facing display name correction',
        ];

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/apps/'.$product['id'].'/manage', $request)
            ->assertRedirect(route('developer.apps.index'));
        $this->assertDatabaseHas('kslp_licensed_products', [
            'id' => $product['id'],
            'organization_id' => $org,
            'product_code' => 'VENDOR.RENAME',
            'name' => 'Updated Application',
            'status' => 'active',
        ]);
        $this->assertDatabaseHas('license_audit_events', [
            'actor_id' => $owner->id,
            'organization_id' => $org,
            'action' => 'kslp_product_rename',
            'status' => 'success',
        ]);

        // Exactly the same request has no second ledger entry.
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/apps/'.$product['id'].'/manage', $request)
            ->assertRedirect(route('developer.apps.index'));
        self::assertSame(
            1,
            DB::table('license_audit_events')
                ->where('organization_id', $org)->where('action', 'kslp_product_rename')
                ->count(),
        );
    }

    public function test_application_pause_revokes_online_bootstrap_and_blocks_new_key(): void
    {
        [$owner, $org] = $this->owner('Secure App Pause');
        $this->enroll($org);
        $product = app(KslpIssuerSubscriptionAuthority::class)
            ->registerProduct($org, 'VENDOR.PAUSABLE', 'Pausable Application');
        $issued = app(KslpDeveloperKeys::class)->issue(
            $org, 'VENDOR.PAUSABLE', 'first-customer', 'trial', (string) $owner->id,
        );

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/apps/'.$product['id'].'/manage', [
                'organization_id' => $org,
                'action' => 'pause',
                'reason' => 'Suspected issuer application credential compromise',
            ])->assertRedirect(route('developer.apps.index'));
        $this->assertDatabaseHas('kslp_licensed_products', [
            'id' => $product['id'], 'status' => 'paused',
        ]);

        try {
            app(KslpDeveloperKeys::class)->resolve($issued['key']);
            self::fail('Suspended application must reject existing online bootstrap keys.');
        } catch (DomainException $exception) {
            self::assertSame('KSLP_LICENSE_KEY_INVALID', $exception->getMessage());
        }

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/keys', [
                'organization_id' => $org,
                'product_code' => 'VENDOR.PAUSABLE',
                'customer_id' => 'second-customer',
                'plan' => 'trial',
            ])->assertSessionHasErrors('customer_id');

        self::assertSame(1, DB::table('kslp_license_keys')->count());
        $this->assertDatabaseHas('license_audit_events', [
            'organization_id' => $org,
            'action' => 'kslp_product_pause',
        ]);
    }

    public function test_paused_app_cannot_be_directly_activated_by_known_license_id(): void
    {
        [$owner, $org] = $this->owner('Direct Activation Guard');
        $this->enroll($org);
        $authority = app(KslpIssuerSubscriptionAuthority::class);
        $product = $authority->registerProduct($org, 'VENDOR.DIRECT', 'Direct Activation Test');
        $issued = app(KslpDeveloperKeys::class)->issue(
            $org, 'VENDOR.DIRECT', 'direct-customer', 'trial', (string) $owner->id,
        );

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/apps/'.$product['id'].'/manage', [
                'organization_id' => $org,
                'action' => 'pause',
                'reason' => 'Block direct activation bypass during incident',
            ])->assertRedirect(route('developer.apps.index'));

        // Deliberately invalid proof: a suspended issuer must be rejected
        // before any challenge consumption or device activation side effect.
        try {
            app(KslpLicenseControlPlane::class)->activate(
                $issued['license_id'],
                'ed25519:bogus-device',
                'device-hash',
                (string) Str::uuid(),
                (string) $owner->id,
                (string) Str::uuid(),
                'bogus-nonce',
                'bogus-proof',
            );
            self::fail('Paused app must fail closed even with a known license ID.');
        } catch (DomainException $exception) {
            self::assertSame('KSLP_ISSUER_PRODUCT_NOT_AUTHORIZED', $exception->getMessage());
        }

        $this->assertDatabaseCount('kslp_activations', 0);
    }

    public function test_app_management_rejects_cross_tenant_and_unconfirmed_actions(): void
    {
        [$owner, $org] = $this->owner('Protected Owner');
        $this->enroll($org);
        $product = app(KslpIssuerSubscriptionAuthority::class)
            ->registerProduct($org, 'VENDOR.PROTECTED', 'Protected Application');
        $attacker = User::factory()->create();
        $request = [
            'organization_id' => $org,
            'action' => 'rename',
            'name' => 'Unauthorized Name',
            'reason' => 'Attempted unauthorized name change',
        ];

        $this->actingAs($attacker)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/apps/'.$product['id'].'/manage', $request)
            ->assertForbidden();

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => 0])
            ->post('/developer/apps/'.$product['id'].'/manage', $request)
            ->assertRedirect();

        $this->assertDatabaseHas('kslp_licensed_products', [
            'id' => $product['id'], 'name' => 'Protected Application',
        ]);
        self::assertSame(
            0,
            DB::table('license_audit_events')
                ->where('organization_id', $org)
                ->where('action', 'kslp_product_rename')->count(),
        );
    }

    public function test_emergency_pause_works_with_rollout_off_but_resume_fails_closed(): void
    {
        [$owner, $org] = $this->owner('Emergency Shutdown');
        $this->enroll($org);
        $product = app(KslpIssuerSubscriptionAuthority::class)
            ->registerProduct($org, 'VENDOR.EMERGENCY', 'Emergency Application');
        config()->set('services.kmj_developer_licensing.enabled', false);

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/apps/'.$product['id'].'/manage', [
                'organization_id' => $org,
                'action' => 'pause',
                'reason' => 'Urgent security lockdown required',
            ])->assertRedirect(route('developer.apps.index'));

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/apps/'.$product['id'].'/manage', [
                'organization_id' => $org,
                'action' => 'resume',
                'reason' => 'Security review has now been approved',
            ])->assertStatus(503);

        config()->set('services.kmj_developer_licensing.enabled', true);
        app(KslpIssuerSubscriptionAuthority::class)
            ->subscribe($org, 'professional', 3, 50, now()->subDay());
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/apps/'.$product['id'].'/manage', [
                'organization_id' => $org,
                'action' => 'resume',
                'reason' => 'Attempt before issuer renewal',
            ])->assertSessionHasErrors('action');

        $this->assertDatabaseHas('kslp_licensed_products', [
            'id' => $product['id'], 'status' => 'paused',
        ]);
        app(KslpIssuerSubscriptionAuthority::class)
            ->subscribe($org, 'professional', 3, 50);
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/developer/apps/'.$product['id'].'/manage', [
                'organization_id' => $org,
                'action' => 'resume',
                'reason' => 'Issuer renewed, owner reviewed reactivation',
            ])->assertRedirect(route('developer.apps.index'));
        $this->assertDatabaseHas('kslp_licensed_products', [
            'id' => $product['id'], 'status' => 'active',
        ]);
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
}
