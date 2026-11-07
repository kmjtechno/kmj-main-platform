<?php

declare(strict_types=1);

namespace App\Services\Licensing\CodeBridge;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

final class CodeBridgeDeviceEnrollmentService
{
    /** @return array{credential:string,device_id:string,expires_at_epoch:int} */
    /**
     * Pairing state as seen by the owner. Redemption is refused once the
     * one-time code expires, so an approved but unredeemed pairing past its
     * expiry can never deliver its credential to any agent.
     */
    public static function pairingState(?string $status, mixed $consumedAt, ?string $expiresAt, int $now): string
    {
        if ($status === 'approved' && $consumedAt === null) {
            return $expiresAt !== null && strtotime($expiresAt) <= $now ? 'approval_expired' : 'approved_unredeemed';
        }

        return $status === 'consumed' && $consumedAt !== null ? 'redeemed' : 'unknown';
    }

    private static function orphaned(object $credential, int $now): bool
    {
        return DB::table('codebridge_device_pairings')
            ->where('activation_id', $credential->activation_id)
            ->where('tenant_id', $credential->tenant_id)
            ->where('status', 'approved')
            ->whereNull('consumed_at')
            ->where('expires_at', '<=', gmdate('Y-m-d H:i:s', $now))
            ->exists();
    }

    public function enroll(string $licenseId, string $activationId, string $tenantId, string $deviceId, int $now): array
    {
        if (! preg_match('/\A[A-Za-z0-9_-]{1,64}\z/D', $tenantId) || ! preg_match('/\A[A-Za-z0-9_-]{1,64}\z/D', $deviceId)) {
            throw new DomainException('CODEBRIDGE_ENROLLMENT_DENIED');
        }

        return DB::transaction(function () use ($licenseId, $activationId, $tenantId, $deviceId, $now): array {
            $license = DB::table('kslp_licenses')->where('id', $licenseId)->lockForUpdate()->first();
            if (! $license || $license->product !== 'KMJ_CODEBRIDGE' || $license->customer_id !== $tenantId || $license->status !== 'active' || $license->revoked_at !== null || strtotime($license->starts_at) > $now || strtotime($license->expires_at) <= $now) {
                throw new DomainException('CODEBRIDGE_ENROLLMENT_DENIED');
            }
            $activation = DB::table('kslp_activations')->where('id', $activationId)->where('license_id', $licenseId)->whereNull('deactivated_at')->lockForUpdate()->first();
            if (! $activation) {
                throw new DomainException('CODEBRIDGE_ENROLLMENT_DENIED');
            }
            $existing = DB::table('codebridge_device_credentials')
                ->where('tenant_id', $tenantId)
                ->where('device_id', $deviceId)
                ->lockForUpdate()
                ->first();
            // Never reuse a prior activation. Active credentials cannot be
            // overwritten. Explicitly expired credentials can be replaced
            // only through the same new proof-bound, owner-approved pairing.
            // So can an ORPHANED credential: its approval expired before any
            // agent redeemed it, so its token was never delivered to anyone.
            $orphaned = $existing !== null && self::orphaned($existing, $now);
            if (DB::table('codebridge_device_credentials')->where('activation_id', $activationId)->exists()
                || ($existing !== null && $existing->revoked_at === null && (int) $existing->expires_at_epoch > $now
                    && ! $orphaned)) {
                throw new DomainException('CODEBRIDGE_DEVICE_ALREADY_ENROLLED');
            }
            $policy = DB::table('plans')->where('code', 'codebridge.'.$license->plan)->where('status', 'active')->first();
            $limits = $policy ? json_decode($policy->limits, true) : null;
            if (! is_array($limits) || ! is_int($limits['devices'] ?? null) || $limits['devices'] < 1) {
                throw new DomainException('CODEBRIDGE_POLICY_UNAVAILABLE');
            }
            // Orphaned credentials (expired, never-redeemed approvals) hold no seat.
            $active = DB::table('codebridge_device_credentials')->where('license_id', $licenseId)->whereNull('revoked_at')->where('expires_at_epoch', '>', $now)
                ->whereNotExists(static function ($query) use ($now): void {
                    $query->selectRaw('1')->from('codebridge_device_pairings as orphan')
                        ->whereColumn('orphan.activation_id', 'codebridge_device_credentials.activation_id')
                        ->where('orphan.status', 'approved')
                        ->whereNull('orphan.consumed_at')
                        ->where('orphan.expires_at', '<=', gmdate('Y-m-d H:i:s', $now));
                })
                ->count();
            if ($active >= $limits['devices']) {
                throw new DomainException('CODEBRIDGE_DEVICE_LIMIT');
            }

            $credential = rtrim(strtr(base64_encode(random_bytes(48)), '+/', '-_'), '=');
            $expires = min($now + 31536000, strtotime($license->expires_at));
            if ($existing !== null) {
                // Unique (tenant, device) remains one row: replace only after
                // revocation and deactivate the OLD activation so it cannot
                // be silently reused for another device after the swap.
                DB::table('kslp_activations')
                    ->where('id', $existing->activation_id)
                    ->where('license_id', $existing->license_id)
                    ->whereNull('deactivated_at')
                    ->update(['deactivated_at' => now()]);
                if ($orphaned) {
                    // The expired one-time grant can never be redeemed; drop its
                    // undelivered secret so nothing recoverable remains.
                    DB::table('codebridge_device_pairings')
                        ->where('activation_id', $existing->activation_id)
                        ->where('status', 'approved')
                        ->whereNull('consumed_at')
                        ->update(['status' => 'expired', 'credential_ciphertext' => null, 'updated_at' => now()]);
                }
                $updated = DB::table('codebridge_device_credentials')
                    ->where('id', $existing->id)
                    ->where(function ($query) use ($now, $orphaned): void {
                        $query->whereNotNull('revoked_at')->orWhere('expires_at_epoch', '<=', $now);
                        if ($orphaned) {
                            $query->orWhere('revoked_at', null);
                        }
                    })
                    ->update([
                        'license_id' => $licenseId,
                        'activation_id' => $activationId,
                        'server_identity' => $activation->server_identity,
                        'token_hash' => hash('sha256', $credential),
                        'lease_sequence' => 0,
                        'expires_at_epoch' => $expires,
                        'revoked_at' => null,
                    ]);
                if ($updated !== 1) {
                    throw new DomainException('CODEBRIDGE_ENROLLMENT_RACE');
                }
            } else {
                DB::table('codebridge_device_credentials')->insert([
                    'id' => (string) Str::uuid(), 'license_id' => $licenseId, 'activation_id' => $activationId,
                    'tenant_id' => $tenantId, 'device_id' => $deviceId, 'server_identity' => $activation->server_identity,
                    'token_hash' => hash('sha256', $credential), 'lease_sequence' => 0, 'expires_at_epoch' => $expires,
                ]);
            }
            DB::table('kslp_license_events')->insert([
                'license_id' => $licenseId, 'actor_id' => 'codebridge-enrollment:'.$deviceId,
                'action' => $existing === null ? 'codebridge_device_enrolled' : 'codebridge_device_reenrolled',
                'reason' => 'Proof-bound device credential provisioned with fresh activation',
                'correlation_id' => (string) Str::uuid(), 'metadata' => json_encode(['activation_id' => $activationId, 'device_id' => $deviceId], JSON_THROW_ON_ERROR),
                'created_at' => now(),
            ]);

            return ['credential' => $credential, 'device_id' => $deviceId, 'expires_at_epoch' => $expires];
        }, 3);
    }
}
