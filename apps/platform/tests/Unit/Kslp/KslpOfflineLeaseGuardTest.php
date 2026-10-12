<?php

declare(strict_types=1);

namespace Tests\Unit\Kslp;

use App\Services\Licensing\Kslp\KslpCodec;
use App\Services\Licensing\Kslp\KslpOfflineLeaseGuard;
use PHPUnit\Framework\TestCase;

final class KslpOfflineLeaseGuardTest extends TestCase
{
    private const NOW = 1800000000;

    /** @return array<string, mixed> */
    private function claims(): array
    {
        return [
            'protocol_version' => 'KSLP-v1',
            'license_id' => 'license-1',
            'customer_id' => 'customer-1',
            'product' => 'KMJ_CLOUDOS',
            'plan' => 'professional',
            'server_identity' => 'ed25519:example-device-public-key',
            'activation_id' => 'activation-1',
            'features' => ['hosting' => true],
            'limits' => ['nodes' => 1],
            'iat' => self::NOW,
            'nbf' => self::NOW - 5,
            'exp' => self::NOW + 3600,
            'sequence' => 3,
            'nonce' => 'nonce-1',
            'kid' => 'license-key-1',
            'jti' => 'issued-token-1',
            'aud' => 'kmj-cloudos',
            'grace_until' => self::NOW + 7200,
        ];
    }

    /**
     * @param  array<string, mixed>  $overrides
     * @return array{string, string}
     */
    private function signed(array $overrides = []): array
    {
        $pair = sodium_crypto_sign_keypair();
        $secret = sodium_crypto_sign_secretkey($pair);
        $public = sodium_crypto_sign_publickey($pair);
        $token = KslpCodec::encode(array_replace($this->claims(), $overrides), 'license-key-1', fn (string $message): string => sodium_crypto_sign_detached($message, $secret));

        return [$token, $public];
    }

    /** @param array<string, mixed> $overrides */
    private function check(array $overrides = [], ?int $now = null, int $lastTrustedTime = self::NOW, int $minimumSequence = 3, bool $revoked = false, string $activation = 'activation-1'): array
    {
        [$token, $public] = $this->signed($overrides);

        return (new KslpOfflineLeaseGuard)->verify(
            $token,
            fn (string $kid): ?string => $kid === 'license-key-1' ? $public : null,
            'ed25519:example-device-public-key',
            $activation,
            'license-1',
            $now ?? self::NOW,
            $lastTrustedTime,
            $minimumSequence,
            $revoked,
        );
    }

    public function test_accepts_pinned_signature_with_matching_license_activation_and_policy(): void
    {
        self::assertSame(3, $this->check()['sequence']);
        self::assertSame(86400, KslpOfflineLeaseGuard::MAX_OFFLINE_SECONDS);
    }

    public function test_rejects_stale_sequence(): void
    {
        $this->expectExceptionMessage('KSLP_REPLAY');
        $this->check(minimumSequence: 4);
    }

    public function test_rejects_device_activation_mismatch(): void
    {
        $this->expectExceptionMessage('KSLP_ACTIVATION_CONFLICT');
        $this->check(activation: 'other-activation');
    }

    public function test_rejects_clock_rollback(): void
    {
        $this->expectExceptionMessage('KSLP_CLOCK_ROLLBACK');
        $this->check(lastTrustedTime: self::NOW + 30);
    }

    public function test_rejects_known_revocation_even_during_grace(): void
    {
        $this->expectExceptionMessage('KSLP_REVOKED');
        $this->check(revoked: true);
    }

    public function test_rejects_token_with_excessive_signed_offline_window(): void
    {
        $this->expectExceptionMessage('KSLP_EXPIRED');
        $this->check(['exp' => self::NOW + 86401, 'grace_until' => self::NOW + 90000]);
    }

    public function test_rejects_token_beyond_signed_commercial_grace(): void
    {
        $this->expectExceptionMessage('KSLP_EXPIRED');
        $this->check(['exp' => self::NOW + 3600, 'grace_until' => self::NOW + 1800]);
    }

    public function test_rejects_future_issued_token(): void
    {
        $this->expectExceptionMessage('KSLP_EXPIRED');
        $this->check(['iat' => self::NOW + 100, 'nbf' => self::NOW - 5]);
    }

    public function test_rejects_non_integer_expiry_even_if_signed(): void
    {
        $this->expectExceptionMessage('KSLP_MALFORMED');
        $this->check(['exp' => (string) (self::NOW + 3600)]);
    }

    public function test_rejects_forged_signature_and_untrusted_verification_key(): void
    {
        [$token] = $this->signed();
        $otherPublic = sodium_crypto_sign_publickey(sodium_crypto_sign_keypair());
        $this->expectExceptionMessage('KSLP_INVALID_SIGNATURE');
        (new KslpOfflineLeaseGuard)->verify(
            $token,
            fn (string $kid): ?string => $otherPublic,
            'ed25519:example-device-public-key',
            'activation-1',
            'license-1',
            self::NOW,
            self::NOW,
            3,
        );
    }

    public function test_rejects_uninitialized_trusted_time(): void
    {
        $this->expectExceptionMessage('KSLP_MALFORMED');
        $this->check(lastTrustedTime: 0);
    }

    public function test_existing_cloudos_golden_vector_remains_offline_compatible(): void
    {
        $fixture = json_decode(
            (string) file_get_contents(__DIR__.'/../../../../../contracts/kslp-v1/golden-vector-001.json'),
            true,
            512,
            JSON_THROW_ON_ERROR,
        );
        $publicKey = base64_decode($fixture['public_key_b64'], true);

        $claims = (new KslpOfflineLeaseGuard)->verify(
            $fixture['token'],
            fn (string $kid): ?string => $kid === 'golden-v1' ? $publicKey : null,
            $fixture['server_identity'],
            $fixture['expected_claims']['activation_id'],
            $fixture['expected_claims']['license_id'],
            $fixture['now'],
            $fixture['now'],
            $fixture['expected_claims']['sequence'],
        );

        self::assertSame($fixture['expected_claims'], $claims);
    }

    public function test_rejects_wrong_product_claim(): void
    {
        $this->expectExceptionMessage('KSLP_WRONG_PRODUCT');
        $this->check(['product' => 'KMJ_OMNIDESK']);
    }

    public function test_rejects_wrong_signed_audience(): void
    {
        $this->expectExceptionMessage('KSLP_WRONG_AUDIENCE');
        $this->check(['aud' => 'kmj-omnidesk']);
    }

    public function test_rejects_cross_license_activation_binding(): void
    {
        $this->expectExceptionMessage('KSLP_ACTIVATION_CONFLICT');
        $this->check(['license_id' => 'different-license']);
    }

    public function test_rejects_expired_signed_lease(): void
    {
        $this->expectExceptionMessage('KSLP_EXPIRED');
        $this->check(['exp' => self::NOW - 1]);
    }

    public function test_rejects_unknown_license_signing_key(): void
    {
        [$token] = $this->signed();
        $this->expectExceptionMessage('KSLP_UNKNOWN_KID');
        (new KslpOfflineLeaseGuard)->verify(
            $token,
            fn (string $kid): ?string => null,
            'ed25519:example-device-public-key',
            'activation-1',
            'license-1',
            self::NOW,
            self::NOW,
            3,
        );
    }

    public function test_rejects_oversized_unsigned_token_without_parsing(): void
    {
        $this->expectExceptionMessage('KSLP_MALFORMED');
        (new KslpOfflineLeaseGuard)->verify(
            str_repeat('X', 16385),
            fn (string $kid): ?string => null,
            'ed25519:example-device-public-key',
            'activation-1',
            'license-1',
            self::NOW,
            self::NOW,
            3,
        );
    }

    public function test_rejects_signed_invalid_entitlement_shape(): void
    {
        $this->expectExceptionMessage('KSLP_MALFORMED');
        $this->check(['features' => 'not-a-feature-map']);
    }

    public function test_rejects_unknown_signed_v1_extension(): void
    {
        $this->expectExceptionMessage('KSLP_MALFORMED');
        $this->check(['future_unapproved_entitlement' => true]);
    }
}
