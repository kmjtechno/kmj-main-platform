<?php

namespace Tests\Feature;

use App\Services\Licensing\Kslp\KslpActivationProof;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use Illuminate\Foundation\Testing\RefreshDatabase;
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
