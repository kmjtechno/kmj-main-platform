<?php

namespace Tests\Unit;

use App\Services\Licensing\LicenseValidator;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class LicenseValidatorIdentityClaimContractTest extends TestCase
{
    use RefreshDatabase;

    public function test_php_validator_rejects_whitespace_only_identity_claims(): void
    {
        $secret = str_repeat('k', 32);
        $validator = new LicenseValidator($secret);

        foreach (['jti', 'organization_id', 'product_id', 'entitlement_id'] as $claim) {
            $claims = [
                'environment' => 'sandbox',
                'jti' => 'license-1',
                'organization_id' => 'org-1',
                'product_id' => 'product-1',
                'entitlement_id' => 'entitlement-1',
                'issued_at' => time(),
                'expires_at' => time() + 1800,
            ];
            $claims[$claim] = " \t\n ";

            $validation = $validator->validate($this->sign($claims, $secret));

            self::assertFalse($validation['valid'], "{$claim} must not accept whitespace-only identity.");
            self::assertSame('missing_claims', $validation['reason']);
            self::assertNull($validation['claims']);
        }
    }

    public function test_php_validator_rejects_signed_scalar_json_payloads(): void
    {
        $secret = str_repeat('k', 32);
        $validator = new LicenseValidator($secret);

        foreach ([null, true, 42, 'sandbox'] as $payload) {
            $validation = $validator->validate($this->signJson($payload, $secret));

            self::assertFalse($validation['valid']);
            self::assertSame('invalid_payload', $validation['reason']);
            self::assertNull($validation['claims']);
        }
    }

    public function test_php_validator_rejects_signed_list_json_payloads(): void
    {
        $secret = str_repeat('k', 32);
        $validator = new LicenseValidator($secret);

        foreach ([[], ['sandbox'], ['environment', 'sandbox']] as $payload) {
            $validation = $validator->validate($this->signJson($payload, $secret));

            self::assertFalse($validation['valid']);
            self::assertSame('invalid_payload', $validation['reason']);
            self::assertNull($validation['claims']);
        }
    }

    /**
     * @param  array<string, mixed>  $claims
     */
    private function sign(array $claims, string $secret): string
    {
        return $this->signJson($claims, $secret);
    }

    private function signJson(mixed $payloadValue, string $secret): string
    {
        $payload = $this->base64UrlEncode(json_encode($payloadValue, JSON_THROW_ON_ERROR));
        $signature = hash_hmac('sha256', $payload, $secret, true);

        return $payload.'.'.$this->base64UrlEncode($signature);
    }

    private function base64UrlEncode(string $value): string
    {
        return rtrim(strtr(base64_encode($value), '+/', '-_'), '=');
    }
}
