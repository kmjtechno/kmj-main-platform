<?php

namespace KMJ\MainPlatform\Entitlements\Services;

use DomainException;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;
use KMJ\MainPlatform\Entitlements\Contracts\DomainEventRecorder;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Entitlements\Models\EntitlementLedgerEntry;

final class EntitlementRevoker
{
    public function __construct(private readonly DomainEventRecorder $events) {}

    public function revoke(string $entitlementId): Entitlement
    {
        $entitlementId = trim($entitlementId);

        if ($entitlementId === '') {
            throw new InvalidArgumentException('Entitlement id is required.');
        }

        return DB::transaction(function () use ($entitlementId): Entitlement {
            $entitlement = Entitlement::query()
                ->lockForUpdate()
                ->findOrFail($entitlementId);

            if ($entitlement->status === 'revoked') {
                return $entitlement;
            }

            if ($entitlement->status !== 'active') {
                throw new DomainException('Only an active entitlement can be revoked.');
            }

            $endedAt = now();
            $entitlement->forceFill([
                'status' => 'revoked',
                'ends_at' => $endedAt,
            ])->save();

            $payload = [
                'product_id' => $entitlement->product_id,
                'policy_id' => $entitlement->policy_id,
                'capability' => $entitlement->capability,
                'status' => 'revoked',
            ];
            $ledger = EntitlementLedgerEntry::query()->create([
                'entitlement_id' => $entitlement->getKey(),
                'organization_id' => $entitlement->organization_id,
                'event_type' => 'entitlement.revoked',
                'payload' => $payload,
                'occurred_at' => $endedAt,
            ]);

            $this->events->recordDomainEvent(
                eventType: 'entitlement.revoked',
                aggregateType: 'entitlement',
                aggregateId: (string) $entitlement->getKey(),
                organizationId: (string) $entitlement->organization_id,
                payload: [
                    'ledger_sequence' => (int) $ledger->getKey(),
                    'facts' => $payload,
                ],
                idempotencyKey: 'entitlement-ledger:'.$ledger->getKey(),
                occurredAt: $ledger->occurred_at,
            );

            return $entitlement->refresh();
        });
    }
}
