<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

use App\Services\Licensing\OmniDeskLicenseContract;
use DomainException;

final class OmniDeskEntitlementIssuer
{
    public function __construct(
        private readonly OmniDeskCanonicalJson $canonicalJson,
    ) {}

    /**
     * Create a detached-signature envelope without ever exposing private key
     * material to the licensing service.
     *
     * @param  array<string, mixed>  $claims
     * @return array{
     *   algorithm: string,
     *   kid: string,
     *   canonical_payload: string,
     *   signature_base64: string
     * }
     */
    public function issue(array $claims, OmniDeskSigner $signer): array
    {
        $this->validate($claims, $signer);

        $canonicalPayload = $this->canonicalJson->encode($claims);
        $signature = $signer->sign($canonicalPayload);

        if (strlen($signature) !== SODIUM_CRYPTO_SIGN_BYTES) {
            throw new DomainException('OMNIDESK_SIGNER_INVALID_SIGNATURE');
        }

        return [
            'algorithm' => OmniDeskLicenseContract::SIGNING_ALGORITHM,
            'kid' => $signer->kid(),
            'canonical_payload' => $canonicalPayload,
            'signature_base64' => base64_encode($signature),
        ];
    }

    /**
     * @param  array<string, mixed>  $claims
     */
    private function validate(array $claims, OmniDeskSigner $signer): void
    {
        foreach (OmniDeskLicenseContract::REQUIRED_SIGNED_CLAIMS as $claim) {
            if (! array_key_exists($claim, $claims)) {
                throw new DomainException('OMNIDESK_ENTITLEMENT_PAYLOAD_INVALID');
            }
        }

        if (($claims['protocol_version'] ?? null) !== OmniDeskLicenseContract::PROTOCOL_VERSION
            || ($claims['contract_version'] ?? null) !== OmniDeskLicenseContract::CONTRACT_VERSION
            || ($claims['product_id'] ?? null) !== OmniDeskLicenseContract::PRODUCT_ID
            || ($claims['product_slug'] ?? null) !== OmniDeskLicenseContract::PRODUCT_SLUG
            || ($claims['kid'] ?? null) !== $signer->kid()
            || !in_array($claims['plan'] ?? null, OmniDeskLicenseContract::PLANS, true)) {
            throw new DomainException('OMNIDESK_ENTITLEMENT_PAYLOAD_INVALID');
        }

        foreach ([
            'jti',
            'kid',
            'license_id',
            'entitlement_id',
            'customer_id',
            'activation_id',
            'device_public_key_fingerprint',
            'installation_id',
            'nonce',
        ] as $field) {
            if (!is_string($claims[$field] ?? null) || trim($claims[$field]) === '') {
                throw new DomainException('OMNIDESK_ENTITLEMENT_PAYLOAD_INVALID');
            }
        }

        if (($claims['organization_id'] ?? null) !== null
            && (!is_string($claims['organization_id']) || trim($claims['organization_id']) === '')) {
            throw new DomainException('OMNIDESK_ENTITLEMENT_PAYLOAD_INVALID');
        }

        foreach (['iat', 'nbf', 'exp', 'lease_expires_at', 'sequence'] as $field) {
            if (!is_int($claims[$field] ?? null) || $claims[$field] < 0) {
                throw new DomainException('OMNIDESK_ENTITLEMENT_PAYLOAD_INVALID');
            }
        }

        if ($claims['sequence'] < 1
            || $claims['nbf'] > $claims['iat']
            || $claims['iat'] > $claims['lease_expires_at']
            || $claims['lease_expires_at'] > $claims['exp']) {
            throw new DomainException('OMNIDESK_ENTITLEMENT_PAYLOAD_INVALID');
        }

        $capabilities = $claims['capabilities'] ?? null;
        if (!is_array($capabilities)
            || ! array_is_list($capabilities)
            || $capabilities === []
            || count($capabilities) !== count(array_unique($capabilities))
            || array_filter($capabilities, fn (mixed $value): bool => !is_string($value) || trim($value) === '') !== []) {
            throw new DomainException('OMNIDESK_ENTITLEMENT_PAYLOAD_INVALID');
        }

        $limits = $claims['limits'] ?? null;
        if (!is_array($limits) || array_is_list($limits)) {
            throw new DomainException('OMNIDESK_ENTITLEMENT_PAYLOAD_INVALID');
        }

        $requiredLimits = [
            'licensed_users',
            'managed_devices',
            'concurrent_sessions',
            'unattended_devices',
            'relay_bytes_monthly',
            'relay_policy',
        ];
        foreach ($requiredLimits as $limit) {
            if (! array_key_exists($limit, $limits)) {
                throw new DomainException('OMNIDESK_ENTITLEMENT_PAYLOAD_INVALID');
            }
        }

        foreach ([
            'licensed_users',
            'managed_devices',
            'concurrent_sessions',
            'unattended_devices',
            'relay_bytes_monthly',
        ] as $limit) {
            $value = $limits[$limit];
            if ($value !== null && (!is_int($value) || $value < 0)) {
                throw new DomainException('OMNIDESK_ENTITLEMENT_PAYLOAD_INVALID');
            }
        }

        if (!is_string($limits['relay_policy']) || trim($limits['relay_policy']) === '') {
            throw new DomainException('OMNIDESK_ENTITLEMENT_PAYLOAD_INVALID');
        }
    }
}
