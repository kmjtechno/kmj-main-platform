<?php

namespace App\Services\Licensing;

use App\Services\Commerce\KmjProductCatalog;

final class OmniDeskLicenseContract
{
    public const PROTOCOL_VERSION = 'KSLP-v1';

    public const CONTRACT_VERSION = 'kmj.omnidesk.license.v1';

    public const PRODUCT_ID = 'KMJ_OMNIDESK';

    public const PRODUCT_SLUG = KmjProductCatalog::OMNIDESK_SLUG;

    public const CAPABILITY = ProductLicenseProfileRegistry::OMNIDESK_CAPABILITY;

    public const SIGNING_ALGORITHM = 'Ed25519';

    public const KEYS_ENDPOINT = '/api/v1/licensing/keys';

    public const ACTIVATIONS_ENDPOINT = '/api/v1/licensing/omnidesk/activations';

    public const LEASE_RENEW_ENDPOINT = '/api/v1/licensing/omnidesk/leases/renew';

    public const CURRENT_ENTITLEMENT_ENDPOINT = '/api/v1/licensing/omnidesk/entitlements/current';

    public const STATES = [
        'ACTIVE',
        'RENEWAL_DUE',
        'GRACE',
        'RESTRICTED',
        'REACTIVATED',
        'REVOKED',
    ];

    public const PLANS = [
        'Personal_Free',
        'Trial',
        'Professional',
        'Business',
        'Enterprise',
        'OEM_Custom',
    ];

    public const REQUIRED_SIGNED_CLAIMS = [
        'protocol_version',
        'contract_version',
        'jti',
        'kid',
        'license_id',
        'entitlement_id',
        'customer_id',
        'organization_id',
        'product_id',
        'product_slug',
        'plan',
        'activation_id',
        'device_public_key_fingerprint',
        'installation_id',
        'capabilities',
        'limits',
        'iat',
        'nbf',
        'exp',
        'lease_expires_at',
        'sequence',
        'nonce',
    ];

    public const ERROR_CODES = [
        'INVALID_REQUEST',
        'UNAUTHENTICATED',
        'FORBIDDEN',
        'PRODUCT_MISMATCH',
        'ENTITLEMENT_INACTIVE',
        'DEVICE_LIMIT_REACHED',
        'ACTIVATION_CONFLICT',
        'ACTIVATION_REVOKED',
        'LICENSE_REVOKED',
        'KEY_REVOKED',
        'LEASE_EXPIRED',
        'STALE_SEQUENCE',
        'REPLAY_DETECTED',
        'RATE_LIMITED',
        'SERVER_UNAVAILABLE',
    ];

    private function __construct() {}
}
