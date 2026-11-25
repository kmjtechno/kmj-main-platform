<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Services\CodeBridge\HostedSeatProofVerifier;
use App\Services\Licensing\Kslp\KslpCodec;
use PHPUnit\Framework\TestCase;

final class CodeBridgeHostedSeatProofVerifierTest extends TestCase
{
    public function test_signed_seat_proof_requires_exact_current_assignment_and_trusted_key(): void
    {
        $now = 1795584000;
        $expected = [
            'organization_id' => '12345678-1234-4234-8234-123456789001',
            'membership_id' => '12345678-1234-4234-8234-123456789002',
            'user_id' => '42',
            'license_id' => '12345678-1234-4234-8234-123456789003',
            'seat_id' => '12345678-1234-4234-8234-123456789004',
            'assignment_revision' => 1,
        ];
        $claims = [
            ...$expected,
            'protocol_version' => 'KSLP-seat-v1',
            'aud' => 'kmj-codebridge-hosted-seat',
            'product' => 'KMJ_CODEBRIDGE',
            'plan' => 'team',
            'iat' => $now,
            'nbf' => $now,
            'exp' => $now + 300,
        ];
        $pair = sodium_crypto_sign_keypair();
        $key = base64_encode(sodium_crypto_sign_publickey($pair));
        $sign = static fn (string $message): string => sodium_crypto_sign_detached($message, sodium_crypto_sign_secretkey($pair));
        $token = KslpCodec::encode($claims, 'seat-test', $sign);
        $verifier = new HostedSeatProofVerifier;

        self::assertTrue($verifier->verifyTrusted($token, $expected, 'seat-test', $key, $now));
        self::assertFalse($verifier->verifyTrusted($token, $expected, 'seat-test', $key, $now + 300));
        self::assertFalse($verifier->verifyTrusted($token, $expected, 'other-kid', $key, $now));
        self::assertFalse($verifier->verifyTrusted($token, $expected, 'seat-test', base64_encode(sodium_crypto_sign_publickey(sodium_crypto_sign_keypair())), $now));

        foreach ([
            ['organization_id' => '12345678-1234-4234-8234-123456789099'],
            ['membership_id' => '12345678-1234-4234-8234-123456789099'],
            ['user_id' => '43'],
            ['license_id' => '12345678-1234-4234-8234-123456789099'],
            ['seat_id' => '12345678-1234-4234-8234-123456789099'],
            ['assignment_revision' => 2],
        ] as $change) {
            self::assertFalse($verifier->verifyTrusted($token, [...$expected, ...$change], 'seat-test', $key, $now));
        }

        foreach ([
            ['aud' => 'kmj-cloudos'],
            ['product' => 'KMJ_OMNIDESK'],
            ['plan' => 'pro'],
            ['exp' => $now + 301],
            ['nbf' => $now + 1],
            ['iat' => $now + 1],
            ['user_id' => 42],
            ['assignment_revision' => '1'],
            ['extra' => 'device_allowance'],
        ] as $change) {
            $invalid = KslpCodec::encode([...$claims, ...$change], 'seat-test', $sign);
            self::assertFalse($verifier->verifyTrusted($invalid, $expected, 'seat-test', $key, $now));
        }
        self::assertFalse($verifier->verifyTrusted('malformed', $expected, 'seat-test', $key, $now));
    }
}
