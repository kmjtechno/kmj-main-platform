<?php

namespace App\Services\Events;

use App\Models\DomainOutboxMessage;
use DateTimeInterface;
use DomainException;
use Illuminate\Support\Str;
use InvalidArgumentException;
use KMJ\MainPlatform\Commerce\Contracts\DomainEventRecorder as CommerceDomainEventRecorder;
use KMJ\MainPlatform\Entitlements\Contracts\DomainEventRecorder as EntitlementDomainEventRecorder;

final class TransactionalOutbox implements CommerceDomainEventRecorder, EntitlementDomainEventRecorder
{
    public function recordDomainEvent(
        string $eventType,
        string $aggregateType,
        string $aggregateId,
        array $payload,
        ?string $organizationId,
        string $idempotencyKey,
        DateTimeInterface $occurredAt,
    ): void {
        $this->record(
            $eventType,
            $aggregateType,
            $aggregateId,
            $payload,
            $organizationId,
            $idempotencyKey,
            $occurredAt,
        );
    }

    /**
     * @param  array<string, mixed>  $payload
     */
    public function record(
        string $eventType,
        string $aggregateType,
        int|string $aggregateId,
        array $payload,
        ?string $organizationId = null,
        ?string $idempotencyKey = null,
        ?DateTimeInterface $occurredAt = null,
    ): DomainOutboxMessage {
        $eventType = trim($eventType);
        $aggregateType = trim($aggregateType);
        $aggregateId = trim((string) $aggregateId);
        $idempotencyKey = trim($idempotencyKey ?? (string) Str::uuid());

        if ($eventType === '' || $aggregateType === '' || $aggregateId === '' || $idempotencyKey === '') {
            throw new InvalidArgumentException('Outbox event, aggregate and idempotency key are required.');
        }

        $message = DomainOutboxMessage::query()->firstOrCreate(
            ['idempotency_key' => $idempotencyKey],
            [
                'id' => (string) Str::uuid(),
                'event_type' => $eventType,
                'aggregate_type' => $aggregateType,
                'aggregate_id' => $aggregateId,
                'organization_id' => $organizationId,
                'payload' => $payload,
                'occurred_at' => $occurredAt ?? now(),
            ],
        );

        $existingPayload = $message->getAttribute('payload');

        if (
            $message->getAttribute('event_type') !== $eventType
            || $message->getAttribute('aggregate_type') !== $aggregateType
            || $message->getAttribute('aggregate_id') !== $aggregateId
            || $message->getAttribute('organization_id') !== $organizationId
            || ! is_array($existingPayload)
            || $existingPayload !== $payload
        ) {
            throw new DomainException('Outbox idempotency key was already used for a different event.');
        }

        return $message;
    }
}
