<?php

namespace KMJ\MainPlatform\Entitlements\Services;

use DomainException;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;
use KMJ\MainPlatform\Entitlements\Contracts\DomainEventRecorder;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Entitlements\Models\EntitlementLedgerEntry;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;

final class EntitlementIssuer
{
    public function __construct(private readonly DomainEventRecorder $events) {}

    public function issue(
        string $organizationId,
        EntitlementPolicy $policy,
        string $idempotencyKey,
    ): Entitlement {
        $idempotencyKey = trim($idempotencyKey);

        if ($organizationId === '' || $idempotencyKey === '') {
            throw new InvalidArgumentException('Organization and idempotency key are required.');
        }

        if ($policy->status !== 'active') {
            throw new DomainException('Only an active entitlement policy can issue an entitlement.');
        }

        return DB::transaction(function () use ($organizationId, $policy, $idempotencyKey): Entitlement {
            $entitlement = Entitlement::query()->firstOrCreate(
                ['idempotency_key' => $idempotencyKey],
                [
                    'organization_id' => $organizationId,
                    'product_id' => $policy->product_id,
                    'policy_id' => $policy->getKey(),
                    'capability' => $policy->capability,
                    'status' => 'active',
                    'starts_at' => now(),
                    'ends_at' => null,
                ],
            );

            $this->assertIdempotencyMatches($entitlement, $organizationId, $policy);

            if ($entitlement->wasRecentlyCreated) {
                $occurredAt = now();
                $payload = [
                    'product_id' => $policy->product_id,
                    'policy_id' => $policy->getKey(),
                    'capability' => $policy->capability,
                    'status' => 'active',
                ];

                EntitlementLedgerEntry::query()->create([
                    'entitlement_id' => $entitlement->getKey(),
                    'organization_id' => $organizationId,
                    'event_type' => 'entitlement.issued',
                    'payload' => $payload,
                    'occurred_at' => $occurredAt,
                ]);

                $this->events->recordDomainEvent(
                    'entitlement.issued',
                    'entitlement',
                    (string) $entitlement->getKey(),
                    $payload,
                    $organizationId,
                    'entitlement:'.$entitlement->getKey().':issued',
                    $occurredAt,
                );
            }

            return $entitlement;
        });
    }

    private function assertIdempotencyMatches(
        Entitlement $entitlement,
        string $organizationId,
        EntitlementPolicy $policy,
    ): void {
        if (
            $entitlement->organization_id !== $organizationId
            || $entitlement->product_id !== $policy->product_id
            || $entitlement->policy_id !== $policy->getKey()
            || $entitlement->capability !== $policy->capability
        ) {
            throw new DomainException('Idempotency key was already used for a different entitlement request.');
        }
    }
}
