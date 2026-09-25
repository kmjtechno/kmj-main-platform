<?php

namespace App\Services\Events;

use App\Models\DomainOutboxMessage;
use DateTimeInterface;
use DomainException;
use Illuminate\Support\Str;
use InvalidArgumentException;

final class TransactionalOutbox
{
    /**
     * @param array<string, mixed> $payload
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

        if (
            $message->event_type !== $eventType
            || $message->aggregate_type !== $aggregateType
            || $message->aggregate_id !== $aggregateId
            || $message->organization_id !== $organizationId
            || $message->payload !== $payload
        ) {
            throw new DomainException('Outbox idempotency key was already used for a different event.');
        }

        return $message;
    }
}
