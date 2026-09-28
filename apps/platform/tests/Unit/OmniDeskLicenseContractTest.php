<?php

namespace Tests\Unit;

use App\Services\Commerce\KmjProductCatalog;
use App\Services\Licensing\OmniDeskLicenseContract;
use App\Services\Licensing\ProductLicenseProfileRegistry;
use PHPUnit\Framework\TestCase;

final class OmniDeskLicenseContractTest extends TestCase
{
    public function test_canonical_identity_and_capability_are_locked(): void
    {
        self::assertSame('KSLP-v1', OmniDeskLicenseContract::PROTOCOL_VERSION);
        self::assertSame('kmj.omnidesk.license.v1', OmniDeskLicenseContract::CONTRACT_VERSION);
        self::assertSame('KMJ_OMNIDESK', OmniDeskLicenseContract::PRODUCT_ID);
        self::assertSame(KmjProductCatalog::OMNIDESK_SLUG, OmniDeskLicenseContract::PRODUCT_SLUG);
        self::assertSame(
            ProductLicenseProfileRegistry::OMNIDESK_CAPABILITY,
            OmniDeskLicenseContract::CAPABILITY,
        );
        self::assertSame('Ed25519', OmniDeskLicenseContract::SIGNING_ALGORITHM);
    }

    public function test_signed_entitlement_requires_replay_device_and_time_claims(): void
    {
        foreach ([
            'jti',
            'kid',
            'activation_id',
            'device_public_key_fingerprint',
            'installation_id',
            'iat',
            'nbf',
            'exp',
            'lease_expires_at',
            'sequence',
            'nonce',
        ] as $claim) {
            self::assertContains($claim, OmniDeskLicenseContract::REQUIRED_SIGNED_CLAIMS);
        }
    }

    public function test_offline_lifecycle_is_explicit_and_non_ambiguous(): void
    {
        self::assertSame(
            ['ACTIVE', 'RENEWAL_DUE', 'GRACE', 'RESTRICTED', 'REACTIVATED', 'REVOKED'],
            OmniDeskLicenseContract::STATES,
        );
    }

    public function test_api_boundary_is_versioned_and_product_scoped(): void
    {
        self::assertSame('/api/v1/licensing/keys', OmniDeskLicenseContract::KEYS_ENDPOINT);
        self::assertSame(
            '/api/v1/licensing/omnidesk/activations',
            OmniDeskLicenseContract::ACTIVATIONS_ENDPOINT,
        );
        self::assertSame(
            '/api/v1/licensing/omnidesk/leases/renew',
            OmniDeskLicenseContract::LEASE_RENEW_ENDPOINT,
        );
        self::assertSame(
            '/api/v1/licensing/omnidesk/entitlements/current',
            OmniDeskLicenseContract::CURRENT_ENTITLEMENT_ENDPOINT,
        );
    }

    public function test_error_contract_contains_security_failures(): void
    {
        foreach ([
            'PRODUCT_MISMATCH',
            'ACTIVATION_REVOKED',
            'LICENSE_REVOKED',
            'KEY_REVOKED',
            'LEASE_EXPIRED',
            'STALE_SEQUENCE',
            'REPLAY_DETECTED',
        ] as $code) {
            self::assertContains($code, OmniDeskLicenseContract::ERROR_CODES);
        }
    }
}
