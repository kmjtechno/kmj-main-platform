<?php

declare(strict_types=1);

namespace App\Services\Licensing\Kslp;

use DomainException;

/**
 * Pure activation-record identity check shared by idempotent retries and
 * existing-seat reuse. It does not query the database or consume a proof.
 */
final class KslpActivationReplayGuard
{
    /** @param array<array-key, mixed> $activation */
    public static function requireMatch(array $activation, string $licenseId, string $serverIdentity, string $machineHash): void
    {
        if ($licenseId === '' || $serverIdentity === '' || $machineHash === ''
            || ! hash_equals($licenseId, (string) ($activation['license_id'] ?? ''))
            || ! hash_equals($serverIdentity, (string) ($activation['server_identity'] ?? ''))
            || ! hash_equals($machineHash, (string) ($activation['machine_identity_hash'] ?? ''))
            || ($activation['deactivated_at'] ?? null) !== null) {
            throw new DomainException('KSLP_ACTIVATION_CONFLICT');
        }
    }
}
