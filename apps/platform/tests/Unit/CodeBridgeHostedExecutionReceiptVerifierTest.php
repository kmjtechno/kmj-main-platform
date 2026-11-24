<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Services\CodeBridge\HostedExecutionReceiptVerifier;
use PHPUnit\Framework\TestCase;

final class CodeBridgeHostedExecutionReceiptVerifierTest extends TestCase
{
    public function test_receipt_signature_binds_scope_request_and_outcome(): void
    {
        $verifier = new HostedExecutionReceiptVerifier;
        $expected = [
            'organization_id' => 'c5f71b5e-955b-4d85-a63e-60310777a52c',
            'subject_key' => 'seat:one',
            'execution_id' => '10004e25-8a92-4cf1-804c-3ed3f03b22cb',
            'device_id' => 'device-one',
            'project_id' => 'project-one',
            'request_sha256' => str_repeat('a', 64),
            'outcome' => 'succeeded',
        ];
        $pair = sodium_crypto_sign_keypair();
        $key = base64_encode(sodium_crypto_sign_publickey($pair));
        $message = $verifier->message($expected);
        self::assertIsString($message);
        $signature = base64_encode(sodium_crypto_sign_detached($message, sodium_crypto_sign_secretkey($pair)));
        self::assertTrue($verifier->verifyTrusted($expected, $signature, $key));

        foreach (['subject_key' => 'seat:two', 'device_id' => 'other', 'project_id' => 'other', 'outcome' => 'failed', 'request_sha256' => str_repeat('b', 64)] as $field => $replacement) {
            self::assertFalse($verifier->verifyTrusted([...$expected, $field => $replacement], $signature, $key));
        }

        $other = sodium_crypto_sign_keypair();
        self::assertFalse($verifier->verifyTrusted($expected, $signature, base64_encode(sodium_crypto_sign_publickey($other))));
        self::assertFalse($verifier->verifyTrusted($expected, 'invalid', $key));
        self::assertFalse($verifier->verifyTrusted([...$expected, 'extra' => 'x'], $signature, $key));
    }
}
