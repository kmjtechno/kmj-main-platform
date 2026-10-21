<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

use App\Services\Licensing\OmniDeskLicenseContract;
use DomainException;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;

final class OmniDeskActivationBindingStore
{
    /**
     * Persist the immutable device/tenant/entitlement binding for an already
     * authorized KSLP activation.
     *
     * @return array<string, mixed>
     */
    public function bind(
        string $activationId,
        string $licenseId,
        string $entitlementId,
        string $organizationId,
        string $devicePublicKey,
        string $deviceFingerprint,
        string $installationId,
        string $idempotencyKey,
        string $actorId,
    ): array {
        $this->validateDeviceIdentity(
            $devicePublicKey,
            $deviceFingerprint,
            $installationId,
            $idempotencyKey,
        );

        return DB::transaction(function () use (
            $activationId,
            $licenseId,
            $entitlementId,
            $organizationId,
            $devicePublicKey,
            $deviceFingerprint,
            $installationId,
            $idempotencyKey,
            $actorId,
        ): array {
            $license = DB::table('kslp_licenses')
                ->where('id', $licenseId)
                ->lockForUpdate()
                ->first();
            if ($license === null) {
                throw new DomainException('OMNIDESK_LICENSE_NOT_FOUND');
            }
            if ((string) $license->customer_id !== $organizationId
                || (string) $license->product !== OmniDeskLicenseContract::PRODUCT_ID) {
                throw new DomainException('OMNIDESK_PRODUCT_OR_TENANT_MISMATCH');
            }
            if ((string) $license->status !== 'active'
                || $license->revoked_at !== null
                || now()->lt($license->starts_at)
                || now()->gte($license->expires_at)) {
                throw new DomainException('OMNIDESK_LICENSE_INACTIVE');
            }

            $activation = DB::table('kslp_activations')
                ->where('id', $activationId)
                ->where('license_id', $licenseId)
                ->lockForUpdate()
                ->first();
            if ($activation === null || $activation->deactivated_at !== null) {
                throw new DomainException('OMNIDESK_ACTIVATION_CONFLICT');
            }

            $product = Product::query()
                ->where('slug', OmniDeskLicenseContract::PRODUCT_SLUG)
                ->first(['id']);
            if (! $product instanceof Product) {
                throw new DomainException('OMNIDESK_PRODUCT_NOT_FOUND');
            }

            $entitlement = Entitlement::query()
                ->whereKey($entitlementId)
                ->where('organization_id', $organizationId)
                ->where('product_id', $product->getKey())
                ->where('capability', OmniDeskLicenseContract::CAPABILITY)
                ->where('status', 'active')
                ->lockForUpdate()
                ->first();
            if (! $entitlement instanceof Entitlement
                || $entitlement->starts_at->isFuture()
                || ($entitlement->ends_at !== null && ! $entitlement->ends_at->isFuture())) {
                throw new DomainException('OMNIDESK_ENTITLEMENT_INACTIVE');
            }

            $candidate = [
                'activation_id' => $activationId,
                'entitlement_id' => $entitlementId,
                'organization_id' => $organizationId,
                'device_public_key' => $devicePublicKey,
                'device_public_key_fingerprint' => $deviceFingerprint,
                'installation_id' => $installationId,
                'idempotency_key' => $idempotencyKey,
            ];

            $existing = DB::table('omnidesk_activation_bindings')
                ->where('idempotency_key', $idempotencyKey)
                ->lockForUpdate()
                ->first();
            if ($existing !== null) {
                $this->requireExactBinding((array) $existing, $candidate);

                return (array) $existing;
            }

            $existing = DB::table('omnidesk_activation_bindings')
                ->where('activation_id', $activationId)
                ->lockForUpdate()
                ->first();
            if ($existing !== null) {
                $this->requireExactBinding((array) $existing, $candidate);

                return (array) $existing;
            }

            $now = now();
            DB::table('omnidesk_activation_bindings')->insert($candidate + [
                'current_jti' => null,
                'current_sequence' => 0,
                'created_at' => $now,
                'updated_at' => $now,
            ]);

            DB::table('kslp_license_events')->insert([
                'license_id' => $licenseId,
                'actor_id' => $actorId,
                'action' => 'omnidesk_device_bound',
                'reason' => null,
                'correlation_id' => (string) \Illuminate\Support\Str::uuid(),
                'metadata' => json_encode([
                    'activation_id' => $activationId,
                    'entitlement_id' => $entitlementId,
                    'device_public_key_fingerprint' => $deviceFingerprint,
                ], JSON_THROW_ON_ERROR),
                'created_at' => $now,
            ]);

            return (array) DB::table('omnidesk_activation_bindings')
                ->where('activation_id', $activationId)
                ->first();
        }, 3);
    }

    /**
     * Atomically advance the signed entitlement replay cursor.
     *
     * @return array<string, mixed>
     */
    public function advanceLease(
        string $activationId,
        ?string $expectedJti,
        int $expectedSequence,
        string $nextJti,
        int $nextSequence,
    ): array {
        if ($expectedSequence < 0
            || $nextSequence !== $expectedSequence + 1
            || trim($nextJti) === ''
            || strlen($nextJti) > 128) {
            throw new DomainException('OMNIDESK_LEASE_SEQUENCE_INVALID');
        }

        return DB::transaction(function () use (
            $activationId,
            $expectedJti,
            $expectedSequence,
            $nextJti,
            $nextSequence,
        ): array {
            $binding = DB::table('omnidesk_activation_bindings')
                ->where('activation_id', $activationId)
                ->lockForUpdate()
                ->first();
            if ($binding === null) {
                throw new DomainException('OMNIDESK_ACTIVATION_CONFLICT');
            }

            if ((int) $binding->current_sequence !== $expectedSequence
                || ($binding->current_jti === null ? $expectedJti !== null : ! hash_equals(
                    (string) $binding->current_jti,
                    (string) $expectedJti,
                ))) {
                throw new DomainException('OMNIDESK_REPLAY_DETECTED');
            }

            DB::table('omnidesk_activation_bindings')
                ->where('activation_id', $activationId)
                ->update([
                    'current_jti' => $nextJti,
                    'current_sequence' => $nextSequence,
                    'updated_at' => now(),
                ]);

            return (array) DB::table('omnidesk_activation_bindings')
                ->where('activation_id', $activationId)
                ->first();
        }, 3);
    }

    /**
     * @param array<string, mixed> $existing
     * @param array<string, string> $candidate
     */
    private function requireExactBinding(array $existing, array $candidate): void
    {
        foreach ($candidate as $key => $value) {
            if (! hash_equals((string) ($existing[$key] ?? ''), $value)) {
                throw new DomainException('OMNIDESK_ACTIVATION_CONFLICT');
            }
        }
    }

    private function validateDeviceIdentity(
        string $devicePublicKey,
        string $deviceFingerprint,
        string $installationId,
        string $idempotencyKey,
    ): void {
        if (preg_match('/\A[A-Za-z0-9_-]{43}\z/', $devicePublicKey) !== 1
            || strlen($installationId) < 8
            || strlen($installationId) > 256
            || strlen($idempotencyKey) < 16
            || strlen($idempotencyKey) > 128) {
            throw new DomainException('OMNIDESK_DEVICE_BINDING_INVALID');
        }

        $padding = (4 - strlen($devicePublicKey) % 4) % 4;
        $raw = base64_decode(
            strtr($devicePublicKey, '-_', '+/').str_repeat('=', $padding),
            true,
        );
        if ($raw === false || strlen($raw) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES) {
            throw new DomainException('OMNIDESK_DEVICE_BINDING_INVALID');
        }

        $expected = 'sha256:'.hash('sha256', $raw);
        if (! hash_equals($expected, $deviceFingerprint)) {
            throw new DomainException('OMNIDESK_DEVICE_BINDING_INVALID');
        }
    }
}
