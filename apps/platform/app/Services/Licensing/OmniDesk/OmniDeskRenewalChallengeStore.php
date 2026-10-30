<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

use App\Services\Licensing\OmniDeskDeviceRenewalProof;
use App\Services\Licensing\OmniDeskLicenseContract;
use DomainException;
use Illuminate\Support\Facades\DB;

/**
 * Private, PostgreSQL-backed one-time challenge for the M9 renewal boundary.
 *
 * No public routes, signer or entitlement mutation. Caller must use a real,
 * tenant-authenticated principal and an outer transaction with the future
 * signed lease issuance and advanceLease() to make those actions atomic.
 */
final class OmniDeskRenewalChallengeStore
{
    /**
     * @return array{server_challenge:string,expires_in:int}
     */
    public function issue(string $activationId, string $organizationId): array
    {
        return DB::transaction(function () use ($activationId, $organizationId): array {
            $binding = $this->lockedBinding($activationId, $organizationId);
            $this->requireLiveBinding($binding, $organizationId);

            $challenge = rtrim(strtr(base64_encode(random_bytes(32)), '+/', '-_'), '=');
            $now = now();

            DB::table('omnidesk_renewal_challenges')->updateOrInsert(
                ['activation_id' => $activationId],
                [
                    'challenge_sha256' => hash('sha256', $challenge),
                    'expires_at' => $now->copy()->addMinutes(5),
                    'consumed_at' => null,
                    'updated_at' => $now,
                    'created_at' => $now,
                ],
            );

            return ['server_challenge' => $challenge, 'expires_in' => 300];
        }, 3);
    }

    /**
     * Atomically verifies a real device signature and consumes the
     * server-issued challenge. It does NOT advance a lease or sign a token.
     *
     * @param  array<string, mixed>  $request
     */
    public function verifyAndConsume(array $request, string $organizationId): void
    {
        $activationId = $request['activation_id'] ?? null;
        if (! is_string($activationId) || $activationId === '') {
            throw new DomainException('INVALID_REQUEST');
        }

        DB::transaction(function () use ($request, $organizationId, $activationId): void {
            $binding = $this->lockedBinding($activationId, $organizationId);
            $this->requireLiveBinding($binding, $organizationId);

            if (! is_string($request['current_jti'] ?? null)
                || ! hash_equals((string) $binding->current_jti, $request['current_jti'])
                || ! is_int($request['current_sequence'] ?? null)
                || $request['current_sequence'] !== (int) $binding->current_sequence) {
                throw new DomainException('OMNIDESK_REPLAY_DETECTED');
            }

            $row = DB::table('omnidesk_renewal_challenges')
                ->where('activation_id', $activationId)
                ->lockForUpdate()
                ->first();
            if ($row === null || $row->consumed_at !== null) {
                throw new DomainException('OMNIDESK_REPLAY_DETECTED');
            }
            if (now()->gte($row->expires_at)) {
                throw new DomainException('OMNIDESK_RENEWAL_CHALLENGE_EXPIRED');
            }
            $challenge = $request['server_challenge'] ?? null;
            if (! is_string($challenge)
                || ! hash_equals((string) $row->challenge_sha256, hash('sha256', $challenge))) {
                throw new DomainException('OMNIDESK_REPLAY_DETECTED');
            }

            // The verifier takes the public key from the tenant-bound DB row,
            // never from the request body.
            $publicKey = $this->decodeDeviceKey((string) $binding->device_public_key);
            app(OmniDeskDeviceRenewalProof::class)->verify($request, $publicKey);

            $updated = DB::table('omnidesk_renewal_challenges')
                ->where('activation_id', $activationId)
                ->whereNull('consumed_at')
                ->update(['consumed_at' => now(), 'updated_at' => now()]);
            if ($updated !== 1) {
                throw new DomainException('OMNIDESK_REPLAY_DETECTED');
            }
        }, 3);
    }

    private function lockedBinding(string $activationId, string $organizationId): object
    {
        $binding = DB::table('omnidesk_activation_bindings')
            ->where('activation_id', $activationId)
            ->where('organization_id', $organizationId)
            ->lockForUpdate()
            ->first();
        if ($binding === null
            || $binding->current_jti === null
            || (int) $binding->current_sequence < 1) {
            throw new DomainException('OMNIDESK_RENEWAL_CHALLENGE_DENIED');
        }

        return $binding;
    }

    private function requireLiveBinding(object $binding, string $organizationId): void
    {
        $activation = DB::table('kslp_activations')
            ->where('id', $binding->activation_id)
            ->whereNull('deactivated_at')
            ->first(['license_id']);
        if ($activation === null) {
            throw new DomainException('OMNIDESK_RENEWAL_CHALLENGE_DENIED');
        }

        $license = DB::table('kslp_licenses')
            ->where('id', $activation->license_id)
            ->where('customer_id', $organizationId)
            ->where('product', OmniDeskLicenseContract::PRODUCT_ID)
            ->where('status', 'active')
            ->whereNull('revoked_at')
            ->where('starts_at', '<=', now())
            ->where('expires_at', '>', now())
            ->exists();
        if (! $license) {
            throw new DomainException('OMNIDESK_RENEWAL_CHALLENGE_DENIED');
        }

        $product = DB::table('products')
            ->where('slug', OmniDeskLicenseContract::PRODUCT_SLUG)
            ->first(['id']);
        if ($product === null
            || ! DB::table('entitlements')
                ->where('id', $binding->entitlement_id)
                ->where('organization_id', $organizationId)
                ->where('product_id', $product->id)
                ->where('capability', OmniDeskLicenseContract::CAPABILITY)
                ->where('status', 'active')
                ->where('starts_at', '<=', now())
                ->where(static function ($query): void {
                    $query->whereNull('ends_at')->orWhere('ends_at', '>', now());
                })
                ->exists()) {
            throw new DomainException('OMNIDESK_RENEWAL_CHALLENGE_DENIED');
        }
    }

    /** @return non-empty-string */
    private function decodeDeviceKey(string $encoded): string
    {
        if (strlen($encoded) !== 43 || preg_match('/\A[A-Za-z0-9_-]{43}\z/D', $encoded) !== 1) {
            throw new DomainException('OMNIDESK_RENEWAL_CHALLENGE_DENIED');
        }
        $raw = base64_decode(strtr($encoded, '-_', '+/').'=', true);
        if ($raw === false
            || $raw === ''
            || strlen($raw) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES
            || rtrim(strtr(base64_encode($raw), '+/', '-_'), '=') !== $encoded) {
            throw new DomainException('OMNIDESK_RENEWAL_CHALLENGE_DENIED');
        }

        return $raw;
    }
}
