<?php

declare(strict_types=1);

namespace App\Services\Licensing\CodeBridge;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

final class CodeBridgeDeviceEnrollmentService
{
    /** @return array{credential:string,device_id:string,expires_at_epoch:int} */
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
            // overwritten; a revoked device requires fresh owner pairing.
            if (DB::table('codebridge_device_credentials')->where('activation_id', $activationId)->exists()
                || ($existing !== null && $existing->revoked_at === null)) {
                throw new DomainException('CODEBRIDGE_DEVICE_ALREADY_ENROLLED');
            }
            $policy = DB::table('plans')->where('code', 'codebridge.'.$license->plan)->where('status', 'active')->first();
            $limits = $policy ? json_decode($policy->limits, true) : null;
            if (! is_array($limits) || ! is_int($limits['devices'] ?? null) || $limits['devices'] < 1) {
                throw new DomainException('CODEBRIDGE_POLICY_UNAVAILABLE');
            }
            $active = DB::table('codebridge_device_credentials')->where('license_id', $licenseId)->whereNull('revoked_at')->where('expires_at_epoch', '>', $now)->count();
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
                DB::table('codebridge_device_credentials')
                    ->where('id', $existing->id)
                    ->whereNotNull('revoked_at')
                    ->update([
                        'license_id' => $licenseId,
                        'activation_id' => $activationId,
                        'server_identity' => $activation->server_identity,
                        'token_hash' => hash('sha256', $credential),
                        'lease_sequence' => 0,
                        'expires_at_epoch' => $expires,
                        'revoked_at' => null,
                    ]);
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
