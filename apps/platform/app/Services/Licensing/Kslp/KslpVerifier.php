<?php

namespace App\Services\Licensing\Kslp;

use DomainException;

final class KslpVerifier
{
    /**
     * @return array<array-key, mixed>
     */
    public function verify(string $token, callable $publicKeyForKid, string $serverIdentity, int $now, string $expectedProduct = 'KMJ_CLOUDOS'): array
    {
        [$h,$c,$sig,$signed] = KslpCodec::decode($token);
        $required = ['protocol_version', 'license_id', 'customer_id', 'product', 'plan', 'server_identity', 'activation_id', 'features', 'limits', 'iat', 'nbf', 'exp', 'sequence', 'nonce', 'kid', 'jti', 'aud'];
        foreach ($required as $k) {
            if (! array_key_exists($k, $c)) {
                throw new DomainException('KSLP_MALFORMED');
            }
        }
        if ($c['protocol_version'] !== 'KSLP-v1') {
            throw new DomainException('KSLP_UNSUPPORTED_VERSION');
        }
        if ($c['product'] !== $expectedProduct) {
            throw new DomainException('KSLP_WRONG_PRODUCT');
        }
        if ($c['aud'] !== 'kmj-cloudos') {
            throw new DomainException('KSLP_WRONG_AUDIENCE');
        }
        if ($c['server_identity'] !== $serverIdentity) {
            throw new DomainException('KSLP_SERVER_MISMATCH');
        }
        if ($c['kid'] !== ($h['kid'] ?? null)) {
            throw new DomainException('KSLP_MALFORMED');
        }
        if ($now < (int) $c['nbf']) {
            throw new DomainException('KSLP_NOT_YET_VALID');
        }
        if ($now > (int) $c['exp']) {
            throw new DomainException('KSLP_EXPIRED');
        }
        $pk = $publicKeyForKid($c['kid']);
        if (! is_string($pk) || strlen($pk) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES) {
            throw new DomainException('KSLP_UNKNOWN_KID');
        }
        if (! sodium_crypto_sign_verify_detached($sig, $signed, $pk)) {
            throw new DomainException('KSLP_INVALID_SIGNATURE');
        }

        return $c;
    }
}
