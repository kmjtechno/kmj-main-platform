<?php

namespace KMJ\MainPlatform\Entitlements\Contracts;

use DateTimeInterface;

interface DomainEventRecorder
{
    /**
     * @param  array<string, mixed>  $payload
     */
    public function recordDomainEvent(
        string $eventType,
        string $aggregateType,
        string $aggregateId,
        array $payload,
        ?string $organizationId,
        string $idempotencyKey,
        DateTimeInterface $occurredAt,
    ): void;
}
