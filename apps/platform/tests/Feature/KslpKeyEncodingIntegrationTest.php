<?php

namespace Tests\Feature;

use App\Services\Licensing\Kslp\KslpCodec;
use App\Services\Licensing\Kslp\KslpKeyRegistry;
use App\Services\Licensing\Kslp\KslpVerifier;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class KslpKeyEncodingIntegrationTest extends TestCase
{
    use RefreshDatabase;

    public function test_signed_lease_can_be_verified_with_only_the_public_key_registry(): void
    {
        $pair = sodium_crypto_sign_keypair();
        $secret = sodium_crypto_sign_secretkey($pair);
        $rawPublic = sodium_crypto_sign_publickey($pair);
        $public = rtrim(strtr(base64_encode($rawPublic), '+/', '-_'), '=');

        $registry = app(KslpKeyRegistry::class);
        $registry->publish('test-lease-key', 'license', $public);
        $now = time();

        $claims = [
            'protocol_version' => 'KSLP-v1', 'license_id' => 'lic-1',
            'customer_id' => 'customer-1', 'product' => 'KMJ_CLOUDOS',
            'plan' => 'business', 'server_identity' => 'server-1',
            'activation_id' => 'activation-1', 'features' => ['hosting' => true],
            'limits' => ['nodes' => 2], 'iat' => $now,
            'nbf' => $now - 5, 'exp' => $now + 60, 'sequence' => 1,
            'nonce' => 'sample-nonce', 'kid' => 'test-lease-key',
            'jti' => 'test-jti', 'aud' => 'kmj-cloudos',
        ];
        $token = KslpCodec::encode(
            $claims,
            'test-lease-key',
            fn (string $message): string => sodium_crypto_sign_detached($message, $secret)
        );

        $decoded = app(KslpVerifier::class)->verify(
            $token, fn (string $kid): string => $registry->publicKey($kid, 'license'),
            'server-1', $now
        );
        self::assertSame('activation-1', $decoded['activation_id']);
        self::assertSame(2, $decoded['limits']['nodes']);

        $registry->revoke('test-lease-key');
        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('KSLP_UNKNOWN_KID');
        app(KslpVerifier::class)->verify(
            $token, fn (string $kid): string => $registry->publicKey($kid, 'license'),
            'server-1', $now
        );
    }
}
