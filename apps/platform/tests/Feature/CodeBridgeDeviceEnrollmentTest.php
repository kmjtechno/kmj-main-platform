<?php

namespace Tests\Feature;

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
        DB::table('plans')->insert([
            'code' => 'codebridge.professional', 'name' => 'CodeBridge Professional', 'status' => 'active',
            'features' => json_encode(['read' => true, 'write' => true, 'execute' => false]),
            'limits' => json_encode(['devices' => $devices]), 'created_at' => now(), 'updated_at' => now(),
        ]);

        return [$license, $activation];
    }
}
