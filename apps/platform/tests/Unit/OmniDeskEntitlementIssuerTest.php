<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Services\Licensing\OmniDesk\OmniDeskEntitlementIssuer;
use App\Services\Licensing\OmniDesk\OmniDeskSigner;
use DomainException;
use Tests\TestCase;

final class OmniDeskEntitlementIssuerTest extends TestCase
{
    private const EXPECTED_CANONICAL = '{"activation_id":"55555555-5555-4555-8555-555555555555","capabilities":["file.transfer","remote.interactive"],"contract_version":"kmj.omnidesk.license.v1","customer_id":"33333333-3333-4333-8333-333333333333","device_public_key_fingerprint":"sha256:test-device-fingerprint-0001","entitlement_id":"22222222-2222-4222-8222-222222222222","exp":1800086400,"iat":1800000000,"installation_id":"install-test-0001","jti":"test-jti-0000000000000001","kid":"test-kid-ed25519-v1","lease_expires_at":1800003600,"license_id":"11111111-1111-4111-8111-111111111111","limits":{"concurrent_sessions":2,"licensed_users":1,"managed_devices":5,"relay_bytes_monthly":1073741824,"relay_policy":"direct_preferred","unattended_devices":3},"nbf":1800000000,"nonce":"test-nonce-0000000000000001","organization_id":"44444444-4444-4444-8444-444444444444","plan":"Professional","product_id":"KMJ_OMNIDESK","product_slug":"kmj-omnidesk","protocol_version":"KSLP-v1","sequence":1}';

    private const EXPECTED_SIGNATURE = 'FrgopTJZX/II4FHv+irYy9Gv3Qe1+Zsx6NxMU+4VEUXKb91mFJWGCEjMTrZwbSUVfQGHy5zcvrYVzPrpFpbKCQ==';

    /** @return array<string, mixed> */
    private function claims(): array
    {
        return [
            'sequence' => 1,
            'product_slug' => 'kmj-omnidesk',
            'limits' => [
                'unattended_devices' => 3,
                'relay_policy' => 'direct_preferred',
                'managed_devices' => 5,
                'relay_bytes_monthly' => 1073741824,
                'licensed_users' => 1,
                'concurrent_sessions' => 2,
            ],
            'activation_id' => '55555555-5555-4555-8555-555555555555',
            'protocol_version' => 'KSLP-v1',
            'lease_expires_at' => 1800003600,
            'capabilities' => ['file.transfer', 'remote.interactive'],
            'organization_id' => '44444444-4444-4444-8444-444444444444',
            'customer_id' => '33333333-3333-4333-8333-333333333333',
            'jti' => 'test-jti-0000000000000001',
            'iat' => 1800000000,
            'device_public_key_fingerprint' => 'sha256:test-device-fingerprint-0001',
            'nonce' => 'test-nonce-0000000000000001',
            'plan' => 'Professional',
            'license_id' => '11111111-1111-4111-8111-111111111111',
            'product_id' => 'KMJ_OMNIDESK',
            'nbf' => 1800000000,
            'kid' => 'test-kid-ed25519-v1',
            'installation_id' => 'install-test-0001',
            'exp' => 1800086400,
            'contract_version' => 'kmj.omnidesk.license.v1',
            'entitlement_id' => '22222222-2222-4222-8222-222222222222',
        ];
    }

    private function vectorSigner(): OmniDeskSigner
    {
        $seed = base64_decode('AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA=', true);
        self::assertIsString($seed);
        $keypair = sodium_crypto_sign_seed_keypair($seed);
        $secret = sodium_crypto_sign_secretkey($keypair);

        return new class($secret) implements OmniDeskSigner
        {
            public function __construct(private readonly string $secret) {}

            public function kid(): string
            {
                return 'test-kid-ed25519-v1';
            }

            public function sign(string $canonicalPayload): string
            {
                return sodium_crypto_sign_detached($canonicalPayload, $this->secret);
            }
        };
    }

    public function test_rust_vector_canonical_payload_and_signature_match_exactly(): void
    {
        $result = app(OmniDeskEntitlementIssuer::class)
            ->issue($this->claims(), $this->vectorSigner());

        self::assertSame('Ed25519', $result['algorithm']);
        self::assertSame('test-kid-ed25519-v1', $result['kid']);
        self::assertSame(self::EXPECTED_CANONICAL, $result['canonical_payload']);
        self::assertSame(self::EXPECTED_SIGNATURE, $result['signature_base64']);
    }

    public function test_signer_kid_mismatch_fails_closed(): void
    {
        $claims = $this->claims();
        $claims['kid'] = 'wrong-kid';

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_ENTITLEMENT_PAYLOAD_INVALID');

        app(OmniDeskEntitlementIssuer::class)->issue($claims, $this->vectorSigner());
    }

    public function test_duplicate_capability_and_invalid_time_order_fail_closed(): void
    {
        $claims = $this->claims();
        $claims['capabilities'][] = 'remote.interactive';

        try {
            app(OmniDeskEntitlementIssuer::class)->issue($claims, $this->vectorSigner());
            self::fail('Duplicate capabilities must be rejected.');
        } catch (DomainException $exception) {
            self::assertSame('OMNIDESK_ENTITLEMENT_PAYLOAD_INVALID', $exception->getMessage());
        }

        $claims = $this->claims();
        $claims['lease_expires_at'] = $claims['exp'] + 1;

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_ENTITLEMENT_PAYLOAD_INVALID');

        app(OmniDeskEntitlementIssuer::class)->issue($claims, $this->vectorSigner());
    }

    public function test_invalid_signature_length_from_signer_is_rejected(): void
    {
        $signer = new class implements OmniDeskSigner
        {
            public function kid(): string
            {
                return 'test-kid-ed25519-v1';
            }

            public function sign(string $canonicalPayload): string
            {
                return hash('sha256', $canonicalPayload, true);
            }
        };

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_SIGNER_INVALID_SIGNATURE');

        app(OmniDeskEntitlementIssuer::class)->issue($this->claims(), $signer);
    }
}
