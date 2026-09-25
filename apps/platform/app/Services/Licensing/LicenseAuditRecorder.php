<?php

namespace App\Services\Licensing;

use App\Models\LicenseAuditEvent;
use App\Services\Events\TransactionalOutbox;
use Illuminate\Support\Facades\DB;

final class LicenseAuditRecorder
{
    public function __construct(private readonly TransactionalOutbox $outbox) {}

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
        DB::transaction(function () use ($action, $actorId, $organizationId, $jti, $status, $metadata): void {
            $event = LicenseAuditEvent::query()->create([
                'actor_id' => $actorId,
                'organization_id' => $organizationId,
                'action' => $action,
                'jti' => $jti,
                'status' => $status,
                'metadata' => $metadata === [] ? null : $metadata,
            ]);

            $this->outbox->record(
                eventType: $action,
                aggregateType: 'sandbox_license',
                aggregateId: $jti ?? 'audit:'.$event->getKey(),
                organizationId: $organizationId === null ? null : (string) $organizationId,
                payload: [
                    'audit_event_id' => $event->getKey(),
                    'actor_id' => $actorId,
                    'organization_id' => $organizationId,
                    'jti' => $jti,
                    'status' => $status,
                    'metadata' => $metadata,
                ],
                idempotencyKey: 'license-audit:'.$event->getKey(),
                occurredAt: $event->created_at,
            );
        });
    }
}
