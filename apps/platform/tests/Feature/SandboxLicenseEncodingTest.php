<?php

namespace Tests\Feature;

use App\Services\Licensing\LicenseValidator;
use App\Services\Licensing\SandboxLicenseIssuer;
use DateTimeImmutable;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class SandboxLicenseEncodingTest extends TestCase
{
    use RefreshDatabase;

    private const SECRET = 'sandbox-encoding-regression-secret-32-bytes';

    public function test_canonical_issuer_token_still_validates(): void
    {
        $token = (new SandboxLicenseIssuer(self::SECRET))->issue(
            'org-1', 'product-1', 'entitlement-1', new DateTimeImmutable('+5 minutes'),
        );

        $result = (new LicenseValidator(self::SECRET))->validate($token);

        self::assertTrue($result['valid']);
        self::assertSame('sandbox', $result['claims']['environment']);
    }

    public function test_oversized_untrusted_token_is_rejected_before_processing(): void
    {
        $token = str_repeat('a', 16_385);

        $result = (new LicenseValidator(self::SECRET))->validate($token);

        self::assertFalse($result['valid']);
        self::assertSame('malformed', $result['reason']);
        self::assertNull($result['claims']);
    }

    public function test_noncanonical_signature_trailing_bits_are_rejected(): void
    {
        $token = (new SandboxLicenseIssuer(self::SECRET))->issue(
            'org-1', 'product-1', 'entitlement-1', new DateTimeImmutable('+5 minutes'),
        );
        [$payload, $signature] = explode('.', $token);
        $alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
        $lastIndex = strpos($alphabet, $signature[strlen($signature) - 1]);
        self::assertNotFalse($lastIndex);
        // 32-byte SHA-256 signatures occupy 43 base64url characters; two
        // low trailing bits are unused. Alter them without changing decoded bytes.
        self::assertSame(0, $lastIndex % 4);
        $alternative = substr($signature, 0, -1).$alphabet[$lastIndex + 1];

        $result = (new LicenseValidator(self::SECRET))->validate($payload.'.'.$alternative);

        self::assertFalse($result['valid']);
        self::assertSame('malformed_signature', $result['reason']);
    }

    public function test_signed_noncanonical_payload_padding_is_rejected(): void
    {
        $token = (new SandboxLicenseIssuer(self::SECRET))->issue(
            'org-1', 'product-1', 'entitlement-1', new DateTimeImmutable('+5 minutes'),
        );
        [$payload] = explode('.', $token);
        $paddedPayload = $payload.str_repeat('=', (4 - strlen($payload) % 4) % 4);
        // Force a noncanonical wire form even if this fixture is already
        // divisible by four, and sign it with the *test-only* secret.
        if ($paddedPayload === $payload) {
            $paddedPayload .= '=';
        }
        $signature = hash_hmac('sha256', $paddedPayload, self::SECRET, true);
        $encodedSignature = rtrim(strtr(base64_encode($signature), '+/', '-_'), '=');

        $result = (new LicenseValidator(self::SECRET))
            ->validate($paddedPayload.'.'.$encodedSignature);

        self::assertFalse($result['valid']);
        self::assertSame('malformed_payload', $result['reason']);
    }

    public function test_non_url_safe_signature_characters_are_rejected(): void
    {
        $token = (new SandboxLicenseIssuer(self::SECRET))->issue(
            'org-1', 'product-1', 'entitlement-1', new DateTimeImmutable('+5 minutes'),
        );
        [$payload, $signature] = explode('.', $token);

        foreach ([$signature.'=', $signature."\n", $signature.'+'] as $badSignature) {
            $result = (new LicenseValidator(self::SECRET))
                ->validate($payload.'.'.$badSignature);
            self::assertFalse($result['valid']);
            self::assertSame('malformed_signature', $result['reason']);
        }
    }
}
