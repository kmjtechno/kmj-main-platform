<?php

declare(strict_types=1);

namespace App\Services\Licensing\Kslp;

use App\Models\User;
use DomainException;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

/**
 * Gated KSLP-v1 CloudOS device-seat recovery with real new-device Ed25519
 * possession proof; never a browser-only "reset HWID" permission.
 *
 * Disabled in all environments until independent signed client proof,
 * issuer policy, offline-lease time/sequence and acceptance gates are attested.
 */
final class KslpCustomerDeviceTransfer
{
    public const COOLDOWN_HOURS = 24;

    public function __construct(
        private readonly OrganizationDirectory $organizations,
        private readonly OrganizationCapabilityContext $capabilities,
        private readonly KslpActivationProof $proof,
        private readonly KslpLicenseControlPlane $control,
    ) {}

    /** @return array<string, mixed> */
    public function challenge(User $actor, string $licenseId, string $newServerIdentity): array
    {
        return DB::transaction(function () use ($actor, $licenseId, $newServerIdentity): array {
            $this->eligible($actor, $licenseId, true);
            $this->requireTransferWindow($licenseId);

            // The KSLP proof service parses Ed25519 public keys and generates
            // an expiring, single-use, server-bound random challenge.
            $challenge = $this->proof->challenge($licenseId, $newServerIdentity);

            return [
                ...$challenge,
                'license_id' => $licenseId,
                'signature_domain' => 'KSLP-ACTIVATE-v1',
                'status' => 'proof_required',
            ];
        }, 3);
    }

    /**
     * @return array{activation_id: string, signed_lease_issued: bool, status: string}
     */
    public function transfer(
        User $actor,
        string $licenseId,
        string $newServerIdentity,
        string $newMachineHash,
        string $idempotencyKey,
        string $challengeId,
        string $nonce,
        string $signature,
        string $reason,
    ): array {
        if (mb_strlen(trim($reason)) < 8 || mb_strlen(trim($reason)) > 240) {
            throw new DomainException('KSLP_TRANSFER_REASON_REQUIRED');
        }

        return DB::transaction(function () use (
            $actor, $licenseId, $newServerIdentity, $newMachineHash,
            $idempotencyKey, $challengeId, $nonce, $signature, $reason,
        ): array {
            $this->eligible($actor, $licenseId, true);

            // An exact successful retry is safe even within a cooldown. The
            // control plane validates license, active binding and device pair.
            $existing = DB::table('kslp_activations')
                ->where('idempotency_key', $idempotencyKey)
                ->first();
            if ($existing === null) {
                $this->requireTransferWindow($licenseId, $newServerIdentity, $newMachineHash);
            }

            // This nested KSLP transaction serializes the current license,
            // consumes the one-time proof atomically and rolls back the old
            // deactivation if new device verification fails.
            $next = $this->control->transfer(
                $licenseId, $newServerIdentity, $newMachineHash,
                $idempotencyKey, 'customer:'.$actor->getKey(), $reason,
                $challengeId, $nonce, $signature,
            );

            if ($existing === null) {
                // Signed online renewals now require a newer monotonic
                // sequence. Previously cached offline leases may remain
                // valid until their independently capped 24h expiry.
                DB::table('kslp_licenses')->where('id', $licenseId)->update([
                    'sequence' => DB::raw('sequence+1'),
                    'updated_at' => now(),
                ]);
            }

            return [
                'activation_id' => (string) $next['id'],
                'signed_lease_issued' => false,
                'status' => 'device_transfer_recorded_pending_signed_lease',
            ];
        }, 3);
    }

    private function eligible(User $actor, string $licenseId, bool $lock): void
    {
        if (! $actor->hasVerifiedEmail()) {
            throw new DomainException('KSLP_TRANSFER_DENIED');
        }

        $query = DB::table('kslp_licenses')->where('id', $licenseId);
        $license = ($lock ? $query->lockForUpdate() : $query)->first();
        if ($license === null) {
            throw new DomainException('KSLP_TRANSFER_DENIED');
        }

        $scope = (string) $license->customer_id;
        $owned = hash_equals((string) $actor->getKey(), $scope);
        if (! $owned) {
            foreach ($this->organizations->forUser((int) $actor->getKey()) as $org) {
                if ($org['id'] === $scope
                    && $this->capabilities->allows((int) $actor->getKey(), $scope, 'license.manage')) {
                    $owned = true;
                    break;
                }
            }
        }

        if (! $owned || $license->product !== 'KMJ_CLOUDOS'
            || $license->plan === 'trial'
            || $license->status !== 'active'
            || $license->revoked_at !== null
            || Carbon::parse($license->starts_at)->gt(now())
            || Carbon::parse($license->expires_at)->lte(now())) {
            throw new DomainException('KSLP_TRANSFER_DENIED');
        }
    }

    private function requireTransferWindow(
        string $licenseId,
        ?string $newServerIdentity = null,
        ?string $newMachineHash = null,
    ): void {
        // No valid active seat, multiple live bindings, or a recently
        // activated seat -> never silently mint another concurrent device.
        $active = DB::table('kslp_activations')->where('license_id', $licenseId)
            ->whereNull('deactivated_at')
            ->limit(2)->get(['server_identity', 'machine_identity_hash', 'activated_at']);
        if ($active->count() !== 1) {
            throw new DomainException('KSLP_TRANSFER_SEAT_NOT_READY');
        }
        $current = $active->first();
        if (Carbon::parse($current->activated_at)->gt(now()->subHours(self::COOLDOWN_HOURS))) {
            throw new DomainException('KSLP_TRANSFER_COOLDOWN');
        }
        if ($newServerIdentity !== null && $newMachineHash !== null
            && hash_equals((string) $current->server_identity, $newServerIdentity)
            && hash_equals((string) $current->machine_identity_hash, $newMachineHash)) {
            throw new DomainException('KSLP_TRANSFER_SAME_DEVICE');
        }

        // Audited transfer events, not client timestamps, govern cooldown.
        if (DB::table('kslp_license_events')->where('license_id', $licenseId)
            ->where('action', 'transferred')
            ->where('created_at', '>', now()->subHours(self::COOLDOWN_HOURS))
            ->exists()) {
            throw new DomainException('KSLP_TRANSFER_COOLDOWN');
        }
    }
}
