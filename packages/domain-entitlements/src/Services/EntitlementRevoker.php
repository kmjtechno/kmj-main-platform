<?php

namespace KMJ\MainPlatform\Entitlements\Services;

use DomainException;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Entitlements\Models\EntitlementLedgerEntry;

final class EntitlementRevoker
{
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

            EntitlementLedgerEntry::query()->create([
                'entitlement_id' => $entitlement->getKey(),
                'organization_id' => $entitlement->organization_id,
                'event_type' => 'entitlement.revoked',
                'payload' => [
                    'product_id' => $entitlement->product_id,
                    'policy_id' => $entitlement->policy_id,
                    'capability' => $entitlement->capability,
                    'status' => 'revoked',
                ],
                'occurred_at' => $endedAt,
            ]);

            return $entitlement->refresh();
        });
    }
}
