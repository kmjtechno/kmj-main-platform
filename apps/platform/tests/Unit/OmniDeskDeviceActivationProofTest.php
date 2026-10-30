<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Services\Licensing\OmniDeskDeviceActivationProof;
use DomainException;
use PHPUnit\Framework\TestCase;

final class OmniDeskDeviceActivationProofTest extends TestCase
{
    /** @return array<string, mixed> */
    private function vector(): array
    {
        return json_decode(
            (string) file_get_contents(__DIR__.'/../Fixtures/OmniDesk/activation-proof-v1.json'),
            true,
            512,
            JSON_THROW_ON_ERROR,
        );
    }

    /** @return array<string, mixed> */
    private function validRequest(): array
    {
        $vector = $this->vector();

        return [
            ...$vector['request'],
            'device_public_key' => $vector['device_public_key'],
            'device_public_key_fingerprint' => $vector['device_public_key_fingerprint'],
            'proof_scheme' => $vector['proof_scheme'],
            'device_signature' => $vector['device_signature'],
        ];
    }

    public function test_rust_golden_vector_canonical_message_and_signature_are_accepted(): void
    {
        $vector = $this->vector();
        $verifier = new OmniDeskDeviceActivationProof;
        $request = $this->validRequest();

        $message = $verifier->canonicalMessage($request);
        self::assertSame(
            $vector['canonical_message_base64url'],
            rtrim(strtr(base64_encode($message), '+/', '-_'), '='),
        );
        self::assertSame('KMJ-OMNIDESK-ACTIVATE-v1', substr($message, 0, 24));

        // The signature was produced by the public OmniDesk Rust test vector,
        // NOT by the PHP issuer and not by a production signing key.
        $verifier->verify($request);
        self::assertTrue(true);
    }

    public function test_every_signed_request_field_is_cryptographically_bound(): void
    {
        $proof = new OmniDeskDeviceActivationProof;
        foreach ([
            'idempotency_key',
            'license_or_entitlement_reference',
            'installation_id',
            'client_version',
            'platform',
            'architecture',
            'client_nonce',
        ] as $field) {
            $request = $this->validRequest();
            $request[$field] .= '-changed';
            try {
                $proof->verify($request);
                self::fail('Tampering with '.$field.' must fail signature verification.');
            } catch (DomainException $exception) {
                self::assertSame('FORBIDDEN', $exception->getMessage(), $field);
            }
        }
    }

    public function test_wrong_device_fingerprint_and_forged_signature_fail_closed(): void
    {
        $proof = new OmniDeskDeviceActivationProof;
        $request = $this->validRequest();
        $request['device_public_key_fingerprint'] = 'sha256:'.str_repeat('0', 64);

        try {
            $proof->verify($request);
            self::fail('Device fingerprint mismatch cannot activate.');
        } catch (DomainException $exception) {
            self::assertSame('FORBIDDEN', $exception->getMessage());
        }

        $request = $this->validRequest();
        $request['device_signature'][0] = $request['device_signature'][0] === 'A' ? 'B' : 'A';
        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('FORBIDDEN');
        $proof->verify($request);
    }

    public function test_malformed_or_ambiguous_payloads_are_refused(): void
    {
        $proof = new OmniDeskDeviceActivationProof;
        $base = $this->validRequest();
        foreach ([
            [...$base, 'unexpected' => 'ignored'],
            array_diff_key($base, ['client_nonce' => true]),
            [...$base, 'device_public_key' => 'AQID'],
            [...$base, 'device_signature' => $base['device_signature'].'='],
            [...$base, 'protocol_version' => 'KSLP-v2'],
            [...$base, 'proof_scheme' => 'KSLP-ACTIVATE-v1'],
            [...$base, 'client_nonce' => 'short'],
            [...$base, 'installation_id' => ['wrong-type']],
            [...$base, 'architecture' => str_repeat('x', 513)],
            [...$base, 'platform' => "windows\0evil"],
            [...$base, 'client_version' => "\xff"],
        ] as $index => $request) {
            try {
                $proof->verify($request);
                self::fail('Malformed activation proof '.$index.' was accepted.');
            } catch (DomainException $exception) {
                self::assertSame('INVALID_REQUEST', $exception->getMessage(), (string) $index);
            }
        }
    }

    public function test_change_of_utf8_request_field_changes_signed_bytes(): void
    {
        $proof = new OmniDeskDeviceActivationProof;
        $baseline = $this->validRequest();
        $changed = $baseline;
        $changed['installation_id'] = 'install-é';
        self::assertNotSame(
            $proof->canonicalMessage($baseline),
            $proof->canonicalMessage($changed),
        );

        $this->expectExceptionMessage('FORBIDDEN');
        $proof->verify($changed);
    }
}
