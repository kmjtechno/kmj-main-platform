<?php

namespace Tests\Feature;

use App\Services\Licensing\Kslp\KslpActivationProof;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use App\Services\Licensing\Kslp\KslpSigner;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Catalog\Models\Plan;
use KMJ\MainPlatform\Catalog\Models\Product;
use Tests\TestCase;

final class KslpLifecycleTest extends TestCase
{
    use RefreshDatabase;

    private function proof(string $licenseId): array
    {
        $kp = sodium_crypto_sign_keypair();
        $sk = sodium_crypto_sign_secretkey($kp);
        $pk = sodium_crypto_sign_publickey($kp);
        $id = 'ed25519:'.rtrim(strtr(base64_encode($pk), '+/', '-_'), '=');
        $ch = app(KslpActivationProof::class)->challenge($licenseId, $id);
        $msg = 'KSLP-ACTIVATE-v1|'.$licenseId.'|'.$ch['nonce'];
        $sig = rtrim(strtr(base64_encode(sodium_crypto_sign_detached($msg, $sk)), '+/', '-_'), '=');

        return [$id, $ch['challenge_id'], $ch['nonce'], $sig];
    }

    private function activate(KslpLicenseControlPlane $c, string $id, string $key): array
    {
        [$server,$challenge,$nonce,$sig] = $this->proof($id);

        return [$c->activate($id, $server, str_repeat('a', 64), $key, 'owner', $challenge, $nonce, $sig), $server];
    }

    public function test_trial_activation_idempotency_transfer_and_states(): void
    {
        $c = app(KslpLicenseControlPlane::class);
        $l = $c->issue('cust-1', 'trial', 'owner');
        self::assertSame(30.0, Carbon::parse($l['starts_at'])->diffInDays(Carbon::parse($l['expires_at'])));
        [$a] = $this->activate($c, $l['id'], 'retry-1');
        $again = $c->activate($l['id'], $a['server_identity'], str_repeat('a', 64), 'retry-1', 'owner', 'unused', 'unused', 'unused');
        self::assertSame($a['id'], $again['id']);
        self::assertSame('ACTIVE', $c->state($l['id'], Carbon::parse($l['starts_at'])->addDay()));
        [$newServer,$challenge,$nonce,$sig] = $this->proof($l['id']);
        $b = $c->transfer($l['id'], $newServer, str_repeat('b', 64), 'retry-2', 'owner', 'replacement', $challenge, $nonce, $sig);
        self::assertNotSame($a['id'], $b['id']);
        $this->assertDatabaseCount('kslp_license_events', 4);
    }

    public function test_trial_cannot_reset_and_revoke_reactivate_plan_change_work(): void
    {
        $c = app(KslpLicenseControlPlane::class);
        $l = $c->issue('cust-2', 'trial', 'owner');
        try {
            $c->issue('cust-2', 'trial', 'owner');
            self::fail();
        } catch (\DomainException $e) {
            self::assertSame('KSLP_TRIAL_ALREADY_USED', $e->getMessage());
        }$c->changePlan($l['id'], 'professional', 'owner', 'paid');
        $c->revoke($l['id'], 'owner', 'security');
        self::assertSame('REVOKED', $c->state($l['id']));
        $c->reactivate($l['id'], 'owner', 'cleared');
        self::assertNotSame('REVOKED', $c->state($l['id']));
    }

    public function test_signed_lease_is_server_bound(): void
    {
        $c = app(KslpLicenseControlPlane::class);
        $l = $c->issue('cust-3', 'business', 'owner');
        [$a] = $this->activate($c, $l['id'], 'retry-3');
        $kp = sodium_crypto_sign_keypair();
        $sk = sodium_crypto_sign_secretkey($kp);
        $signer = new class($sk) implements KslpSigner
        {
            public function __construct(private string $sk) {}

            public function kid(): string
            {
                return 'test-kid';
            }

            public function sign(string $m): string
            {
                return sodium_crypto_sign_detached($m, $this->sk);
            }
        };
        $product = Product::query()->create(['slug' => 'cloudos-test', 'name' => 'CloudOS', 'status' => 'active']);
        Plan::query()->create(['product_id' => $product->id, 'code' => 'cloudos.business', 'name' => 'Business', 'pricing_model' => 'quote', 'status' => 'active', 'features' => ['hosting' => true], 'limits' => ['nodes' => 3]]);
        $token = $c->lease($l['id'], $a['id'], $signer);
        self::assertSame(3, count(explode('.', $token)));
    }

    public function test_cloudos_lease_signer_rejects_omnidesk_before_signing(): void
    {
        $control = app(KslpLicenseControlPlane::class);
        $license = $control->issue('cross-product-tenant', 'business', 'owner');
        [$activation] = $this->activate($control, $license['id'], 'cross-product-activation');

        DB::table('kslp_licenses')
            ->where('id', $license['id'])
            ->update(['product' => 'KMJ_OMNIDESK']);

        $signer = new class implements KslpSigner
        {
            public function kid(): string
            {
                throw new \\RuntimeException('KSLP signer must not be consulted for another product');
            }

            public function sign(string $message): string
            {
                throw new \\RuntimeException('KSLP signer must not sign another product');
            }
        };

        $this->expectException(\\DomainException::class);
        $this->expectExceptionMessage('KSLP_WRONG_PRODUCT');
        $control->lease($license['id'], $activation['id'], $signer);
    }

    public function test_sensitive_mutation_requires_a_specific_audit_reason(): void
    {
        $c = app(KslpLicenseControlPlane::class);
        $l = $c->issue('cust-reason', 'business', 'owner');
        $this->expectException(\DomainException::class);
        $this->expectExceptionMessage('KSLP_REASON_REQUIRED');
        $c->revoke($l['id'], 'owner', ' ');
    }

    public function test_idempotency_key_cannot_replay_another_customers_activation(): void
    {
        $control = app(KslpLicenseControlPlane::class);
        $first = $control->issue('idempotency-customer-a', 'professional', 'owner');
        $second = $control->issue('idempotency-customer-b', 'professional', 'owner');
        [$activation, $server] = $this->activate($control, $first['id'], 'shared-retry-key');

        self::assertSame($first['id'], $activation['license_id']);
        $this->expectExceptionMessage('KSLP_ACTIVATION_CONFLICT');
        $control->activate(
            $second['id'],
            $server,
            str_repeat('a', 64),
            'shared-retry-key',
            'owner',
            'unused',
            'unused',
            'unused',
        );
    }

    public function test_idempotency_retry_rejects_different_device_or_hardware(): void
    {
        $control = app(KslpLicenseControlPlane::class);
        $license = $control->issue('idempotency-customer-device', 'professional', 'owner');
        [, $server] = $this->activate($control, $license['id'], 'device-retry');

        try {
            $control->activate(
                $license['id'], 'ed25519:other', str_repeat('a', 64),
                'device-retry', 'owner', 'unused', 'unused', 'unused',
            );
            self::fail('A mismatched device reused the idempotency key.');
        } catch (\DomainException $e) {
            self::assertSame('KSLP_ACTIVATION_CONFLICT', $e->getMessage());
        }

        $this->expectExceptionMessage('KSLP_ACTIVATION_CONFLICT');
        $control->activate(
            $license['id'], $server, str_repeat('b', 64),
            'device-retry', 'owner', 'unused', 'unused', 'unused',
        );
    }

    public function test_an_active_device_cannot_silently_change_hardware_identity(): void
    {
        $control = app(KslpLicenseControlPlane::class);
        $license = $control->issue('idempotency-customer-hardware', 'professional', 'owner');
        $pair = sodium_crypto_sign_keypair();
        $secret = sodium_crypto_sign_secretkey($pair);
        $public = sodium_crypto_sign_publickey($pair);
        $server = 'ed25519:'.rtrim(strtr(base64_encode($public), '+/', '-_'), '=');
        $proofs = app(KslpActivationProof::class);

        $first = $proofs->challenge($license['id'], $server);
        $firstSignature = rtrim(strtr(base64_encode(sodium_crypto_sign_detached(
            'KSLP-ACTIVATE-v1|'.$license['id'].'|'.$first['nonce'],
            $secret,
        )), '+/', '-_'), '=');
        $control->activate(
            $license['id'], $server, str_repeat('a', 64), 'initial-device',
            'owner', $first['challenge_id'], $first['nonce'], $firstSignature,
        );

        $next = $proofs->challenge($license['id'], $server);
        $nextSignature = rtrim(strtr(base64_encode(sodium_crypto_sign_detached(
            'KSLP-ACTIVATE-v1|'.$license['id'].'|'.$next['nonce'],
            $secret,
        )), '+/', '-_'), '=');

        // Despite VALID proof of the original private key, a changed
        // machine hash must use the audited transfer path.
        $this->expectExceptionMessage('KSLP_ACTIVATION_CONFLICT');
        $control->activate(
            $license['id'], $server, str_repeat('b', 64),
            'new-hardware-attempt', 'owner',
            $next['challenge_id'], $next['nonce'], $nextSignature,
        );
    }

    public function test_deactivated_activation_cannot_be_resurrected_by_retry_key(): void
    {
        $control = app(KslpLicenseControlPlane::class);
        $license = $control->issue('idempotency-customer-transfer', 'professional', 'owner');
        [, $previousServer] = $this->activate($control, $license['id'], 'initial-transfer-key');
        [$newServer, $challenge, $nonce, $signature] = $this->proof($license['id']);
        $control->transfer(
            $license['id'], $newServer, str_repeat('b', 64),
            'replacement-transfer-key', 'owner', 'approved transfer',
            $challenge, $nonce, $signature,
        );

        $this->expectExceptionMessage('KSLP_ACTIVATION_CONFLICT');
        $control->activate(
            $license['id'], $previousServer, str_repeat('a', 64),
            'initial-transfer-key', 'owner', 'unused', 'unused', 'unused',
        );
    }

    public function test_revoked_license_does_not_return_cached_activation_on_retry(): void
    {
        $control = app(KslpLicenseControlPlane::class);
        $license = $control->issue('idempotency-customer-revoked', 'professional', 'owner');
        [, $server] = $this->activate($control, $license['id'], 'revoked-retry-key');
        $control->revoke($license['id'], 'owner', 'fraud investigation');

        $this->expectExceptionMessage('KSLP_REVOKED');
        $control->activate(
            $license['id'], $server, str_repeat('a', 64),
            'revoked-retry-key', 'owner', 'unused', 'unused', 'unused',
        );
    }

    public function test_failed_seat_change_does_not_consume_valid_activation_challenge(): void
    {
        $control = app(KslpLicenseControlPlane::class);
        $license = $control->issue('idempotency-challenge-retry', 'professional', 'owner');
        $this->activate($control, $license['id'], 'original-active-seat');

        [$otherServer, $challenge, $nonce, $signature] = $this->proof($license['id']);
        try {
            $control->activate(
                $license['id'],
                $otherServer,
                str_repeat('b', 64),
                'unapproved-seat-change',
                'owner',
                $challenge,
                $nonce,
                $signature,
            );
            self::fail('Unapproved device reuse must not succeed.');
        } catch (\DomainException $exception) {
            self::assertSame('KSLP_ACTIVATION_CONFLICT', $exception->getMessage());
        }

        $pendingChallenge = DB::table('kslp_activation_challenges')->where('id', $challenge)->first();
        self::assertNotNull($pendingChallenge);
        self::assertNull($pendingChallenge->used_at, 'Rejected seat change must roll back proof consumption.');
    }

    public function test_retried_successful_transfer_keeps_new_activation_and_single_audit_event(): void
    {
        $control = app(KslpLicenseControlPlane::class);
        $license = $control->issue('transfer-idempotent-customer', 'professional', 'owner');
        $this->activate($control, $license['id'], 'transfer-old-device');

        [$server, $challenge, $nonce, $proof] = $this->proof($license['id']);
        $first = $control->transfer(
            $license['id'], $server, str_repeat('b', 64),
            'same-transfer-key', 'owner', 'approved replacement',
            $challenge, $nonce, $proof,
        );
        $retry = $control->transfer(
            $license['id'], $server, str_repeat('b', 64),
            'same-transfer-key', 'owner', 'same approved replacement',
            'unused', 'unused', 'unused',
        );

        self::assertSame($first['id'], $retry['id']);
        self::assertSame(
            1,
            DB::table('kslp_activations')->where('license_id', $license['id'])->whereNull('deactivated_at')->count(),
        );
        self::assertSame(
            1,
            DB::table('kslp_license_events')
                ->where('license_id', $license['id'])
                ->where('action', 'transferred')
                ->count(),
        );
    }

    public function test_foreign_transfer_retry_key_does_not_disable_current_device(): void
    {
        $control = app(KslpLicenseControlPlane::class);
        $first = $control->issue('foreign-transfer-customer-a', 'professional', 'owner');
        $second = $control->issue('foreign-transfer-customer-b', 'professional', 'owner');
        $this->activate($control, $first['id'], 'foreign-used-idempotency-key');
        [$active] = $this->activate($control, $second['id'], 'legitimate-second-device');

        try {
            $control->transfer(
                $second['id'], $active['server_identity'], str_repeat('a', 64),
                'foreign-used-idempotency-key', 'owner', 'unauthorized retry',
                'unused', 'unused', 'unused',
            );
            self::fail('Foreign license retry should be rejected.');
        } catch (\DomainException $exception) {
            self::assertSame('KSLP_ACTIVATION_CONFLICT', $exception->getMessage());
        }

        self::assertNull(
            DB::table('kslp_activations')->where('id', $active['id'])->value('deactivated_at'),
            'Foreign transfer retry must not deactivate the existing seat.',
        );
    }

    public function test_expired_license_rejects_idempotent_activation_retry(): void
    {
        $control = app(KslpLicenseControlPlane::class);
        $license = $control->issue('customer-expired-retry', 'trial', 'owner');
        [$activation, $server] = $this->activate($control, $license['id'], 'expired-retry-key');

        DB::table('kslp_licenses')
            ->where('id', $license['id'])
            ->update(['expires_at' => now()->subMinute()]);

        $this->expectExceptionMessage('KSLP_EXPIRED');
        $control->activate(
            $license['id'], $server, str_repeat('a', 64), 'expired-retry-key',
            'owner', 'unused', 'unused', 'unused',
        );
    }

    public function test_inactive_license_rejects_idempotent_activation_retry(): void
    {
        $control = app(KslpLicenseControlPlane::class);
        $license = $control->issue('customer-paused-retry', 'trial', 'owner');
        [, $server] = $this->activate($control, $license['id'], 'paused-retry-key');

        DB::table('kslp_licenses')
            ->where('id', $license['id'])
            ->update(['status' => 'suspended']);

        $this->expectExceptionMessage('KSLP_ACTIVATION_CONFLICT');
        $control->activate(
            $license['id'], $server, str_repeat('a', 64), 'paused-retry-key',
            'owner', 'unused', 'unused', 'unused',
        );
    }
}
