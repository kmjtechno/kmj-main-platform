<?php

declare(strict_types=1);

namespace App\Services\Licensing\CodeBridge;

use DomainException;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

final class CodeBridgeDevicePairingService
{
    public function __construct(
        private readonly CodeBridgeDeviceEnrollmentService $enrollment,
        private readonly OrganizationDirectory $organizations,
    ) {}

    /** @param array<string,mixed> $input
     * @return array<string,mixed>
     */
    public function create(array $input, int $now): array
    {
        $deviceCode = rtrim(strtr(base64_encode(random_bytes(48)), '+/', '-_'), '=');
        $alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
        $userCode = '';
        for ($i = 0; $i < 8; $i++) {
            $userCode .= $alphabet[random_int(0, strlen($alphabet) - 1)];
        }
        $displayCode = substr($userCode, 0, 4).'-'.substr($userCode, 4);
        $id = (string) Str::uuid();

        DB::table('codebridge_device_pairings')->insert([
            'id' => $id,
            'device_code_hash' => hash('sha256', $deviceCode),
            'user_code_hash' => hash('sha256', $userCode),
            'device_id' => $input['device']['id'],
            'device_name' => $input['device']['name'],
            'platform' => $input['device']['platform'],
            'arch' => $input['device']['arch'],
            'project_id' => $input['project']['id'],
            'project_name' => $input['project']['name'],
            'requested_permissions' => json_encode($input['requested_permissions'], JSON_THROW_ON_ERROR),
            'code_challenge' => $input['code_challenge'],
            'status' => 'pending',
            'expires_at' => gmdate('Y-m-d H:i:s', $now + 300),
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $base = rtrim((string) config('app.url'), '/');

        return [
            'device_code' => $deviceCode,
            'user_code' => $displayCode,
            'verification_uri' => $base.'/codebridge/pair',
            'verification_uri_complete' => $base.'/codebridge/pair?code='.rawurlencode($displayCode),
            'expires_in' => 300,
            'interval' => 5,
        ];
    }

    /** @return array<string,mixed>|null */
    public function preview(string $displayCode, int $userId, int $now): ?array
    {
        $code = strtoupper(str_replace('-', '', trim($displayCode)));
        if (! preg_match('/\A[A-Z2-9]{8}\z/D', $code)) {
            return null;
        }
        $row = DB::table('codebridge_device_pairings')
            ->where('user_code_hash', hash('sha256', $code))
            ->where('status', 'pending')
            ->where('expires_at', '>', gmdate('Y-m-d H:i:s', $now))
            ->first();
        if (! $row) {
            return null;
        }

        $eligible = collect($this->organizations->forUser($userId))
            ->filter(fn (array $org): bool => $this->organizations->userCanManage($userId, $org['id']))
            ->filter(fn (array $org): bool => DB::table('kslp_licenses')
                ->where('customer_id', $org['id'])
                ->where('product', 'KMJ_CODEBRIDGE')
                ->where('status', 'active')
                ->whereNull('revoked_at')
                ->where('starts_at', '<=', now())
                ->where('expires_at', '>', now())
                ->exists())
            ->values()
            ->all();

        return [
            'code' => $displayCode,
            'device_id' => $row->device_id,
            'device_name' => $row->device_name,
            'platform' => $row->platform,
            'arch' => $row->arch,
            'project_id' => $row->project_id,
            'project_name' => $row->project_name,
            'permissions' => json_decode($row->requested_permissions, true, flags: JSON_THROW_ON_ERROR),
            'expires_at' => $row->expires_at,
            'organizations' => $eligible,
        ];
    }

    public function approve(string $displayCode, int $userId, string $tenantId, int $now): void
    {
        if (! $this->organizations->userCanManage($userId, $tenantId)) {
            throw new DomainException('CODEBRIDGE_PAIRING_DENIED');
        }
        $code = strtoupper(str_replace('-', '', trim($displayCode)));

        DB::transaction(function () use ($code, $tenantId, $now): void {
            $row = DB::table('codebridge_device_pairings')
                ->where('user_code_hash', hash('sha256', $code))
                ->lockForUpdate()
                ->first();
            if (! $row || $row->status !== 'pending' || strtotime($row->expires_at) <= $now) {
                throw new DomainException('CODEBRIDGE_PAIRING_EXPIRED');
            }
            $license = DB::table('kslp_licenses')
                ->where('customer_id', $tenantId)
                ->where('product', 'KMJ_CODEBRIDGE')
                ->where('status', 'active')
                ->whereNull('revoked_at')
                ->where('starts_at', '<=', gmdate('Y-m-d H:i:s', $now))
                ->where('expires_at', '>', gmdate('Y-m-d H:i:s', $now))
                ->oldest('created_at')
                ->lockForUpdate()
                ->first();
            if (! $license) {
                throw new DomainException('CODEBRIDGE_PAIRING_NO_LICENSE');
            }

            $activationId = (string) Str::uuid();
            DB::table('kslp_activations')->insert([
                'id' => $activationId,
                'license_id' => $license->id,
                'server_identity' => 'codebridge-device:'.$row->device_id,
                'machine_identity_hash' => hash('sha256', $row->device_id.'|'.$row->code_challenge.'|'.$row->project_id),
                'idempotency_key' => 'codebridge-pairing:'.$row->id,
                'activated_at' => now(),
                'created_at' => now(),
                'updated_at' => now(),
            ]);

            $issued = $this->enrollment->enroll(
                (string) $license->id,
                $activationId,
                $tenantId,
                (string) $row->device_id,
                $now,
            );

            DB::table('codebridge_device_pairings')->where('id', $row->id)->update([
                'status' => 'approved',
                'tenant_id' => $tenantId,
                'license_id' => $license->id,
                'activation_id' => $activationId,
                'credential_ciphertext' => Crypt::encryptString($issued['credential']),
                'approved_at' => now(),
                'updated_at' => now(),
            ]);
        }, 3);
    }

    /** @return array<string,mixed> */
    public function redeem(string $deviceCode, string $verifier, string $deviceId, int $now): array
    {
        return DB::transaction(function () use ($deviceCode, $verifier, $deviceId, $now): array {
            $row = DB::table('codebridge_device_pairings')
                ->where('device_code_hash', hash('sha256', $deviceCode))
                ->lockForUpdate()
                ->first();
            if (! $row || strtotime($row->expires_at) <= $now) {
                throw new DomainException('CODEBRIDGE_PAIRING_EXPIRED');
            }
            if ($row->status === 'pending') {
                throw new DomainException('CODEBRIDGE_PAIRING_PENDING');
            }
            if ($row->status === 'denied') {
                throw new DomainException('CODEBRIDGE_PAIRING_DENIED');
            }
            if ($row->status !== 'approved' || $row->consumed_at !== null || ! is_string($row->credential_ciphertext)) {
                throw new DomainException('CODEBRIDGE_PAIRING_CONSUMED');
            }
            if (! hash_equals((string) $row->device_id, $deviceId)) {
                throw new DomainException('CODEBRIDGE_PAIRING_INVALID');
            }
            $challenge = rtrim(strtr(base64_encode(hash('sha256', $verifier, true)), '+/', '-_'), '=');
            if (! hash_equals((string) $row->code_challenge, $challenge)) {
                throw new DomainException('CODEBRIDGE_PAIRING_INVALID');
            }

            $credential = Crypt::decryptString($row->credential_ciphertext);
            $permissions = json_decode($row->requested_permissions, true, flags: JSON_THROW_ON_ERROR);
            DB::table('codebridge_device_pairings')->where('id', $row->id)->update([
                'status' => 'consumed',
                'credential_ciphertext' => null,
                'consumed_at' => now(),
                'updated_at' => now(),
            ]);

            $gateway = rtrim((string) config('services.codebridge_gateway.url'), '/');
            if (! preg_match('/\Ahttps:\/\/[^\/?#]+(?::[0-9]{1,5})?\z/D', $gateway)) {
                throw new DomainException('CODEBRIDGE_GATEWAY_UNAVAILABLE');
            }

            // The owner-side onboarding request is informational, NOT an agent grant.
            // Record that the approved agent redeemed its credential; live presence
            // must still be verified separately by an authenticated gateway heartbeat.
            if ($row->project_id === 'kmj-omnidesk'
                && is_string($row->tenant_id)
                && Schema::hasTable('codebridge_project_onboarding_requests')) {
                DB::table('codebridge_project_onboarding_requests')
                    ->where('tenant_id', $row->tenant_id)
                    ->where('project_id', 'kmj-omnidesk')
                    ->where('status', 'awaiting_agent_pairing')
                    ->update([
                        'status' => 'registered_not_live_verified',
                        'updated_at' => now(),
                    ]);
            }

            return [
                'gateway' => $gateway,
                'agent' => [
                    'token' => $credential,
                    'id' => $row->device_id,
                    'tenant' => $row->tenant_id,
                ],
                'projects' => [['id' => $row->project_id]],
                'permissions' => $permissions,
            ];
        }, 3);
    }
}
