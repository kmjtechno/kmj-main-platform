<?php

namespace App\Services\Licensing\Kslp;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

final class KslpActivationProof
{
    /**
     * @return array<array-key, mixed>
     */
    public function challenge(string $licenseId, string $serverIdentity): array
    {
        $this->publicKey($serverIdentity);
        $nonce = random_bytes(32);
        $id = (string) Str::uuid();
        DB::table('kslp_activation_challenges')->insert(['id' => $id, 'license_id' => $licenseId, 'server_identity' => $serverIdentity, 'nonce_hash' => hash('sha256', $nonce), 'expires_at' => now()->addMinutes(5), 'created_at' => now()]);

        return ['challenge_id' => $id, 'nonce' => $this->b64($nonce), 'expires_in' => 300];
    }

    public function consume(string $challengeId, string $licenseId, string $serverIdentity, string $nonce, string $signature): void
    {
        DB::transaction(function () use ($challengeId, $licenseId, $serverIdentity, $nonce, $signature) {
            $c = DB::table('kslp_activation_challenges')->where('id', $challengeId)->lockForUpdate()->first();
            if (! $c || $c->license_id !== $licenseId || $c->server_identity !== $serverIdentity) {
                throw new DomainException('KSLP_ACTIVATION_PROOF_INVALID');
            }
            if ($c->used_at) {
                throw new DomainException('KSLP_REPLAY');
            }
            if (now()->gt($c->expires_at)) {
                throw new DomainException('KSLP_ACTIVATION_CHALLENGE_EXPIRED');
            }
            $raw = $this->unb64($nonce);
            if (! hash_equals($c->nonce_hash, hash('sha256', $raw))) {
                throw new DomainException('KSLP_ACTIVATION_PROOF_INVALID');
            }
            $sig = $this->unb64($signature);
            $msg = 'KSLP-ACTIVATE-v1|'.$licenseId.'|'.$nonce;
            if ($sig === '' || strlen($sig) !== SODIUM_CRYPTO_SIGN_BYTES || ! sodium_crypto_sign_verify_detached($sig, $msg, $this->publicKey($serverIdentity))) {
                throw new DomainException('KSLP_ACTIVATION_PROOF_INVALID');
            }
            DB::table('kslp_activation_challenges')->where('id', $challengeId)->update(['used_at' => now()]);
        }, 3);
    }

    /** @return non-empty-string */
    private function publicKey(string $identity): string
    {
        if (! str_starts_with($identity, 'ed25519:')) {
            throw new DomainException('KSLP_SERVER_IDENTITY_INVALID');
        }
        try {
            $pk = $this->unb64(substr($identity, 8));
        } catch (DomainException) {
            throw new DomainException('KSLP_SERVER_IDENTITY_INVALID');
        }
        if ($pk === '' || strlen($pk) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES) {
            throw new DomainException('KSLP_SERVER_IDENTITY_INVALID');
        }

        return $pk;
    }

    private function b64(string $v): string
    {
        return rtrim(strtr(base64_encode($v), '+/', '-_'), '=');
    }

    private function unb64(string $v): string
    {
        // A challenge, identity or signature must use exactly one canonical,
        // unpadded base64url representation. No whitespace, standard
        // base64 alphabet or alternative padding is accepted.
        if ($v === '' || preg_match('/\\A[A-Za-z0-9_-]+\\z/', $v) !== 1) {
            throw new DomainException('KSLP_ACTIVATION_PROOF_INVALID');
        }

        $x = base64_decode(strtr($v, '-_', '+/'), true);
        if ($x === false || ! hash_equals($this->b64($x), $v)) {
            throw new DomainException('KSLP_ACTIVATION_PROOF_INVALID');
        }

        return $x;
    }
}
