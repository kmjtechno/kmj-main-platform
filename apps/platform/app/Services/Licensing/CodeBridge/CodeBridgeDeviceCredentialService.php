<?php

declare(strict_types=1);

namespace App\Services\Licensing\CodeBridge;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

final class CodeBridgeDeviceCredentialService
{
    /** @return array{credential:string,device_id:string,expires_at_epoch:int} */
    public function rotate(string $licenseId, string $tenantId, string $deviceId, int $now): array
    {
        return DB::transaction(function () use ($licenseId, $tenantId, $deviceId, $now): array {
            $row = DB::table('codebridge_device_credentials')
                ->where('license_id', $licenseId)->where('tenant_id', $tenantId)->where('device_id', $deviceId)
                ->lockForUpdate()->first();

            if (! $row || $row->revoked_at !== null || (int) $row->expires_at_epoch <= $now) {
                throw new DomainException('CODEBRIDGE_CREDENTIAL_DENIED');
            }

            $license = DB::table('kslp_licenses')->where('id', $licenseId)->lockForUpdate()->first();
            if (! $license || $license->product !== 'KMJ_CODEBRIDGE' || $license->customer_id !== $tenantId
                || $license->status !== 'active' || $license->revoked_at !== null
                || strtotime($license->starts_at) > $now || strtotime($license->expires_at) <= $now) {
                throw new DomainException('CODEBRIDGE_CREDENTIAL_DENIED');
            }

            $credential = rtrim(strtr(base64_encode(random_bytes(48)), '+/', '-_'), '=');
            DB::table('codebridge_device_credentials')->where('id', $row->id)->update([
                'token_hash' => hash('sha256', $credential),
            ]);
            $this->audit($licenseId, $deviceId, 'codebridge_device_credential_rotated', 'Device credential rotated', [
                'activation_id' => $row->activation_id,
                'lease_sequence' => (int) $row->lease_sequence,
            ]);

            return ['credential' => $credential, 'device_id' => $deviceId, 'expires_at_epoch' => (int) $row->expires_at_epoch];
        }, 3);
    }

    public function revoke(string $licenseId, string $tenantId, string $deviceId, int $now): void
    {
        DB::transaction(function () use ($licenseId, $tenantId, $deviceId, $now): void {
            $row = DB::table('codebridge_device_credentials')
                ->where('license_id', $licenseId)->where('tenant_id', $tenantId)->where('device_id', $deviceId)
                ->lockForUpdate()->first();

            if (! $row) {
                throw new DomainException('CODEBRIDGE_CREDENTIAL_DENIED');
            }
            if ($row->revoked_at !== null) {
                return;
            }

            DB::table('codebridge_device_credentials')->where('id', $row->id)->update([
                'revoked_at' => gmdate('Y-m-d H:i:s', $now),
            ]);
            $this->audit($licenseId, $deviceId, 'codebridge_device_credential_revoked', 'Device credential revoked', [
                'activation_id' => $row->activation_id,
                'lease_sequence' => (int) $row->lease_sequence,
            ]);
        }, 3);
    }

    /** @param array<string,mixed> $metadata */
    private function audit(string $licenseId, string $deviceId, string $action, string $reason, array $metadata): void
    {
        DB::table('kslp_license_events')->insert([
            'license_id' => $licenseId,
            'actor_id' => 'codebridge-device:'.$deviceId,
            'action' => $action,
            'reason' => $reason,
            'correlation_id' => (string) Str::uuid(),
            'metadata' => json_encode($metadata, JSON_THROW_ON_ERROR),
            'created_at' => now(),
        ]);
    }
}
