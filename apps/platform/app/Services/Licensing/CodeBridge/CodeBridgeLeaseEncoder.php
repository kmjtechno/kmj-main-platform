<?php

declare(strict_types=1);

namespace App\Services\Licensing\CodeBridge;

use App\Services\Licensing\Kslp\KslpSigner;
use DomainException;

/** Encodes already-authorized entitlements; never decides purchase or trial eligibility. */
final class CodeBridgeLeaseEncoder
{
    public function encode(array $claims, KslpSigner $signer, int $now): string
    {
        $required = ['v', 'product', 'tenant', 'device', 'license_id', 'activation_id', 'jti', 'sequence', 'iat', 'nbf', 'exp', 'grace_until', 'features', 'limits'];
        $names = array_keys($claims);
        sort($required);
        sort($names);
        if ($names !== $required || $claims['v'] !== 1 || $claims['product'] !== 'KMJ_CODEBRIDGE') {
            throw new DomainException('CODEBRIDGE_INVALID_CLAIMS');
        }
        foreach (['tenant', 'device'] as $field) {
            if (!is_string($claims[$field]) || !preg_match('/\A[A-Za-z0-9_-]{1,64}\z/D', $claims[$field])) {
                throw new DomainException('CODEBRIDGE_INVALID_BINDING');
            }
        }
        foreach (['license_id', 'activation_id', 'jti'] as $field) {
            if (!is_string($claims[$field]) || trim($claims[$field]) === '' || strlen($claims[$field]) > 200) {
                throw new DomainException('CODEBRIDGE_INVALID_IDENTITY');
            }
        }
        foreach (['sequence', 'iat', 'nbf', 'exp', 'grace_until'] as $field) {
            if (!is_int($claims[$field]) || $claims[$field] < 0 || $claims[$field] > 9007199254740991) {
                throw new DomainException('CODEBRIDGE_INVALID_TIME');
            }
        }
        if ($claims['sequence'] < 1 || $claims['iat'] > $now || $claims['nbf'] > $now || $claims['exp'] <= $now || $claims['exp'] <= $claims['iat'] || $claims['exp'] - $claims['iat'] > 86400 || $claims['grace_until'] < $claims['exp'] || $claims['grace_until'] - $claims['exp'] > 172800) {
            throw new DomainException('CODEBRIDGE_INVALID_LEASE');
        }
        if (!is_array($claims['features']) || !array_is_list($claims['features'])) {
            throw new DomainException('CODEBRIDGE_INVALID_FEATURES');
        }
        foreach ($claims['features'] as $feature) {
            if (!in_array($feature, ['read', 'write', 'execute'], true)) {
                throw new DomainException('CODEBRIDGE_INVALID_FEATURES');
            }
        }
        if (!is_array($claims['limits']) || count($claims['limits']) !== 2 || !isset($claims['limits']['devices'], $claims['limits']['concurrent_jobs']) || !is_int($claims['limits']['devices']) || $claims['limits']['devices'] < 1 || $claims['limits']['devices'] > 9007199254740991 || !is_int($claims['limits']['concurrent_jobs']) || $claims['limits']['concurrent_jobs'] < 1 || $claims['limits']['concurrent_jobs'] > 16) {
            throw new DomainException('CODEBRIDGE_INVALID_LIMITS');
        }
        $kid = $signer->kid();
        if (!preg_match('/\A[A-Za-z0-9_-]{1,128}\z/D', $kid)) {
            throw new DomainException('CODEBRIDGE_INVALID_KEY');
        }
        $header = ['alg' => 'EdDSA', 'kid' => $kid, 'typ' => 'JWT'];
        $message = self::b64(json_encode($header, JSON_THROW_ON_ERROR)).'.'.self::b64(json_encode($claims, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES));
        $signature = $signer->sign($message);
        if (strlen($signature) !== 64) {
            throw new DomainException('CODEBRIDGE_INVALID_SIGNATURE');
        }

        return $message.'.'.self::b64($signature);
    }

    private static function b64(string $value): string
    {
        return rtrim(strtr(base64_encode($value), '+/', '-_'), '=');
    }
}
