<?php

declare(strict_types=1);

namespace Tests\Unit\Kslp;

use App\Services\Licensing\Kslp\KslpCodec;
use App\Services\Licensing\Kslp\KslpVerifier;
use DomainException;
use PHPUnit\Framework\TestCase;

final class KslpStrictVerifierTest extends TestCase
{
    private const NOW = 1800000000;

    /** @return array<string,mixed> */
    private function claims(): array
    {
        return [
            'protocol_version' => 'KSLP-v1',
            'license_id' => 'license-test',
            'customer_id' => 'customer-test',
            'product' => 'KMJ_CLOUDOS',
            'plan' => 'professional',
            'server_identity' => 'ed25519:valid-unique-test-device',
            'activation_id' => 'activation-test',
            'features' => ['hosting' => true],
            'limits' => ['nodes' => 2],
            'iat' => self::NOW,
            'nbf' => self::NOW - 5,
            'exp' => self::NOW + 3600,
            'sequence' => 5,
            'nonce' => 'signed-nonce',
            'kid' => 'test-signing-kid',
            'jti' => 'test-jti',
            'aud' => 'kmj-cloudos',
            'grace_until' => self::NOW + 7200,
        ];
    }

    /**
     * A fresh **test-only** signing key is never used for production licensing.
     * @param array<string,mixed> $claims
     * @return array{string,string}
     */
    private function signed(array $claims): array
    {
        $pair = sodium_crypto_sign_keypair();
        $secret = sodium_crypto_sign_secretkey($pair);
        $public = sodium_crypto_sign_publickey($pair);

        return [
            KslpCodec::encode(
                $claims,
                'test-signing-kid',
                fn (string $message): string => sodium_crypto_sign_detached($message, $secret),
            ),
            $public,
        ];
    }

    /** @param array<string,mixed> $overrides */
    private function check(array $overrides = []): array
    {
        [$token, $pk] = $this->signed(array_replace($this->claims(), $overrides));

        return (new KslpVerifier)->verify(
            $token,
            fn (string $kid): ?string => $kid === 'test-signing-kid' ? $pk : null,
            'ed25519:valid-unique-test-device',
            self::NOW,
        );
    }

    public function test_valid_signed_v1_claims_are_unchanged(): void
    {
        self::assertSame($this->claims(), $this->check());
    }

    public function test_signed_unknown_v1_field_is_rejected_not_silently_accepted(): void
    {
        $this->expectExceptionMessage('KSLP_MALFORMED');
        $this->check(['paid_entitlement_override' => true]);
    }

    public function test_signed_missing_required_field_is_rejected(): void
    {
        $claims = $this->claims();
        unset($claims['activation_id']);
        [$token, $pk] = $this->signed($claims);
        $this->expectExceptionMessage('KSLP_MALFORMED');
        (new KslpVerifier)->verify(
            $token,
            fn (string $kid): ?string => $pk,
            'ed25519:valid-unique-test-device',
            self::NOW,
        );
    }

    public function test_signed_string_expiry_cannot_be_cast_to_integer(): void
    {
        $this->expectExceptionMessage('KSLP_MALFORMED');
        $this->check(['exp' => (string) (self::NOW + 3600)]);
    }

    public function test_signed_float_and_boolean_time_are_rejected(): void
    {
        foreach (['nbf' => (float) (self::NOW - 5), 'iat' => true] as $field => $invalid) {
            try {
                $this->check([$field => $invalid]);
                self::fail('Invalid time field was treated as integer: '.$field);
            } catch (DomainException $exception) {
                self::assertSame('KSLP_MALFORMED', $exception->getMessage());
            }
        }
    }

    public function test_signed_zero_sequence_is_rejected(): void
    {
        $this->expectExceptionMessage('KSLP_MALFORMED');
        $this->check(['sequence' => 0]);
    }

    public function test_signed_wrong_audience_never_authorizes_cloudos(): void
    {
        $this->expectExceptionMessage('KSLP_WRONG_AUDIENCE');
        $this->check(['aud' => 'kmj-omnidesk']);
    }

    public function test_signed_wrong_product_is_rejected(): void
    {
        $this->expectExceptionMessage('KSLP_WRONG_PRODUCT');
        $this->check(['product' => 'KMJ_OMNIDESK']);
    }

    public function test_signed_kid_header_claim_mismatch_is_rejected(): void
    {
        $this->expectExceptionMessage('KSLP_MALFORMED');
        $this->check(['kid' => 'other-signing-kid']);
    }

    public function test_64_byte_ed25519_signature_is_mandatory(): void
    {
        [$token, $pk] = $this->signed($this->claims());
        $parts = explode('.', $token);
        $parts[2] = rtrim(strtr(base64_encode(str_repeat('x', 8)), '+/', '-_'), '=');
        $this->expectExceptionMessage('KSLP_MALFORMED');
        (new KslpVerifier)->verify(
            implode('.', $parts),
            fn (string $kid): ?string => $pk,
            'ed25519:valid-unique-test-device',
            self::NOW,
        );
    }

    public function test_tampered_claims_are_rejected_before_entitlement_processing(): void
    {
        [$token, $pk] = $this->signed($this->claims());
        $parts = explode('.', $token);
        $claims = $this->claims();
        $claims['plan'] = 'enterprise';
        $parts[1] = rtrim(strtr(base64_encode(KslpCodec::canonical($claims)), '+/', '-_'), '=');
        $this->expectExceptionMessage('KSLP_INVALID_SIGNATURE');
        (new KslpVerifier)->verify(
            implode('.', $parts),
            fn (string $kid): ?string => $pk,
            'ed25519:valid-unique-test-device',
            self::NOW,
        );
    }

    public function test_noncanonical_base64url_aliases_are_rejected(): void
    {
        [$token] = $this->signed($this->claims());
        $parts = explode('.', $token);
        foreach ([
            $parts[0].'='.$parts[1].'.'.$parts[2],
            $parts[0].'.'.$parts[1].'.'.$parts[2].'=',
            '+'.$parts[0].'.'.$parts[1].'.'.$parts[2],
        ] as $badToken) {
            try {
                KslpCodec::decode($badToken);
                self::fail('Noncanonical token spelling was accepted.');
            } catch (DomainException $exception) {
                self::assertSame('KSLP_MALFORMED', $exception->getMessage());
            }
        }
    }

    public function test_oversized_token_is_rejected_before_key_lookup(): void
    {
        $calls = 0;
        $this->expectExceptionMessage('KSLP_MALFORMED');
        try {
            (new KslpVerifier)->verify(
                str_repeat('A', 16385),
                function (string $kid) use (&$calls): ?string {
                    $calls++;

                    return null;
                },
                'ed25519:valid-unique-test-device',
                self::NOW,
            );
        } finally {
            self::assertSame(0, $calls);
        }
    }
}
