<?php

namespace Tests\Feature;

use App\Services\Licensing\Kslp\KslpActivationProof;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class KslpActivationProofTest extends TestCase
{
    use RefreshDatabase;

    private function identity(): array
    {
        $kp = sodium_crypto_sign_keypair();
        $sk = sodium_crypto_sign_secretkey($kp);
        $pk = sodium_crypto_sign_publickey($kp);
        $id = 'ed25519:'.rtrim(strtr(base64_encode($pk), '+/', '-_'), '=');

        return [$id, $sk];
    }

    public function test_challenge_proves_server_private_key_and_is_single_use(): void
    {
        $c = app(KslpLicenseControlPlane::class);
        $l = $c->issue('proof-customer', 'professional', 'owner');
        [$id,$sk] = $this->identity();
        $p = app(KslpActivationProof::class);
        $ch = $p->challenge($l['id'], $id);
        $msg = 'KSLP-ACTIVATE-v1|'.$l['id'].'|'.$ch['nonce'];
        $sig = rtrim(strtr(base64_encode(sodium_crypto_sign_detached($msg, $sk)), '+/', '-_'), '=');
        $p->consume($ch['challenge_id'], $l['id'], $id, $ch['nonce'], $sig);
        try {
            $p->consume($ch['challenge_id'], $l['id'], $id, $ch['nonce'], $sig);
            self::fail();
        } catch (\DomainException $e) {
            self::assertSame('KSLP_REPLAY', $e->getMessage());
        }
    }

    public function test_proof_expires_at_exact_five_minute_boundary_without_consumption(): void
    {
        $control = app(KslpLicenseControlPlane::class);
        $license = $control->issue('expiring-proof-customer', 'professional', 'owner');
        [$identity, $secret] = $this->identity();
        $proof = app(KslpActivationProof::class);
        $challenge = $proof->challenge($license['id'], $identity);
        $message = 'KSLP-ACTIVATE-v1|'.$license['id'].'|'.$challenge['nonce'];
        $signature = rtrim(strtr(
            base64_encode(sodium_crypto_sign_detached($message, $secret)),
            '+/',
            '-_',
        ), '=');

        $expiresAt = Carbon::parse(
            DB::table('kslp_activation_challenges')
                ->where('id', $challenge['challenge_id'])
                ->value('expires_at'),
        );
        $this->travelTo($expiresAt);
        try {
            try {
                $proof->consume(
                    $challenge['challenge_id'],
                    $license['id'],
                    $identity,
                    $challenge['nonce'],
                    $signature,
                );
                self::fail('Challenge at expiration must be rejected.');
            } catch (\DomainException $exception) {
                self::assertSame(
                    'KSLP_ACTIVATION_CHALLENGE_EXPIRED',
                    $exception->getMessage(),
                );
            }

            $this->assertDatabaseHas('kslp_activation_challenges', [
                'id' => $challenge['challenge_id'],
                'used_at' => null,
            ]);
        } finally {
            $this->travelBack();
        }
    }

    public function test_padded_device_identity_is_rejected_before_creating_challenge(): void
    {
        [$identity] = $this->identity();
        $proof = app(KslpActivationProof::class);

        try {
            $proof->challenge('not-needed-for-validation', $identity.'=');
            self::fail('Noncanonical public key representation must not be accepted.');
        } catch (\DomainException $exception) {
            self::assertSame('KSLP_SERVER_IDENTITY_INVALID', $exception->getMessage());
        }

        $this->assertDatabaseCount('kslp_activation_challenges', 0);
    }

    public function test_noncanonical_nonce_or_signature_does_not_consume_a_challenge(): void
    {
        $control = app(KslpLicenseControlPlane::class);
        $license = $control->issue('canonical-proof-customer', 'professional', 'owner');
        [$identity, $secret] = $this->identity();
        $proof = app(KslpActivationProof::class);
        $challenge = $proof->challenge($license['id'], $identity);
        $message = 'KSLP-ACTIVATE-v1|'.$license['id'].'|'.$challenge['nonce'];
        $signature = rtrim(strtr(
            base64_encode(sodium_crypto_sign_detached($message, $secret)),
            '+/',
            '-_',
        ), '=');

        foreach ([
            [$challenge['nonce'].'=', $signature],
            [$challenge['nonce'], $signature.'='],
        ] as [$nonce, $sig]) {
            try {
                $proof->consume(
                    $challenge['challenge_id'],
                    $license['id'],
                    $identity,
                    $nonce,
                    $sig,
                );
                self::fail('Noncanonical proof must not be accepted.');
            } catch (\DomainException $exception) {
                self::assertSame('KSLP_ACTIVATION_PROOF_INVALID', $exception->getMessage());
            }

            $this->assertDatabaseHas('kslp_activation_challenges', [
                'id' => $challenge['challenge_id'],
                'used_at' => null,
            ]);
        }

        $proof->consume(
            $challenge['challenge_id'],
            $license['id'],
            $identity,
            $challenge['nonce'],
            $signature,
        );
        $this->assertDatabaseMissing('kslp_activation_challenges', [
            'id' => $challenge['challenge_id'],
            'used_at' => null,
        ]);
    }

    public function test_wrong_server_private_key_is_rejected(): void
    {
        $c = app(KslpLicenseControlPlane::class);
        $l = $c->issue('proof-customer-2', 'professional', 'owner');
        [$id,$sk] = $this->identity();
        [, $wrong] = $this->identity();
        $p = app(KslpActivationProof::class);
        $ch = $p->challenge($l['id'], $id);
        $msg = 'KSLP-ACTIVATE-v1|'.$l['id'].'|'.$ch['nonce'];
        $sig = rtrim(strtr(base64_encode(sodium_crypto_sign_detached($msg, $wrong)), '+/', '-_'), '=');
        $this->expectExceptionMessage('KSLP_ACTIVATION_PROOF_INVALID');
        $p->consume($ch['challenge_id'], $l['id'], $id, $ch['nonce'], $sig);
    }
}
