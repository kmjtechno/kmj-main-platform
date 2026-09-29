<?php

namespace Tests\Feature;

use App\Services\Licensing\CodeBridge\CodeBridgeDeviceCredentialService;
use App\Services\Licensing\CodeBridge\CodeBridgeDeviceEnrollmentService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

final class CodeBridgeDeviceCredentialTest extends TestCase
{
  use RefreshDatabase;

  public function test_rotation_replaces_hash_preserves_sequence_and_never_persists_raw_secret(): void
  {
    [$license, $activation] = $this->fixture();
    $old = app(CodeBridgeDeviceEnrollmentService::class)->enroll($license, $activation, 'tenant-a', 'device-a', time());
    DB::table('codebridge_device_credentials')->where('activation_id', $activation)->update(['lease_sequence' => 7]);

    $new = app(CodeBridgeDeviceCredentialService::class)->rotate($license, 'tenant-a', 'device-a', time());
    self::assertNotSame($old['credential'], $new['credential']);

    $row = DB::table('codebridge_device_credentials')->where('activation_id', $activation)->first();
    self::assertSame(7, (int) $row->lease_sequence);
    self::assertSame(hash('sha256', $new['credential']), $row->token_hash);
    self::assertNotSame(hash('sha256', $old['credential']), $row->token_hash);
    self::assertDatabaseHas('kslp_license_events', ['license_id' => $license, 'action' => 'codebridge_device_credential_rotated']);
    self::assertStringNotContainsString($new['credential'], (string) DB::table('kslp_license_events')->where('action', 'codebridge_device_credential_rotated')->value('metadata'));
  }

  public function test_revocation_is_immediate_and_idempotent(): void
  {
    [$license, $activation] = $this->fixture();
    app(CodeBridgeDeviceEnrollmentService::class)->enroll($license, $activation, 'tenant-a', 'device-a', time());

    $service = app(CodeBridgeDeviceCredentialService::class);
    $service->revoke($license, 'tenant-a', 'device-a', time());
    $first = DB::table('kslp_license_events')->where('action', 'codebridge_device_credential_revoked')->count();
    $service->revoke($license, 'tenant-a', 'device-a', time());

    self::assertNotNull(DB::table('codebridge_device_credentials')->where('activation_id', $activation)->value('revoked_at'));
    self::assertSame(1, $first);
    self::assertSame(1, DB::table('kslp_license_events')->where('action', 'codebridge_device_credential_revoked')->count());
    $this->expectExceptionMessage('CODEBRIDGE_CREDENTIAL_DENIED');
    $service->rotate($license, 'tenant-a', 'device-a', time());
  }

  /** @return array{string, string} */
  private function fixture(): array
  {
    $license = (string) Str::uuid();\n        $activation = (string) Str::uuid();\n        $now = now();
    DB::table('kslp_licenses')->insert(['id' => $license, 'customer_id' => 'tenant-a', 'product' => 'KMJ_CODEBRIDGE', 'plan' => 'professional', 'status' => 'active', 'sequence' => 1, 'starts_at' => $now->copy()->subMinute(), 'expires_at' => $now->copy()->addYear(), 'grace_until' => $now->copy()->addYear()->addDays(2), 'created_at' => $now, 'updated_at' => $now]);
    DB::table('kslp_activations')->insert(['id' => $activation, 'license_id' => $license, 'server_identity' => 'ed25519:test-server', 'machine_identity_hash' => str_repeat('a', 64), 'idempotency_key' => 'credential-test', 'activated_at' => $now, 'created_at' => $now, 'updated_at' => $now]);
    $product=(string) Str::uuid();
    DB::table('products')->insert(['id' => $product, 'slug' => 'codebridge', 'name' => 'CodeBridge', 'status' => 'active', 'lifecycle' => 'available', 'is_public' => false, 'sort_order' => 100, 'purchase_enabled' => false, 'licensing_enabled' => true, 'created_at' => $now, 'updated_at' => $now]);
    DB::table('plans')->insert(['id' => (string) Str::uuid(), 'product_id' => $product, 'code' => 'codebridge.professional', 'name' => 'CodeBridge Professional', 'pricing_model' => 'license', 'status' => 'active', 'trial_days' => 0, 'features' => json_encode(['read' => true]), 'limits' => json_encode(['devices' => 1]), 'created_at' => $now, 'updated_at' => $now]);
    return [$license, $activation];
  }
}
