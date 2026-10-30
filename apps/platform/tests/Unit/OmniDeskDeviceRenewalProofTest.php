<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Services\Licensing\OmniDeskDeviceRenewalProof;
use DomainException;
use PHPUnit\Framework\TestCase;

final class OmniDeskDeviceRenewalProofTest extends TestCase
{
    /** @return array<string, mixed> */
    private function vector(): array
    {
        return json_decode(
            (string) file_get_contents(__DIR__.'/../Fixtures/OmniDesk/renewal-proof-v1.json'),
            true,
            512,
            JSON_THROW_ON_ERROR,
        );
    }

    /** @return array<string, mixed> */
    private function request(): array
    {
        $vector = $this->vector();

        return [
            'activation_id' => $vector['activation_id'],
            'current_jti' => $vector['current_jti'],
            'current_sequence' => $vector['current_sequence'],
            'server_challenge' => $vector['server_challenge'],
            'client_nonce' => $vector['client_nonce'],
            'client_version' => $vector['client_version'],
            'proof_scheme' => $vector['proof_scheme'],
            'device_signature' => $vector['signature_base64url'],
        ];
    }

    private function key(): string
    {
        $encoded = (string) $this->vector()['public_key_base64url'];

        return (string) base64_decode(strtr($encoded, '-_', '+/').'=', true);
    }

    public function test_rust_renewal_vector_matches_php_canonical_message_and_ed25519_verification(): void
    {
        $vector = $this->vector();
        $proof = new OmniDeskDeviceRenewalProof;
        $message = $proof->canonicalMessage($this->request());
        self::assertSame(
            $vector['canonical_message_base64url'],
            rtrim(strtr(base64_encode($message), '+/', '-_'), '='),
        );
        $proof->verify($this->request(), $this->key());
        self::assertTrue(true);
    }

    public function test_signed_sequence_jti_challenge_nonce_and_other_fields_cannot_be_changed(): void
    {
        $proof = new OmniDeskDeviceRenewalProof;
        foreach ([
            'activation_id',
            'current_jti',
            'current_sequence',
            'server_challenge',
            'client_nonce',
            'client_version',
        ] as $field) {
            $request = $this->request();
            $request[$field] = $field === 'current_sequence' ? 8 : $request[$field].'-changed';
            try {
                $proof->verify($request, $this->key());
                self::fail('Changed '.$field.' accepted old device signature');
            } catch (DomainException $exception) {
                self::assertSame('FORBIDDEN', $exception->getMessage(), $field);
            }
        }
    }

    public function test_wrong_trusted_device_key_cannot_renew(): void
    {
        $proof = new OmniDeskDeviceRenewalProof;
        $this->expectExceptionMessage('FORBIDDEN');
        $proof->verify($this->request(), str_repeat('x', SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES));
    }

    public function test_invalid_request_shape_and_signature_are_rejected(): void
    {
        $proof = new OmniDeskDeviceRenewalProof;
        $base = $this->request();
        foreach ([
            [...$base, 'unknown_claim' => 'ignored'],
            array_diff_key($base, ['activation_id' => true]),
            [...$base, 'proof_scheme' => 'KMJ-OMNIDESK-ACTIVATE-v1'],
            [...$base, 'current_sequence' => 0],
            [...$base, 'current_sequence' => '7'],
            [...$base, 'client_nonce' => 'short'],
            [...$base, 'server_challenge' => "nonce\0invalid"],
            [...$base, 'client_version' => "\xff"],
            [...$base, 'activation_id' => ['array']],
            [...$base, 'device_signature' => $base['device_signature'].'='],
        ] as $index => $request) {
            try {
                $proof->verify($request, $this->key());
                self::fail('Malformed request '.$index.' accepted.');
            } catch (DomainException $exception) {
                self::assertSame('INVALID_REQUEST', $exception->getMessage(), (string) $index);
            }
        }
    }

    public function test_invalid_signature_and_key_length_fail_closed(): void
    {
        $proof = new OmniDeskDeviceRenewalProof;
        try {
            $proof->verify($this->request(), 'not-a-key');
            self::fail('Invalid trusted device public key accepted.');
        } catch (DomainException $exception) {
            self::assertSame('INVALID_REQUEST', $exception->getMessage());
        }

        $request = $this->request();
        $request['device_signature'][0] = $request['device_signature'][0] === 'A' ? 'B' : 'A';
        $this->expectExceptionMessage('FORBIDDEN');
        $proof->verify($request, $this->key());
    }
}
