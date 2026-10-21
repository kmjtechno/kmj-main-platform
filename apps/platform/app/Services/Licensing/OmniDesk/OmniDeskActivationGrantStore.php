<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

final class OmniDeskActivationGrantStore
{
    /**
     * @param array{
     *   id:string,
     *   organization_id:string,
     *   entitlement_id:string,
     *   device_public_key:string,
     *   device_public_key_fingerprint:string,
     *   installation_id:string
     * } $pairing
     * @return array{grant:string,expires_in:int}
     */
    public function issue(array $pairing, int $now): array
    {
        $grant = rtrim(strtr(base64_encode(random_bytes(48)), '+/', '-_'), '=');
        $expiresIn = 300;

        DB::table('omnidesk_activation_grants')->insert([
            'id' => (string) Str::uuid(),
            'pairing_id' => $pairing['id'],
            'token_hash' => hash('sha256', $grant),
            'organization_id' => $pairing['organization_id'],
            'entitlement_id' => $pairing['entitlement_id'],
            'device_public_key' => $pairing['device_public_key'],
            'device_public_key_fingerprint' => $pairing['device_public_key_fingerprint'],
            'installation_id' => $pairing['installation_id'],
            'expires_at' => gmdate('Y-m-d H:i:s', $now + $expiresIn),
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return ['grant' => $grant, 'expires_in' => $expiresIn];
    }

    /**
     * Consume an activation grant exactly once.
     *
     * @return array{
     *   organization_id:string,
     *   entitlement_id:string,
     *   device_public_key:string,
     *   device_public_key_fingerprint:string,
     *   installation_id:string
     * }
     */
    public function consume(
        string $grant,
        string $deviceFingerprint,
        string $installationId,
        int $now,
    ): array {
        if (strlen($grant) < 64 || strlen($grant) > 128) {
            throw new DomainException('OMNIDESK_ACTIVATION_GRANT_INVALID');
        }

        return DB::transaction(function () use (
            $grant,
            $deviceFingerprint,
            $installationId,
            $now,
        ): array {
            $row = DB::table('omnidesk_activation_grants')
                ->where('token_hash', hash('sha256', $grant))
                ->lockForUpdate()
                ->first();
            if ($row === null
                || $row->consumed_at !== null
                || strtotime((string) $row->expires_at) <= $now
                || ! hash_equals((string) $row->device_public_key_fingerprint, $deviceFingerprint)
                || ! hash_equals((string) $row->installation_id, $installationId)) {
                throw new DomainException('OMNIDESK_ACTIVATION_GRANT_INVALID');
            }

            DB::table('omnidesk_activation_grants')
                ->where('id', $row->id)
                ->update(['consumed_at' => now(), 'updated_at' => now()]);

            return [
                'organization_id' => (string) $row->organization_id,
                'entitlement_id' => (string) $row->entitlement_id,
                'device_public_key' => (string) $row->device_public_key,
                'device_public_key_fingerprint' => (string) $row->device_public_key_fingerprint,
                'installation_id' => (string) $row->installation_id,
            ];
        }, 3);
    }
}
