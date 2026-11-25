<?php

declare(strict_types=1);

namespace Tests\Feature\CodeBridge;

use App\Models\User;
use App\Services\CodeBridge\HostedExecutionReceiptVerifier;
use App\Services\CodeBridge\HostedPilotUsageSnapshot;
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

    public function test_real_http_pilot_round_trip_and_scoped_dashboard_snapshot(): void
    {
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $stranger = User::factory()->create(['email_verified_at' => now()]);
        $org = $this->tenant($owner, 'desk-a', 'proj-a');
        $pair = sodium_crypto_sign_keypair();
        $execution = (string) Str::uuid();
        $token = str_repeat('z', 43);
        config()->set('codebridge.enabled', true);
        config()->set('codebridge.hosted_metering_pilot_enabled', true);
        config()->set('codebridge.hosted_metering_pilot_tenant', $org);
        config()->set('codebridge.hosted_metering_pilot_token_hash', hash('sha256', $token));
        $snapshot = app(HostedPilotUsageSnapshot::class);
        self::assertNull($snapshot->forOwner($owner, $org));
        app(HostedSignedSettlement::class)->pinApprovedSigner($owner, $org, 'desk-a', base64_encode(sodium_crypto_sign_publickey($pair)));
        $path = '/api/codebridge/v1/hosted-metering-pilot';
        $reserve = [
            'action' => 'reserve',
            'organization_id' => $org,
            'execution_id' => $execution,
            'user_subject' => 'kmj-user:'.$owner->getKey(),
            'device_id' => 'desk-a',
            'project_id' => 'proj-a',
            'tool' => 'git_status',
        ];
        $hash = hash('sha256', "git_status\ndesk-a\nproj-a\n");
        $this->withToken($token)->postJson($path, $reserve)->assertOk()
            ->assertExactJson(['reserved' => true, 'request_sha256' => $hash]);
        $this->withToken($token)->postJson($path, $reserve)->assertConflict();
        self::assertSame(1, $snapshot->forOwner($owner, $org)['reserved']);
        self::assertNull($snapshot->forOwner($stranger, $org));
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
        $settle = [
            'action' => 'settle',
            'organization_id' => $org,
            'execution_id' => $execution,
            'outcome' => 'succeeded',
            'signature' => $signature,
        ];
        $this->withToken($token)->postJson($path, [...$settle, 'signature' => 'wrong'])->assertConflict();
        $this->withToken($token)->postJson($path, $settle)->assertOk()->assertExactJson(['settled' => true]);
        $this->withToken($token)->postJson($path, $settle)->assertOk();
        $this->withToken($token)->postJson($path, $reserve)->assertConflict();
        $result = $snapshot->forOwner($owner, $org);
        self::assertSame('pilot_only', $result['status']);
        self::assertFalse($result['billable']);
        self::assertSame(1, $result['completed']);
        self::assertSame(0, $result['reserved']);
        self::assertSame(9999, $result['remaining']);
        self::assertArrayNotHasKey('verified_signature', $result);
        DB::table('codebridge_receipt_bindings')->where('execution_id', $execution)->update(['verified_signature' => null]);
        self::assertNull($snapshot->forOwner($owner, $org));
        config()->set('codebridge.hosted_metering_pilot_enabled', false);
        self::assertNull($snapshot->forOwner($owner, $org));
    }

    public function test_owner_signer_enrollment_requires_fresh_proof_and_consumes_challenge(): void
    {
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $org = $this->tenant($owner, 'desk-a', 'proj-a');
        config()->set('codebridge.enabled', true);
        config()->set('codebridge.hosted_metering_pilot_enabled', true);
        config()->set('codebridge.hosted_metering_pilot_tenant', $org);
        $path = '/services/kmj-codebridge/organizations/'.$org.'/devices/desk-a/receipt-signer';
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()]);
        $challenge = $this->postJson($path.'/challenge')->assertOk()->json();
        $pair = sodium_crypto_sign_keypair();
        $public = base64_encode(sodium_crypto_sign_publickey($pair));
        $message = implode("\n", [
            'KMJ_CODEBRIDGE_SIGNER_ENROLLMENT_V1',
            $org,
            'desk-a',
            $challenge['activation_id'],
            $challenge['credential_id'],
            (string) $owner->getKey(),
            $challenge['nonce'],
            (string) $challenge['expires_at'],
            $public,
            '',
        ]);
        $input = [
            'public_key' => $public,
            'signature' => base64_encode(sodium_crypto_sign_detached($message, sodium_crypto_sign_secretkey($pair))),
            'confirm' => 'APPROVE_DEVICE_RECEIPT_SIGNER',
        ];
        $this->postJson($path.'/confirm', $input)->assertOk()->assertExactJson(['enrollment' => 'PINNED']);
        $this->postJson($path.'/confirm', $input)->assertConflict();
        self::assertDatabaseHas('codebridge_receipt_signers', ['public_key' => $public]);
        $this->postJson($path.'/challenge')->assertOk();
        $this->postJson($path.'/confirm', $input)->assertConflict();
        $this->assertDatabaseCount('codebridge_receipt_signers', 1);
    }

    public function test_signer_challenge_denies_unconfirmed_foreign_and_disabled_requests(): void
    {
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $stranger = User::factory()->create(['email_verified_at' => now()]);
        $org = $this->tenant($owner, 'desk-a', 'proj-a');
        config()->set('codebridge.enabled', true);
        config()->set('codebridge.hosted_metering_pilot_enabled', true);
        config()->set('codebridge.hosted_metering_pilot_tenant', $org);
        $path = '/services/kmj-codebridge/organizations/'.$org.'/devices/desk-a/receipt-signer';
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => 0]);
        $this->postJson($path.'/challenge')->assertStatus(423);
        $this->actingAs($stranger)->withSession(['auth.password_confirmed_at' => time()]);
        $this->postJson($path.'/challenge')->assertForbidden();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()]);
        config()->set('codebridge.hosted_metering_pilot_enabled', false);
        $this->postJson($path.'/challenge')->assertStatus(503);
        $this->assertDatabaseCount('codebridge_receipt_signers', 0);
    }

    public function test_expired_signer_challenge_cannot_pin_even_with_a_valid_signature(): void
    {
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $org = $this->tenant($owner, 'desk-a', 'proj-a');
        $service = app(HostedSignedSettlement::class);
        $challenge = $service->issueSignerChallenge($owner, $org, 'desk-a');
        $challenge['expires_at'] = time() - 1;
        $pair = sodium_crypto_sign_keypair();
        $public = base64_encode(sodium_crypto_sign_publickey($pair));
        $message = implode("\n", [
            'KMJ_CODEBRIDGE_SIGNER_ENROLLMENT_V1',
            $org,
            'desk-a',
            $challenge['activation_id'],
            $challenge['credential_id'],
            (string) $owner->getKey(),
            $challenge['nonce'],
            (string) $challenge['expires_at'],
            $public,
            '',
        ]);
        $signature = base64_encode(sodium_crypto_sign_detached($message, sodium_crypto_sign_secretkey($pair)));
        try {
            $service->confirmSignerChallenge($owner, $org, 'desk-a', $challenge, $public, $signature);
            self::fail('Expired proof must not pin a signer.');
        } catch (DomainException $exception) {
            self::assertSame('CODEBRIDGE_SIGNER_PROOF_DENIED', $exception->getMessage());
        }
        $this->assertDatabaseCount('codebridge_receipt_signers', 0);
    }

    public function test_signer_enrollment_requires_consumed_pairing(): void
    {
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $org = $this->tenant($owner, 'desk-a', 'proj-a');
        $service = app(HostedSignedSettlement::class);
        DB::table('codebridge_device_pairings')->where('tenant_id', $org)
            ->update(['status' => 'approved', 'consumed_at' => null]);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('CODEBRIDGE_RECEIPT_SCOPE_DENIED');
        $service->issueSignerChallenge($owner, $org, 'desk-a');
    }

    public function test_team_device_license_alone_cannot_authorize_a_paid_seat(): void
    {
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $org = $this->tenant($owner, 'desk-a', 'proj-a');
        $service = app(HostedSignedSettlement::class);
        $pair = sodium_crypto_sign_keypair();
        $service->pinApprovedSigner($owner, $org, 'desk-a', base64_encode(sodium_crypto_sign_publickey($pair)));
        DB::table('kslp_licenses')->where('customer_id', $org)->update(['plan' => 'team']);

        try {
            $service->reserveForOwner($owner, $org, 'desk-a', 'proj-a', (string) Str::uuid(), str_repeat('a', 64));
            self::fail('A device license must not be treated as a paid human seat.');
        } catch (DomainException $exception) {
            self::assertSame('CODEBRIDGE_MONTHLY_PLAN_UNAVAILABLE', $exception->getMessage());
        }
        $this->assertDatabaseCount('codebridge_receipt_bindings', 0);
        $this->assertDatabaseCount('codebridge_usage_executions', 0);
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
