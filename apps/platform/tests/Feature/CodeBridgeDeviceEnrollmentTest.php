<?php

namespace Tests\Feature;

use App\Services\Licensing\CodeBridge\CodeBridgeDeviceCredentialService;
use App\Services\Licensing\CodeBridge\CodeBridgeDeviceEnrollmentService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

final class CodeBridgeDeviceEnrollmentTest extends TestCase
{
    use RefreshDatabase;

    public function test_enrollment_returns_raw_credential_once_and_stores_only_hash(): void
    {
        [$license, $activation] = $this->fixture(2);
        $result = app(CodeBridgeDeviceEnrollmentService::class)->enroll($license, $activation, 'tenant-a', 'device-a', time());

        self::assertGreaterThanOrEqual(64, strlen($result['credential']));
        $row = DB::table('codebridge_device_credentials')->where('activation_id', $activation)->first();
        self::assertNotNull($row);
        self::assertSame(hash('sha256', $result['credential']), $row->token_hash);
        self::assertSame('ed25519:test-server', $row->server_identity);
        self::assertDatabaseHas('kslp_license_events', ['license_id' => $license, 'action' => 'codebridge_device_enrolled']);

        $this->expectExceptionMessage('CODEBRIDGE_DEVICE_ALREADY_ENROLLED');
        app(CodeBridgeDeviceEnrollmentService::class)->enroll($license, $activation, 'tenant-a', 'device-a', time());
    }

    public function test_revoked_device_reconnects_only_with_fresh_activation_and_new_token(): void
    {
        [$license, $activation] = $this->fixture(1);
        $enroll = app(CodeBridgeDeviceEnrollmentService::class);
        $old = $enroll->enroll($license, $activation, 'tenant-a', 'device-a', time());
        $oldRow = DB::table('codebridge_device_credentials')->where('device_id', 'device-a')->first();
        self::assertNotNull($oldRow);

        app(CodeBridgeDeviceCredentialService::class)
            ->revoke($license, 'tenant-a', 'device-a', time());

        $freshActivation = (string) Str::uuid();
        DB::table('kslp_activations')->insert([
            'id' => $freshActivation, 'license_id' => $license,
            'server_identity' => 'ed25519:repaired-agent',
            'machine_identity_hash' => str_repeat('c', 64),
            'idempotency_key' => 'repaired-'.Str::uuid(),
            'activated_at' => now(), 'created_at' => now(), 'updated_at' => now(),
        ]);
        $new = $enroll->enroll($license, $freshActivation, 'tenant-a', 'device-a', time());
        self::assertNotSame($old['credential'], $new['credential']);
        self::assertSame(1, DB::table('codebridge_device_credentials')->count());
        $row = DB::table('codebridge_device_credentials')->where('device_id', 'device-a')->first();
        self::assertSame($oldRow->id, $row->id);
        self::assertSame($freshActivation, $row->activation_id);
        self::assertNull($row->revoked_at);
        self::assertSame(hash('sha256', $new['credential']), $row->token_hash);
        self::assertNotSame(hash('sha256', $old['credential']), $row->token_hash);
        self::assertNotNull(DB::table('kslp_activations')
            ->where('id', $activation)->value('deactivated_at'));
        self::assertDatabaseHas('kslp_license_events', [
            'license_id' => $license, 'action' => 'codebridge_device_reenrolled',
        ]);

        // The old activation cannot be re-used for any new device once its
        // credential row is replaced by a fresh proof-bound activation.
        $this->expectExceptionMessage('CODEBRIDGE_ENROLLMENT_DENIED');
        $enroll->enroll($license, $activation, 'tenant-a', 'device-b', time());
    }

    public function test_active_device_still_rejects_fresh_activation_without_disconnect(): void
    {
        [$license, $activation] = $this->fixture(2);
        $enroll = app(CodeBridgeDeviceEnrollmentService::class);
        $enroll->enroll($license, $activation, 'tenant-a', 'device-a', time());
        $next = (string) Str::uuid();
        DB::table('kslp_activations')->insert([
            'id' => $next, 'license_id' => $license,
            'server_identity' => 'ed25519:another-attempt',
            'machine_identity_hash' => str_repeat('d', 64),
            'idempotency_key' => 'attempt-'.Str::uuid(),
            'activated_at' => now(), 'created_at' => now(), 'updated_at' => now(),
        ]);

        $this->expectExceptionMessage('CODEBRIDGE_DEVICE_ALREADY_ENROLLED');
        $enroll->enroll($license, $next, 'tenant-a', 'device-a', time());
    }

    public function test_device_limit_is_enforced_before_credential_creation(): void
    {
        [$license, $activation] = $this->fixture(1);
        app(CodeBridgeDeviceEnrollmentService::class)->enroll($license, $activation, 'tenant-a', 'device-a', time());

        $activation2 = (string) Str::uuid();
        DB::table('kslp_activations')->insert([
            'id' => $activation2, 'license_id' => $license, 'server_identity' => 'ed25519:test-server-2',
            'machine_identity_hash' => str_repeat('b', 64), 'idempotency_key' => 'idem-2',
            'activated_at' => now(), 'created_at' => now(), 'updated_at' => now(),
        ]);

        $this->expectExceptionMessage('CODEBRIDGE_DEVICE_LIMIT');
        app(CodeBridgeDeviceEnrollmentService::class)->enroll($license, $activation2, 'tenant-a', 'device-b', time());
    }

    /** @return array{string,string} */
    private function fixture(int $devices): array
    {
        $license = (string) Str::uuid();
        $activation = (string) Str::uuid();
        DB::table('kslp_licenses')->insert([
            'id' => $license, 'customer_id' => 'tenant-a', 'product' => 'KMJ_CODEBRIDGE', 'plan' => 'professional',
            'status' => 'active', 'sequence' => 1, 'starts_at' => now()->subMinute(), 'expires_at' => now()->addYear(),
            'grace_until' => now()->addYear()->addDays(2), 'created_at' => now(), 'updated_at' => now(),
        ]);
        DB::table('kslp_activations')->insert([
            'id' => $activation, 'license_id' => $license, 'server_identity' => 'ed25519:test-server',
            'machine_identity_hash' => str_repeat('a', 64), 'idempotency_key' => 'idem-1',
            'activated_at' => now(), 'created_at' => now(), 'updated_at' => now(),
        ]);
        $product = (string) Str::uuid();
        DB::table('products')->insert([
            'id' => $product, 'slug' => 'codebridge', 'name' => 'CodeBridge', 'status' => 'active',
            'lifecycle' => 'available', 'is_public' => false, 'sort_order' => 100,
            'purchase_enabled' => false, 'licensing_enabled' => true, 'created_at' => now(), 'updated_at' => now(),
        ]);
        DB::table('plans')->insert([
            'id' => (string) Str::uuid(), 'product_id' => $product, 'code' => 'codebridge.professional',
            'name' => 'CodeBridge Professional', 'pricing_model' => 'license', 'billing_interval' => null,
            'currency' => null, 'amount_minor' => null, 'status' => 'active', 'trial_days' => 0,
            'features' => json_encode(['read' => true, 'write' => true, 'execute' => false]),
            'limits' => json_encode(['devices' => $devices]), 'created_at' => now(), 'updated_at' => now(),
        ]);

        return [$license, $activation];
    }
}
