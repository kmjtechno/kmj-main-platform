<?php

namespace App\Services\Licensing;

use App\Models\LicenseAuditEvent;

final class LicenseAuditRecorder
{
    /**
     * @param  array<string, mixed>  $metadata
     */
    public function record(
        string $action,
        int|string|null $actorId,
        int|string|null $organizationId,
        ?string $jti,
        string $status,
        array $metadata = [],
    ): void {
        LicenseAuditEvent::query()->create([
            'actor_id' => $actorId,
            'organization_id' => $organizationId,
            'action' => $action,
            'jti' => $jti,
            'status' => $status,
            'metadata' => $metadata === [] ? null : $metadata,
        ]);
    }
}
