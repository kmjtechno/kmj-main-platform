<?php

declare(strict_types=1);

namespace App\Services\CodeBridge;

use Illuminate\Support\Str;

/**
 * Source-only Ed25519 contract. Expected identifiers and public key MUST come
 * from a trusted server reservation and pinned device enrollment.
 * Never accept a client-supplied verification key. Not wired to settlement.
 */
final class HostedExecutionReceiptVerifier
{
    /** @param array<string, mixed> $expected */
    public function verifyTrusted(array $expected, string $signatureBase64, string $pinnedPublicKeyBase64): bool
    {
        $message = $this->message($expected);
        if ($message === null || strlen($signatureBase64) !== 88 || strlen($pinnedPublicKeyBase64) !== 44) {
            return false;
        }

        $signature = base64_decode($signatureBase64, true);
        $key = base64_decode($pinnedPublicKeyBase64, true);

        return is_string($signature)
            && strlen($signature) === SODIUM_CRYPTO_SIGN_BYTES
            && base64_encode($signature) === $signatureBase64
            && is_string($key)
            && strlen($key) === SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES
            && base64_encode($key) === $pinnedPublicKeyBase64
            && sodium_crypto_sign_verify_detached($signature, $message, $key);
    }

    /** @param array<string, mixed> $expected */
    public function message(array $expected): ?string
    {
        $keys = ['organization_id', 'subject_key', 'execution_id', 'device_id', 'project_id', 'request_sha256', 'outcome'];
        if (count($expected) !== count($keys)) {
            return null;
        }

        foreach ($keys as $key) {
            if (! is_string($expected[$key] ?? null)) {
                return null;
            }
        }

        if (! Str::isUuid($expected['organization_id'])
            || ! Str::isUuid($expected['execution_id'])
            || preg_match('/\\A[A-Za-z0-9:_-]{1,64}\\z/D', $expected['subject_key']) !== 1
            || preg_match('/\\A[A-Za-z0-9_-]{1,64}\\z/D', $expected['device_id']) !== 1
            || preg_match('/\\A[A-Za-z0-9_-]{1,64}\\z/D', $expected['project_id']) !== 1
            || preg_match('/\\A[a-f0-9]{64}\\z/D', $expected['request_sha256']) !== 1
            || ! in_array($expected['outcome'], ['succeeded', 'failed'], true)) {
            return null;
        }

        return "KMJ_CODEBRIDGE_HOSTED_RECEIPT_V1\n".implode("\n", array_map(fn (string $key): string => $expected[$key], $keys))."\n";
    }
}
