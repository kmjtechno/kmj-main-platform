<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Services\Licensing\OmniDesk\OmniDeskActivationProof;
use DomainException;
use Tests\TestCase;

final class OmniDeskActivationProofTest extends TestCase
{
    private const PUBLIC_KEY = '0EqyMnQrtKs6E2i9RhXk5tAiSrcaAWuvhSCjMsl3hzc';

    private const FINGERPRINT = 'sha256:10ba682c8ad13513971e8b56881aab8bd702bb807796eca81932c735a94d6e6d';

    private const SIGNATURE = 'rWbwyRQJupT44i7OcuSWqJnpQ0Ff6rXhZOw_OXSY_y8mAWnwpZq40uDIsHu1aUrvl461jvsuNJQqLhx9n4hYBg';

    /** @return array<string, string> */
    private function request(): array
    {
        return [
            'license_or_entitlement_reference' => 'entitlement-123',
            'device_public_key' => self::PUBLIC_KEY,
            'device_public_key_fingerprint' => self::FINGERPRINT,
            'installation_id' => 'install-12345678',
            'client_version' => '0.0.1',
            'protocol_version' => 'KSLP-v1',
            'platform' => 'windows',
            'architecture' => 'x86_64',
            'client_nonce' => 'nonce-0123456789abcdef',
            'proof_scheme' => 'KMJ-OMNIDESK-ACTIVATE-v1',
            'device_signature' => self::SIGNATURE,
        ];
    }

    public function test_rust_golden_vector_verifies_in_php(): void
    {
        $proof = app(OmniDeskActivationProof::class);
        $proof->verify($this->request(), 'idem-0123456789abcdef');

        self::assertTrue(true);
    }

    public function test_canonical_message_matches_rust_golden_vector(): void
    {
        $expected = 'S01KLU9NTklERVNLLUFDVElWQVRFLXYxAAAAFWlkZW0tMDEyMzQ1Njc4OWFiY2RlZgAAAA9lbnRpdGxlbWVudC0xMjMAAAArMEVxeU1uUXJ0S3M2RTJpOVJoWGs1dEFpU3JjYUFXdXZoU0NqTXNsM2h6YwAAAEdzaGEyNTY6MTBiYTY4MmM4YWQxMzUxMzk3MWU4YjU2ODgxYWFiOGJkNzAyYmI4MDc3OTZlY2E4MTkzMmM3MzVhOTRkNmU2ZAAAABBpbnN0YWxsLTEyMzQ1Njc4AAAABTAuMC4xAAAAB0tTTFAtdjEAAAAHd2luZG93cwAAAAZ4ODZfNjQAAAAWbm9uY2UtMDEyMzQ1Njc4OWFiY2RlZg';
        $message = app(OmniDeskActivationProof::class)
            ->canonicalMessage($this->request(), 'idem-0123456789abcdef');

        self::assertSame($expected, rtrim(strtr(base64_encode($message), '+/', '-_'), '='));
    }

    public function test_tampered_nonce_is_rejected(): void
    {
        $request = $this->request();
        $request['client_nonce'] = 'nonce-fedcba9876543210';

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_ACTIVATION_PROOF_INVALID');
        app(OmniDeskActivationProof::class)->verify($request, 'idem-0123456789abcdef');
    }

    public function test_fingerprint_mismatch_is_rejected(): void
    {
        $request = $this->request();
        $request['device_public_key_fingerprint'] = 'sha256:'.str_repeat('0', 64);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_ACTIVATION_PROOF_INVALID');
        app(OmniDeskActivationProof::class)->verify($request, 'idem-0123456789abcdef');
    }

    public function test_idempotency_key_is_part_of_the_signed_request(): void
    {
        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_ACTIVATION_PROOF_INVALID');
        app(OmniDeskActivationProof::class)->verify($this->request(), 'idem-fedcba9876543210');
    }
}
