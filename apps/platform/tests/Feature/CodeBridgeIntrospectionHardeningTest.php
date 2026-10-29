<?php

declare(strict_types=1);

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

/**
 * Positive/negative matrix for the gateway-facing device credential
 * introspection route. Introspection is the authority the gateway consults on
 * every reconnect, so every revoked/expired/foreign state must fail closed.
 */
final class CodeBridgeIntrospectionHardeningTest extends TestCase
{
    use RefreshDatabase;

    private const URL = '/api/codebridge/v1/device-credentials/introspect';

    protected function setUp(): void
    {
        parent::setUp();
        config()->set('codebridge.enabled', true);
    }

    public function test_active_credential_reports_only_its_own_tenant_device_and_project(): void
    {
        $a = $this->fixture('tenant-device-a', 'project-a', ['read', 'write']);
        $b = $this->fixture('tenant-device-b', 'project-b', ['read']);

        $response = $this->withToken($a['token'])->postJson(self::URL)->assertOk()
            ->assertHeader('Cache-Control')
            ->assertJson([
                'active' => true,
                'device_id' => 'tenant-device-a',
                'tenant_id' => $a['tenant'],
                'projects' => ['project-a'],
                'permissions' => ['read', 'write'],
            ]);
        self::assertStringContainsString('no-store', (string) $response->headers->get('Cache-Control'));
        self::assertStringNotContainsString($b['tenant'], $response->getContent());
        self::assertStringNotContainsString('project-b', $response->getContent());

        $this->withToken($b['token'])->postJson(self::URL)->assertOk()
            ->assertJson(['tenant_id' => $b['tenant'], 'projects' => ['project-b'], 'permissions' => ['read']]);
    }

    public function test_missing_malformed_and_unknown_tokens_are_rejected(): void
    {
        $this->fixture('tenant-device-a', 'project-a', ['read']);

        $this->postJson(self::URL)->assertUnauthorized();
        $this->withToken('short')->postJson(self::URL)->assertUnauthorized();
        $this->withToken(str_repeat('z', 4097))->postJson(self::URL)->assertUnauthorized();
        $this->withToken(str_repeat('z', 48))->postJson(self::URL)->assertUnauthorized()->assertJson(['active' => false]);
    }

    public function test_revoked_and_expired_credentials_are_denied_immediately(): void
    {
        $a = $this->fixture('tenant-device-a', 'project-a', ['read']);
        $this->withToken($a['token'])->postJson(self::URL)->assertOk();

        DB::table('codebridge_device_credentials')->where('device_id', 'tenant-device-a')->update(['expires_at_epoch' => time() - 1]);
        $this->withToken($a['token'])->postJson(self::URL)->assertUnauthorized()->assertJson(['active' => false]);

        DB::table('codebridge_device_credentials')->where('device_id', 'tenant-device-a')->update(['expires_at_epoch' => time() + 3600]);
        $this->withToken($a['token'])->postJson(self::URL)->assertOk();

        DB::table('codebridge_device_credentials')->where('device_id', 'tenant-device-a')->update(['revoked_at' => now()]);
        $this->withToken($a['token'])->postJson(self::URL)->assertUnauthorized()->assertJson(['active' => false]);
    }

    public function test_inactive_expired_or_revoked_license_denies_even_a_valid_credential(): void
    {
        $a = $this->fixture('tenant-device-a', 'project-a', ['read']);
        $license = DB::table('kslp_licenses')->where('id', $a['license']);

        foreach ([
            ['status' => 'suspended'],
            ['status' => 'active', 'revoked_at' => now()],
            ['status' => 'active', 'revoked_at' => null, 'expires_at' => now()->subSecond()],
            ['status' => 'active', 'expires_at' => now()->addYear(), 'starts_at' => now()->addDay()],
        ] as $bad) {
            $license->update($bad);
            $this->withToken($a['token'])->postJson(self::URL)->assertUnauthorized()->assertJson(['active' => false]);
        }

        $license->update(['status' => 'active', 'revoked_at' => null, 'starts_at' => now()->subDay(), 'expires_at' => now()->addYear()]);
        $this->withToken($a['token'])->postJson(self::URL)->assertOk();
    }

    public function test_credential_without_valid_pairing_permissions_never_activates(): void
    {
        $a = $this->fixture('tenant-device-a', 'project-a', ['read']);

        foreach ([[], ['admin'], ['root', 'sudo'], [1, 2]] as $invalid) {
            DB::table('codebridge_device_pairings')->where('device_id', 'tenant-device-a')
                ->update(['requested_permissions' => json_encode($invalid)]);
            $this->withToken($a['token'])->postJson(self::URL)->assertUnauthorized()->assertJson(['active' => false]);
        }

        DB::table('codebridge_device_pairings')->where('device_id', 'tenant-device-a')->delete();
        $this->withToken($a['token'])->postJson(self::URL)->assertUnauthorized()->assertJson(['active' => false]);
    }

    public function test_permissions_are_whitelisted_deduplicated_and_ordered(): void
    {
        $a = $this->fixture('tenant-device-a', 'project-a', ['execute', 'admin', 'read', 'read']);

        $this->withToken($a['token'])->postJson(self::URL)->assertOk()
            ->assertJson(['permissions' => ['read', 'execute']]);
    }

    public function test_revoking_one_device_does_not_affect_another_tenants_device(): void
    {
        $a = $this->fixture('tenant-device-a', 'project-a', ['read']);
        $b = $this->fixture('tenant-device-b', 'project-b', ['read']);

        DB::table('codebridge_device_credentials')->where('tenant_id', $a['tenant'])->update(['revoked_at' => now()]);

        $this->withToken($a['token'])->postJson(self::URL)->assertUnauthorized();
        $this->withToken($b['token'])->postJson(self::URL)->assertOk();
    }

    public function test_api_disabled_fails_closed_before_any_lookup(): void
    {
        $a = $this->fixture('tenant-device-a', 'project-a', ['read']);
        config()->set('codebridge.enabled', false);

        $this->withToken($a['token'])->postJson(self::URL)->assertStatus(503);
    }

    /**
     * @param  list<mixed>  $permissions
     * @return array{tenant:string,license:string,token:string}
     */
    private function fixture(string $device, string $project, array $permissions): array
    {
        $tenant = (string) Str::uuid();
        $license = (string) Str::uuid();
        $activation = (string) Str::uuid();
        $token = hash('sha256', 'introspection-hardening:'.$device).'x';
        $now = now();

        DB::table('kslp_licenses')->insert([
            'id' => $license, 'customer_id' => $tenant, 'product' => 'KMJ_CODEBRIDGE',
            'plan' => 'professional', 'status' => 'active', 'sequence' => 1,
            'starts_at' => $now->copy()->subDay(), 'expires_at' => $now->copy()->addYear(),
            'grace_until' => $now->copy()->addYear()->addDays(2),
            'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('kslp_activations')->insert([
            'id' => $activation, 'license_id' => $license,
            'server_identity' => 'codebridge-device:'.$device,
            'machine_identity_hash' => hash('sha256', $device),
            'idempotency_key' => 'introspection-hardening:'.$device,
            'activated_at' => $now, 'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('codebridge_device_credentials')->insert([
            'id' => (string) Str::uuid(), 'license_id' => $license,
            'activation_id' => $activation, 'tenant_id' => $tenant,
            'device_id' => $device,
            'server_identity' => 'codebridge-device:'.$device,
            'token_hash' => hash('sha256', $token),
            'lease_sequence' => 0, 'expires_at_epoch' => time() + 3600,
        ]);
        DB::table('codebridge_device_pairings')->insert([
            'id' => (string) Str::uuid(),
            'device_code_hash' => hash('sha256', 'device-code:'.$device),
            'user_code_hash' => hash('sha256', 'user-code:'.$device),
            'device_id' => $device, 'device_name' => $device,
            'platform' => 'win32', 'arch' => 'x64',
            'project_id' => $project, 'project_name' => $project,
            'requested_permissions' => json_encode($permissions),
            'code_challenge' => str_repeat('x', 43),
            'status' => 'consumed', 'tenant_id' => $tenant,
            'license_id' => $license, 'activation_id' => $activation,
            'expires_at' => $now->copy()->addMinutes(5),
            'consumed_at' => $now,
            'created_at' => $now, 'updated_at' => $now,
        ]);

        return ['tenant' => $tenant, 'license' => $license, 'token' => $token];
    }
}
