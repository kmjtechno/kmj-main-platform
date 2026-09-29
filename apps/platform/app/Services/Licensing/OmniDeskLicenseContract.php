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

    /**
     * Main Platform's complete OmniDesk integration scope.
     *
     * @var list<string>
     */
    public const MAIN_PLATFORM_SCOPE = [
        'billing',
        'plans',
        'subscriptions',
        'commercial_reconciliation',
        'entitlements',
        'license_issuance',
        'device_activation_licensing',
        'lease_renewal',
        'revocation',
        'commercial_audit',
        'signing_key_custody',
    ];

    /**
     * OmniDesk runtime/data-plane responsibilities that must never move into Main Platform.
     *
     * @var list<string>
     */
    public const FORBIDDEN_RUNTIME_SCOPE = [
        'remote_session_transport',
        'p2p_connectivity',
        'session_signaling',
        'relay_data_plane',
        'screen_or_video_streaming',
        'audio_streaming',
        'remote_input_transport',
        'clipboard_transport',
        'file_transfer_data_plane',
        'media_encoding_or_decoding',
        'nat_traversal_runtime',
        'omnidesk_device_runtime',
    ];

    public const KEYS_ENDPOINT = '/api/v1/licensing/keys';

    public const ACTIVATIONS_ENDPOINT = '/api/v1/licensing/omnidesk/activations';

    public const LEASE_RENEW_ENDPOINT = '/api/v1/licensing/omnidesk/leases/renew';

    public const CURRENT_ENTITLEMENT_ENDPOINT = '/api/v1/licensing/omnidesk/entitlements/current';

    public const ACTIVATION_STATUS_ENDPOINT = '/api/v1/licensing/omnidesk/activations/{activation_id}/status';

    public const DEACTIVATE_ENDPOINT = '/api/v1/licensing/omnidesk/activations/{activation_id}/deactivate';

    public const TRANSFER_ENDPOINT = '/api/v1/licensing/omnidesk/activations/{activation_id}/transfer';

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

    public const VERIFICATION_ORDER = [
        'parse_strict_schema',
        'resolve_trusted_kid',
        'verify_ed25519_signature',
        'verify_protocol_and_contract_version',
        'verify_product_binding',
        'verify_time_bounds',
        'verify_activation_binding',
        'reject_replayed_or_older_sequence',
        'apply_revocation_state',
        'enforce_capabilities_and_limits',
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
