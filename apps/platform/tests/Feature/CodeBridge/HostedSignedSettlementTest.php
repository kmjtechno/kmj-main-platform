<?php

declare(strict_types=1);

namespace Tests\Feature\CodeBridge;

use App\Models\User;
use App\Services\CodeBridge\HostedExecutionReceiptVerifier;
use App\Services\CodeBridge\HostedSignedSettlement;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class HostedSignedSettlementTest extends TestCase
{
    use RefreshDatabase;

    public function test_exact_binding_settles_only_a_valid_signature_once(): void
    {
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $org = $this->tenant($owner, 'desk-a', 'proj-a');
        $service = app(HostedSignedSettlement::class);
        $pair = sodium_crypto_sign_keypair();
        $public = base64_encode(sodium_crypto_sign_publickey($pair));
        $execution = (string) Str::uuid();
        $hash = str_repeat('a', 64);
        $service->pinApprovedSigner($owner, $org, 'desk-a', $public);
        $first = $service->reserveForOwner($owner, $org, 'desk-a', 'proj-a', $execution, $hash);
        self::assertSame(9999, $first['remaining']);
        self::assertSame($first, $service->reserveForOwner($owner, $org, 'desk-a', 'proj-a', $execution, $hash));

        $message = app(HostedExecutionReceiptVerifier::class)->message([
            'organization_id' => $org,
            'subject_key' => 'account',
            'execution_id' => $execution,
            'device_id' => 'desk-a',
            'project_id' => 'proj-a',
            'request_sha256' => $hash,
            'outcome' => 'succeeded',
        ]);
        self::assertIsString($message);
        $signature = base64_encode(sodium_crypto_sign_detached($message, sodium_crypto_sign_secretkey($pair)));
        try {
            $service->settleSigned($org, $execution, 'failed', $signature);
            self::fail('Wrong outcome must not settle.');
        } catch (DomainException $exception) {
            self::assertSame('CODEBRIDGE_MONTHLY_COMPLETION_PROOF_REQUIRED', $exception->getMessage());
        }
        self::assertDatabaseHas('codebridge_usage_periods', ['completed_calls' => 0, 'reserved_calls' => 1]);
        $result = $service->settleSigned($org, $execution, 'succeeded', $signature);
        self::assertSame(1, $result['completed']);
        self::assertSame(0, $result['reserved']);
        self::assertSame($result, $service->settleSigned($org, $execution, 'succeeded', $signature));
    }

    public function test_foreign_owner_cannot_pin_a_key(): void
    {
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $stranger = User::factory()->create(['email_verified_at' => now()]);
        $org = $this->tenant($owner, 'desk-a', 'proj-a');
        $pair = sodium_crypto_sign_keypair();

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('CODEBRIDGE_RECEIPT_SCOPE_DENIED');
        app(HostedSignedSettlement::class)->pinApprovedSigner($stranger, $org, 'desk-a', base64_encode(sodium_crypto_sign_publickey($pair)));
    }

    private function tenant(User $owner, string $device, string $project, array $permissions = ['read', 'write', 'execute']): string
    {
        $tenant = (string) app(OrganizationCreator::class)->create('Receipt test org', (int) $owner->getKey())->getKey();
        $license = (string) Str::uuid();
        $activation = (string) Str::uuid();
        $now = now();
        DB::table('kslp_licenses')->insert([
            'id' => $license, 'customer_id' => $tenant, 'product' => 'KMJ_CODEBRIDGE', 'plan' => 'community',
            'status' => 'active', 'sequence' => 1, 'starts_at' => $now->copy()->subDay(), 'expires_at' => $now->copy()->addYear(),
            'grace_until' => $now->copy()->addYear()->addDays(2), 'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('kslp_activations')->insert([
            'id' => $activation, 'license_id' => $license, 'server_identity' => 'codebridge-device:'.$device,
            'machine_identity_hash' => hash('sha256', $device), 'idempotency_key' => 'workspace-jobs-test:'.$device,
            'activated_at' => $now, 'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('codebridge_device_credentials')->insert([
            'id' => (string) Str::uuid(), 'license_id' => $license, 'activation_id' => $activation, 'tenant_id' => $tenant,
            'device_id' => $device, 'server_identity' => 'codebridge-device:'.$device,
            'token_hash' => hash('sha256', 'fixture-token:'.$device), 'lease_sequence' => 0, 'expires_at_epoch' => time() + 3600,
        ]);
        DB::table('codebridge_device_pairings')->insert([
            'id' => (string) Str::uuid(), 'device_code_hash' => hash('sha256', 'device-code:'.$device),
            'user_code_hash' => hash('sha256', 'user-code:'.$device), 'device_id' => $device, 'device_name' => $device,
            'platform' => 'win32', 'arch' => 'x64', 'project_id' => $project, 'project_name' => $project,
            'requested_permissions' => json_encode($permissions), 'code_challenge' => str_repeat('x', 43),
            'status' => 'consumed', 'tenant_id' => $tenant, 'license_id' => $license, 'activation_id' => $activation,
            'expires_at' => $now->copy()->addMinutes(5), 'consumed_at' => $now, 'created_at' => $now, 'updated_at' => $now,
        ]);

        return $tenant;
    }
}
