<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

use App\Services\Licensing\Kslp\KslpKeyRegistry;
use App\Services\Licensing\OmniDeskLicenseContract;
use DomainException;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

/**
 * Transactional OmniDesk-only lease authority.
 *
 * A real, externally provisioned OmniDeskSigner and independently published
 * Ed25519 verification key are mandatory. No private key is accepted from
 * HTTP, environment variables, or a database. Production must bind the
 * signer only to an owner-approved protected signing service.
 */
final class OmniDeskProtectedLeaseService
{
    public function __construct(
        private readonly OmniDeskActivationProof $deviceProof,
        private readonly OmniDeskActivationBindingStore $bindings,
        private readonly OmniDeskRenewalChallengeStore $challenges,
        private readonly OmniDeskEntitlementIssuer $issuer,
        private readonly KslpKeyRegistry $keys,
    ) {}

    /**
     * Activate one proven device against one unambiguous existing license.
     * The activation, binding, signature and replay cursor are all inside
     * one transaction; a signing/eligibility failure rolls everything back.
     *
     * @param  array<string, mixed>  $request
     * @return array{activation_id:string,signed_entitlement:string,lease_expires_at:int,server_time:int,key_set_version:string}
     */
    public function activate(
        array $request,
        string $idempotencyKey,
        OmniDeskApiPrincipal $principal,
        OmniDeskSigner $signer,
    ): array {
        $this->requireManager($principal);
        $this->validateActivationInput($request, $idempotencyKey);
        $this->deviceProof->verify($request, $idempotencyKey);

        return DB::transaction(function () use ($request, $idempotencyKey, $principal, $signer): array {
            $reference = $request['license_or_entitlement_reference'];
            $product = DB::table('products')
                ->where('slug', OmniDeskLicenseContract::PRODUCT_SLUG)
                ->first(['id']);
            if ($product === null) {
                throw new DomainException('OMNIDESK_PRODUCT_NOT_FOUND');
            }

            // A reference can be a license UUID or a tenant-owned entitlement
            // UUID. Unlocked discovery is only a hint for the license-first lock.
            $licensePreview = DB::table('kslp_licenses')
                ->where('id', $reference)
                ->where('customer_id', $principal->organizationId)
                ->where('product', OmniDeskLicenseContract::PRODUCT_ID)
                ->first(['id']);
            $entitlementReference = false;
            if ($licensePreview === null) {
                $entitlementReference = DB::table('entitlements')
                    ->where('id', $reference)
                    ->where('organization_id', $principal->organizationId)
                    ->where('product_id', $product->id)
                    ->where('capability', OmniDeskLicenseContract::CAPABILITY)
                    ->exists();
                if (! $entitlementReference) {
                    throw new DomainException('OMNIDESK_ACTIVATION_NOT_FOUND');
                }
                $candidates = DB::table('kslp_licenses')
                    ->where('customer_id', $principal->organizationId)
                    ->where('product', OmniDeskLicenseContract::PRODUCT_ID)
                    ->where('status', 'active')
                    ->whereNull('revoked_at')
                    ->limit(2)
                    ->get(['id']);
                if ($candidates->count() !== 1) {
                    throw new DomainException('OMNIDESK_ACTIVATION_CONFLICT');
                }
                $licenseId = (string) $candidates->first()->id;
            } else {
                $licenseId = (string) $licensePreview->id;
            }

            $license = DB::table('kslp_licenses')
                ->where('id', $licenseId)
                ->where('customer_id', $principal->organizationId)
                ->where('product', OmniDeskLicenseContract::PRODUCT_ID)
                ->lockForUpdate()
                ->first();
            if ($license === null
                || (string) $license->status !== 'active'
                || $license->revoked_at !== null
                || now()->lt($license->starts_at)
                || now()->gte($license->expires_at)) {
                throw new DomainException('OMNIDESK_LICENSE_INACTIVE');
            }

            $entitlements = DB::table('entitlements')
                ->where('organization_id', $principal->organizationId)
                ->where('product_id', $product->id)
                ->where('capability', OmniDeskLicenseContract::CAPABILITY)
                ->where('status', 'active')
                ->where('starts_at', '<=', now())
                ->where(static function ($query): void {
                    $query->whereNull('ends_at')->orWhere('ends_at', '>', now());
                })
                ->when($entitlementReference, static function ($query) use ($reference): void {
                    $query->where('id', $reference);
                })
                ->limit(2)
                ->lockForUpdate()
                ->get();
            if ($entitlements->count() !== 1) {
                // Fail closed instead of guessing an entitlement when the
                // commercial plan has more than one possible binding.
                throw new DomainException('OMNIDESK_ENTITLEMENT_INACTIVE');
            }
            $entitlement = $entitlements->first();

            // This first protected issuer supports exactly one active device
            // per license. Never silently assume plan seat limits from UI text.
            if (DB::table('kslp_activations')
                ->where('license_id', $licenseId)
                ->whereNull('deactivated_at')
                ->exists()
                || DB::table('kslp_activations')
                    ->where('idempotency_key', $idempotencyKey)
                    ->exists()) {
                throw new DomainException('OMNIDESK_ACTIVATION_CONFLICT');
            }

            $activationId = (string) Str::uuid();
            $publicKey = $request['device_public_key'];
            $installId = $request['installation_id'];
            $now = now();
            DB::table('kslp_activations')->insert([
                'id' => $activationId,
                'license_id' => $licenseId,
                'server_identity' => 'ed25519:'.$publicKey,
                'machine_identity_hash' => hash('sha256', $publicKey.'|'.$installId),
                'idempotency_key' => $idempotencyKey,
                'activated_at' => $now,
                'deactivated_at' => null,
                'created_at' => $now,
                'updated_at' => $now,
            ]);

            $binding = $this->bindings->bind(
                $activationId,
                $licenseId,
                (string) $entitlement->id,
                $principal->organizationId,
                $publicKey,
                $request['device_public_key_fingerprint'],
                $installId,
                $idempotencyKey,
                $principal->actorId,
            );
            $lease = $this->signedLease($binding, $license, $entitlement, $signer, 1);
            $this->bindings->advanceLease(
                $activationId,
                null,
                0,
                null,
                $lease['jti'],
                1,
                $lease['nonce'],
            );
            $this->audit($licenseId, $principal, $activationId, 'omnidesk_signed_activation', 1);

            return [
                'activation_id' => $activationId,
                'signed_entitlement' => $lease['token'],
                'lease_expires_at' => $lease['lease_expires_at'],
                'server_time' => $lease['server_time'],
                'key_set_version' => $lease['kid'],
            ];
        }, 3);
    }

    /**
     * Verify and consume a one-time device challenge, sign the next lease
     * with the protected signer, and advance its cursor atomically.
     *
     * @param  array<string, mixed>  $request
     * @return array{signed_entitlement:string,lease_expires_at:int,next_renewal_at:int,server_time:int}
     */
    public function renew(
        array $request,
        OmniDeskApiPrincipal $principal,
        OmniDeskSigner $signer,
    ): array {
        $this->requireManager($principal);

        return DB::transaction(function () use ($request, $principal, $signer): array {
            // Proof validation and challenge consumption acquire the same
            // license -> activation -> entitlement -> binding -> challenge
            // locks as every related lease/deactivation operation.
            $this->challenges->verifyAndConsume($request, $principal->organizationId);
            $activationId = $request['activation_id'];
            $binding = DB::table('omnidesk_activation_bindings')
                ->where('activation_id', $activationId)
                ->where('organization_id', $principal->organizationId)
                ->first();
            $activation = DB::table('kslp_activations')
                ->where('id', $activationId)
                ->whereNull('deactivated_at')
                ->first();
            if ($binding === null || $activation === null
                || (int) $binding->current_sequence !== $request['current_sequence']
                || ! hash_equals((string) $binding->current_jti, $request['current_jti'])) {
                throw new DomainException('OMNIDESK_REPLAY_DETECTED');
            }

            $license = DB::table('kslp_licenses')
                ->where('id', $activation->license_id)
                ->where('customer_id', $principal->organizationId)
                ->where('product', OmniDeskLicenseContract::PRODUCT_ID)
                ->first();
            $entitlement = DB::table('entitlements')
                ->where('id', $binding->entitlement_id)
                ->where('organization_id', $principal->organizationId)
                ->first();
            if ($license === null || $entitlement === null
                || (string) $license->status !== 'active'
                || $license->revoked_at !== null
                || now()->lt($license->starts_at)
                || now()->gte($license->expires_at)) {
                throw new DomainException('OMNIDESK_LICENSE_INACTIVE');
            }

            $sequence = (int) $binding->current_sequence + 1;
            $lease = $this->signedLease((array) $binding, $license, $entitlement, $signer, $sequence);
            $this->bindings->advanceLease(
                $activationId,
                (string) $binding->current_jti,
                (int) $binding->current_sequence,
                (string) $binding->current_nonce,
                $lease['jti'],
                $sequence,
                $lease['nonce'],
            );
            $this->audit((string) $license->id, $principal, $activationId, 'omnidesk_signed_renewal', $sequence);

            return [
                'signed_entitlement' => $lease['token'],
                'lease_expires_at' => $lease['lease_expires_at'],
                'next_renewal_at' => $lease['next_renewal_at'],
                'server_time' => $lease['server_time'],
            ];
        }, 3);
    }

    /**
     * @param  array<string, mixed>  $binding
     * @return array{token:string,jti:string,nonce:string,kid:string,lease_expires_at:int,next_renewal_at:int,server_time:int}
     */
    private function signedLease(
        array $binding,
        object $license,
        object $entitlement,
        OmniDeskSigner $signer,
        int $sequence,
    ): array {
        $kid = $signer->kid();
        $activeKey = DB::table('kslp_signing_keys')
            ->where('kid', $kid)
            ->where('purpose', 'license')
            ->where('status', 'active')
            ->whereNull('revoked_at')
            ->where('not_before', '<=', now())
            ->where(static function ($query): void {
                $query->whereNull('not_after')->orWhere('not_after', '>', now());
            })
            ->exists();
        if (! $activeKey) {
            throw new DomainException('OMNIDESK_SIGNER_UNAVAILABLE');
        }
        $publicKey = $this->keys->publicKey($kid, 'license');

        $now = time();
        $expiry = min(
            $now + 86_400,
            Carbon::parse($license->expires_at)->getTimestamp(),
            $entitlement->ends_at === null
                ? PHP_INT_MAX
                : Carbon::parse($entitlement->ends_at)->getTimestamp(),
        );
        $duration = min(3_600, intdiv(max(0, $expiry - $now), 2));
        if ($duration < 60) {
            throw new DomainException('OMNIDESK_LICENSE_INACTIVE');
        }
        $leaseExpiry = $now + $duration;
        $plan = match ((string) $license->plan) {
            'personal_free' => 'Personal_Free',
            'trial' => 'Trial',
            'professional' => 'Professional',
            'business' => 'Business',
            'enterprise' => 'Enterprise',
            'custom_oem' => 'OEM_Custom',
            default => throw new DomainException('OMNIDESK_LICENSE_INACTIVE'),
        };
        $jti = (string) Str::uuid();
        $nonce = rtrim(strtr(base64_encode(random_bytes(24)), '+/', '-_'), '=');

        $claims = [
            'protocol_version' => OmniDeskLicenseContract::PROTOCOL_VERSION,
            'contract_version' => OmniDeskLicenseContract::CONTRACT_VERSION,
            'jti' => $jti,
            'kid' => $kid,
            'license_id' => (string) $license->id,
            'entitlement_id' => (string) $entitlement->id,
            'customer_id' => (string) $license->customer_id,
            'organization_id' => (string) $binding['organization_id'],
            'product_id' => OmniDeskLicenseContract::PRODUCT_ID,
            'product_slug' => OmniDeskLicenseContract::PRODUCT_SLUG,
            'plan' => $plan,
            'activation_id' => (string) $binding['activation_id'],
            'device_public_key_fingerprint' => (string) $binding['device_public_key_fingerprint'],
            'installation_id' => (string) $binding['installation_id'],
            // Only the actual tenant-entitled capability. Never grant
            // clipboard, files, relay or unattended access implicitly.
            'capabilities' => [OmniDeskLicenseContract::CAPABILITY],
            'limits' => [
                'licensed_users' => 1,
                'managed_devices' => 1,
                'concurrent_sessions' => 1,
                'unattended_devices' => 0,
                'relay_bytes_monthly' => 0,
                'relay_policy' => 'direct_only',
            ],
            'iat' => $now,
            'nbf' => $now,
            'exp' => $expiry,
            'lease_expires_at' => $leaseExpiry,
            'sequence' => $sequence,
            'nonce' => $nonce,
        ];

        $signed = $this->issuer->issue($claims, $signer);
        $signature = base64_decode($signed['signature_base64'], true);
        if ($signature === false
            || ! sodium_crypto_sign_verify_detached(
                $signature, $signed['canonical_payload'], $publicKey,
            )) {
            throw new DomainException('OMNIDESK_SIGNER_UNAVAILABLE');
        }
        $token = rtrim(strtr(base64_encode($signed['canonical_payload']), '+/', '-_'), '=')
            .'.'.rtrim(strtr(base64_encode($signature), '+/', '-_'), '=');

        return [
            'token' => $token,
            'jti' => $jti,
            'nonce' => $nonce,
            'kid' => $kid,
            'lease_expires_at' => $leaseExpiry,
            'next_renewal_at' => $now + intdiv($duration, 2),
            'server_time' => $now,
        ];
    }

    private function requireManager(OmniDeskApiPrincipal $principal): void
    {
        if (! $principal->canManage) {
            throw new DomainException('OMNIDESK_FORBIDDEN');
        }
    }

    /** @param  array<string, mixed>  $request */
    private function validateActivationInput(array $request, string $idempotencyKey): void
    {
        $fields = [
            'license_or_entitlement_reference',
            'device_public_key',
            'device_public_key_fingerprint',
            'installation_id',
            'client_version',
            'protocol_version',
            'platform',
            'architecture',
            'client_nonce',
            'proof_scheme',
            'device_signature',
        ];
        $actual = array_keys($request);
        sort($actual);
        sort($fields);
        if ($actual !== $fields
            || ! preg_match('/\A[A-Za-z0-9_-]{16,128}\z/D', $idempotencyKey)
            || ! is_string($request['license_or_entitlement_reference'])
            || ! Str::isUuid($request['license_or_entitlement_reference'])
            || $request['protocol_version'] !== OmniDeskLicenseContract::PROTOCOL_VERSION) {
            throw new DomainException('INVALID_REQUEST');
        }
        foreach ($fields as $field) {
            if (! is_string($request[$field])
                || $request[$field] === ''
                || strlen($request[$field]) > 512) {
                throw new DomainException('INVALID_REQUEST');
            }
        }
    }

    private function audit(
        string $licenseId,
        OmniDeskApiPrincipal $principal,
        string $activationId,
        string $action,
        int $sequence,
    ): void {
        DB::table('kslp_license_events')->insert([
            'license_id' => $licenseId,
            'actor_id' => $principal->actorId,
            'action' => $action,
            'reason' => null,
            'correlation_id' => (string) Str::uuid(),
            'metadata' => json_encode([
                'activation_id' => $activationId,
                'sequence' => $sequence,
            ], JSON_THROW_ON_ERROR),
            'created_at' => now(),
        ]);
    }
}
