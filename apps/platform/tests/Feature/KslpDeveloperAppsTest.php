<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\Kslp\KslpDeveloperKeys;
use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class KslpDeveloperAppsTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
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
                'plan' => 'professional',
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
                'plan' => 'professional',
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

    public function test_revoked_developer_key_cannot_be_resolved(): void
    {
        [$owner, $org] = $this->owner();
        $authority = app(KslpIssuerSubscriptionAuthority::class);
        $this->enroll($org);
        $authority->registerProduct($org, 'VENDOR.APP', 'Vendor App');

        $issued = app(KslpDeveloperKeys::class)->issue(
            $org, 'VENDOR.APP', 'customer-123', 'professional', (string) $owner->id,
        );
        DB::table('kslp_license_keys')->where('license_id', $issued['license_id'])
            ->update(['revoked_at' => now()]);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('KSLP_LICENSE_KEY_INVALID');
        app(KslpDeveloperKeys::class)->resolve($issued['key']);
    }

    public function test_unsigned_or_guessed_key_is_rejected(): void
    {
        $this->expectExceptionMessage('KSLP_LICENSE_KEY_INVALID');
        app(KslpDeveloperKeys::class)->resolve('KMJ1-' . str_repeat('A', 43));
    }
}
