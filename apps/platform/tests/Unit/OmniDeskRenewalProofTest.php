<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Services\Licensing\OmniDesk\OmniDeskRenewalProof;
use DomainException;
use Tests\TestCase;

final class OmniDeskRenewalProofTest extends TestCase
{
    /** @return array<string, int|string> */
    private function request(): array
    {
        return [
            'activation_id' => 'activation-12345678',
            'current_jti' => 'jti-0123456789abcdef',
            'current_sequence' => 7,
            'server_challenge' => 'challenge-0123456789abcdef',
            'client_nonce' => 'nonce-fedcba9876543210',
            'client_version' => '0.0.1',
            'proof_scheme' => 'KMJ-OMNIDESK-RENEW-v1',
            'device_signature' => 'wlnKmf7B4cEBJbctnucygV9z-bz1Is5psWXdVgP5GgE0J6IvjzucJv-2mphxh7ztYj6JuO1N03_HLET1jLt_BQ',
        ];
    }

    public function test_rust_vector_canonical_message_and_signature_match_exactly(): void
    {
        $proof = app(OmniDeskRenewalProof::class);
        $request = $this->request();

        self::assertSame(
            'S01KLU9NTklERVNLLVJFTkVXLXYxAAAAE2FjdGl2YXRpb24tMTIzNDU2NzgAAAAUanRpLTAxMjM0NTY3ODlhYmNkZWYAAAABNwAAABpjaGFsbGVuZ2UtMDEyMzQ1Njc4OWFiY2RlZgAAABZub25jZS1mZWRjYmE5ODc2NTQzMjEwAAAABTAuMC4x',
            $this->base64UrlEncode($proof->canonicalMessage($request)),
        );

        $proof->verify(
            $request,
            'IIKL9cW9ystoSGMzbCAvtVmdpIvlWWYVdCFwcFvsqfc',
        );

        self::assertTrue(true);
    }

    public function test_changed_challenge_fails_closed(): void
    {
        $request = $this->request();
        $request['server_challenge'] = 'challenge-fedcba9876543210';

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_RENEWAL_PROOF_INVALID');

        app(OmniDeskRenewalProof::class)->verify(
            $request,
            'IIKL9cW9ystoSGMzbCAvtVmdpIvlWWYVdCFwcFvsqfc',
        );
    }

    public function test_changed_sequence_jti_and_proof_scheme_fail_closed(): void
    {
        foreach ([
            ['current_sequence', 8],
            ['current_jti', 'jti-fedcba9876543210'],
            ['proof_scheme', 'KMJ-OMNIDESK-ACTIVATE-v1'],
        ] as [$field, $value]) {
            $request = $this->request();
            $request[$field] = $value;

            try {
                app(OmniDeskRenewalProof::class)->verify(
                    $request,
                    'IIKL9cW9ystoSGMzbCAvtVmdpIvlWWYVdCFwcFvsqfc',
                );
                self::fail("Mutated {$field} must be rejected.");
            } catch (DomainException $exception) {
                self::assertSame('OMNIDESK_RENEWAL_PROOF_INVALID', $exception->getMessage());
            }
        }
    }

    public function test_malformed_public_key_or_signature_is_rejected(): void
    {
        $request = $this->request();

        try {
            app(OmniDeskRenewalProof::class)->verify($request, 'not-a-valid-ed25519-key');
            self::fail('Malformed public key must be rejected.');
        } catch (DomainException $exception) {
            self::assertSame('OMNIDESK_RENEWAL_PROOF_INVALID', $exception->getMessage());
        }

        $request['device_signature'] = 'short';

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_RENEWAL_PROOF_INVALID');

        app(OmniDeskRenewalProof::class)->verify(
            $request,
            'IIKL9cW9ystoSGMzbCAvtVmdpIvlWWYVdCFwcFvsqfc',
        );
    }

    private function base64UrlEncode(string $value): string
    {
        return rtrim(strtr(base64_encode($value), '+/', '-_'), '=');
    }
}
