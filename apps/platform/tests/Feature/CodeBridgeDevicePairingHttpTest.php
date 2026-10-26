<?php

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\CodeBridge\CodeBridgeCustomerDeviceDirectory;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

final class CodeBridgeDevicePairingHttpTest extends TestCase
{
    use RefreshDatabase;

    public function test_empty_enrollment_probe_reports_validation_only_when_api_enabled_without_creating_pairing(): void
    {
        config()->set('codebridge.enabled', false);
        $this->postJson('/api/codebridge/v1/device-enrollments', [])->assertStatus(503);
        self::assertDatabaseCount('codebridge_device_pairings', 0);

        config()->set('codebridge.enabled', true);
        $this->postJson('/api/codebridge/v1/device-enrollments', [])->assertStatus(422);
        self::assertDatabaseCount('codebridge_device_pairings', 0);
        self::assertDatabaseCount('codebridge_device_credentials', 0);
    }

    public function test_fresh_device_can_create_approve_redeem_once_without_manual_agent_token(): void
    {
        config()->set('codebridge.enabled', true);
        config()->set('services.codebridge_gateway.url', 'http://127.0.0.1:18787');
        config()->set('services.codebridge_gateway.agent_public_url', 'https://gateway.example');
        $user = User::factory()->create();
        [$tenant] = $this->fixture($user);

        $verifier = rtrim(strtr(base64_encode(random_bytes(32)), '+/', '-_'), '=');
        $challenge = rtrim(strtr(base64_encode(hash('sha256', $verifier, true)), '+/', '-_'), '=');

        $created = $this->postJson('/api/codebridge/v1/device-enrollments', [
            'product' => 'KMJ_CODEBRIDGE',
            'device' => ['id' => 'vps1', 'name' => 'VPS 1', 'platform' => 'linux', 'arch' => 'x64'],
            'project' => ['id' => 'project1', 'name' => 'App'],
            'requested_permissions' => ['read', 'write', 'execute'],
            'code_challenge' => $challenge,
            'code_challenge_method' => 'S256',
        ])->assertCreated()->json();

        self::assertArrayHasKey('device_code', $created);
        self::assertArrayHasKey('user_code', $created);
        self::assertStringNotContainsString($created['device_code'], json_encode(DB::table('codebridge_device_pairings')->first()));

        $this->postJson('/api/codebridge/v1/device-enrollments/token', [
            'product' => 'KMJ_CODEBRIDGE',
            'device_code' => $created['device_code'],
            'code_verifier' => $verifier,
            'device_id' => 'vps1',
        ])->assertStatus(428);

        $this->actingAs($user)
            ->get('/codebridge/pair?code='.urlencode($created['user_code']))
            ->assertOk()
            ->assertSee('VPS 1')
            ->assertSee('project1');

        $this->actingAs($user)
            ->post('/codebridge/pair', ['code' => $created['user_code'], 'tenant_id' => $tenant])
            ->assertRedirect();

        // An issued but not yet redeemed approval is not a connected device.
        $approvedDirectory = app(CodeBridgeCustomerDeviceDirectory::class)->forTenant($tenant, time());
        self::assertCount(1, $approvedDirectory);
        self::assertSame('approved_unredeemed', $approvedDirectory[0]['pairing_state']);
        self::assertNull($approvedDirectory[0]['registered_at']);
        self::assertSame('not_verified', $approvedDirectory[0]['connection_status']);

        $redeemed = $this->postJson('/api/codebridge/v1/device-enrollments/token', [
            'product' => 'KMJ_CODEBRIDGE',
            'device_code' => $created['device_code'],
            'code_verifier' => $verifier,
            'device_id' => 'vps1',
        ])->assertOk()->json();

        self::assertSame('https://gateway.example', $redeemed['gateway']);
        self::assertSame('vps1', $redeemed['agent']['id']);
        self::assertSame($tenant, $redeemed['agent']['tenant']);
        self::assertGreaterThanOrEqual(32, strlen($redeemed['agent']['token']));
        self::assertSame([['id' => 'project1']], $redeemed['projects']);
        self::assertNull(DB::table('codebridge_device_pairings')->value('credential_ciphertext'));
        self::assertDatabaseHas('codebridge_device_pairings', ['status' => 'consumed']);
        self::assertDatabaseHas('codebridge_device_credentials', ['tenant_id' => $tenant, 'device_id' => 'vps1']);

        // The customer dashboard may show only this tenant's registered
        // devices, and must never imply a live heartbeat from enrollment.
        $directory = app(CodeBridgeCustomerDeviceDirectory::class);
        $devices = $directory->forTenant($tenant, time());
        self::assertCount(1, $devices);
        self::assertSame('vps1', $devices[0]['id']);
        self::assertSame('VPS 1', $devices[0]['name']);
        self::assertSame([['id' => 'project1', 'name' => 'App']], $devices[0]['projects']);
        self::assertSame('registered', $devices[0]['registration']);
        self::assertSame('redeemed', $devices[0]['pairing_state']);
        self::assertSame('not_verified', $devices[0]['connection_status']);
        self::assertArrayNotHasKey('token', $devices[0]);
        self::assertArrayNotHasKey('token_hash', $devices[0]);
        self::assertSame([], $directory->forTenant((string) Str::uuid(), time()));

        $this->withToken($redeemed['agent']['token'])
            ->postJson('/api/codebridge/v1/device-credentials/introspect')
            ->assertOk()
            ->assertJson([
                'active' => true,
                'device_id' => 'vps1',
                'tenant_id' => $tenant,
                'projects' => ['project1'],
            ]);

        $this->postJson('/api/codebridge/v1/device-enrollments/token', [
            'product' => 'KMJ_CODEBRIDGE',
            'device_code' => $created['device_code'],
            'code_verifier' => $verifier,
            'device_id' => 'vps1',
        ])->assertStatus(410);
    }

    public function test_gateway_origin_missing_fails_before_device_registration(): void
    {
        config()->set('codebridge.enabled', true);
        config()->set('services.codebridge_gateway.agent_public_url', '');
        $user = User::factory()->create();
        [$tenant] = $this->fixture($user);
        $verifier = rtrim(strtr(base64_encode(random_bytes(32)), '+/', '-_'), '=');
        $challenge = rtrim(strtr(base64_encode(hash('sha256', $verifier, true)), '+/', '-_'), '=');
        $created = $this->postJson('/api/codebridge/v1/device-enrollments', [
            'product' => 'KMJ_CODEBRIDGE',
            'device' => ['id' => 'home-office', 'name' => 'Home Office', 'platform' => 'win32', 'arch' => 'x64'],
            'project' => ['id' => 'calibration', 'name' => 'Calibration Pro'],
            'requested_permissions' => ['read', 'write', 'execute'],
            'code_challenge' => $challenge,
            'code_challenge_method' => 'S256',
        ])->assertCreated()->json();

        $this->actingAs($user)
            ->post('/codebridge/pair', ['code' => $created['user_code'], 'tenant_id' => $tenant])
            ->assertRedirect()
            ->assertSessionHasErrors(['code' => 'CODEBRIDGE_GATEWAY_UNAVAILABLE']);

        self::assertSame(0, DB::table('codebridge_device_credentials')->count());
        self::assertSame(0, DB::table('kslp_activations')->count());
        self::assertSame('pending', DB::table('codebridge_device_pairings')->value('status'));
        self::assertNull(DB::table('codebridge_device_pairings')->value('credential_ciphertext'));
    }

    public function test_existing_device_error_shows_recovery_without_repeat_approval(): void
    {
        config()->set('codebridge.enabled', true);
        config()->set('services.codebridge_gateway.agent_public_url', 'https://gateway.example');
        $user = User::factory()->create();
        [$tenant] = $this->fixture($user);

        $newPairing = function (): array {
            $verifier = rtrim(strtr(base64_encode(random_bytes(32)), '+/', '-_'), '=');
            $challenge = rtrim(strtr(base64_encode(hash('sha256', $verifier, true)), '+/', '-_'), '=');

            return $this->postJson('/api/codebridge/v1/device-enrollments', [
                'product' => 'KMJ_CODEBRIDGE',
                'device' => ['id' => 'vps1', 'name' => 'Existing VPS', 'platform' => 'win32', 'arch' => 'x64'],
                'project' => ['id' => 'project1', 'name' => 'App'],
                'requested_permissions' => ['read', 'write', 'execute'],
                'code_challenge' => $challenge,
                'code_challenge_method' => 'S256',
            ])->assertCreated()->json();
        };

        $first = $newPairing();
        $this->actingAs($user)->post('/codebridge/pair', [
            'code' => $first['user_code'],
            'tenant_id' => $tenant,
        ])->assertRedirect();
        self::assertSame(1, DB::table('codebridge_device_credentials')->count());

        $second = $newPairing();
        $uri = '/codebridge/pair?code='.urlencode($second['user_code']);
        $this->actingAs($user)
            ->from($uri)
            ->post('/codebridge/pair', ['code' => $second['user_code'], 'tenant_id' => $tenant])
            ->assertRedirect($uri)
            ->assertSessionHasErrors('code');

        $this->actingAs($user)
            ->get($uri)
            ->assertOk()
            ->assertSee('Existing VPS')
            ->assertSee('This device is already registered.')
            ->assertSee('CONNECT-ANY-DEVICE.cmd')
            ->assertSee('/services/kmj-codebridge#codebridge-device-control', false)
            ->assertDontSee('Approve CodeBridge device</button>', false);

        // Repeated approval must never revoke, overwrite or replace the token hash.
        self::assertSame(1, DB::table('codebridge_device_credentials')->whereNull('revoked_at')->count());
    }

    public function test_pairing_rejects_wrong_verifier_and_expired_code(): void
    {
        config()->set('codebridge.enabled', true);
        config()->set('services.codebridge_gateway.agent_public_url', 'https://gateway.example');
        $user = User::factory()->create();
        [$tenant] = $this->fixture($user);
        $verifier = rtrim(strtr(base64_encode(random_bytes(32)), '+/', '-_'), '=');
        $challenge = rtrim(strtr(base64_encode(hash('sha256', $verifier, true)), '+/', '-_'), '=');
        $created = $this->postJson('/api/codebridge/v1/device-enrollments', [
            'product' => 'KMJ_CODEBRIDGE',
            'device' => ['id' => 'vps2', 'name' => 'VPS 2', 'platform' => 'linux', 'arch' => 'arm64'],
            'project' => ['id' => 'project1', 'name' => 'App'],
            'requested_permissions' => ['read'],
            'code_challenge' => $challenge,
            'code_challenge_method' => 'S256',
        ])->assertCreated()->json();

        $this->actingAs($user)->post('/codebridge/pair', [
            'code' => $created['user_code'],
            'tenant_id' => $tenant,
        ])->assertRedirect();

        $this->postJson('/api/codebridge/v1/device-enrollments/token', [
            'product' => 'KMJ_CODEBRIDGE',
            'device_code' => $created['device_code'],
            'code_verifier' => str_repeat('x', 43),
            'device_id' => 'vps2',
        ])->assertStatus(400);

        DB::table('codebridge_device_pairings')->update(['expires_at' => now()->subSecond()]);
        $this->postJson('/api/codebridge/v1/device-enrollments/token', [
            'product' => 'KMJ_CODEBRIDGE',
            'device_code' => $created['device_code'],
            'code_verifier' => $verifier,
            'device_id' => 'vps2',
        ])->assertStatus(410);
    }

    /** @return array{string,string} */
    private function fixture(User $user): array
    {
        $tenant = (string) Str::uuid();
        $license = (string) Str::uuid();
        $now = now();
        DB::table('organizations')->insert(['id' => $tenant, 'name' => 'KMJ Test Org', 'created_at' => $now, 'updated_at' => $now]);
        DB::table('organization_memberships')->insert([
            'id' => (string) Str::uuid(), 'organization_id' => $tenant, 'user_id' => $user->id,
            'role' => 'owner', 'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('kslp_licenses')->insert([
            'id' => $license, 'customer_id' => $tenant, 'product' => 'KMJ_CODEBRIDGE', 'plan' => 'professional',
            'status' => 'active', 'sequence' => 1, 'starts_at' => $now->copy()->subMinute(), 'expires_at' => $now->copy()->addYear(),
            'grace_until' => $now->copy()->addYear()->addDays(2), 'created_at' => $now, 'updated_at' => $now,
        ]);
        $product = (string) Str::uuid();
        DB::table('products')->insert([
            'id' => $product, 'slug' => 'codebridge', 'name' => 'CodeBridge', 'status' => 'active',
            'lifecycle' => 'available', 'is_public' => false, 'sort_order' => 100,
            'purchase_enabled' => false, 'licensing_enabled' => true, 'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('plans')->insert([
            'id' => (string) Str::uuid(), 'product_id' => $product, 'code' => 'codebridge.professional',
            'name' => 'CodeBridge Professional', 'pricing_model' => 'license', 'status' => 'active', 'trial_days' => 0,
            'features' => json_encode(['read' => true, 'write' => true, 'execute' => true]),
            'limits' => json_encode(['devices' => 5]), 'created_at' => $now, 'updated_at' => $now,
        ]);

        return [$tenant, $license];
    }
}
