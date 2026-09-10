<?php

namespace KMJ\MainPlatform\Entitlements\Services;

use KMJ\MainPlatform\Entitlements\Models\Entitlement;

final class EntitlementReader
{
    /**
     * @return list<array{id: string, product_id: string, capability: string, status: string, starts_at: string}>
     */
    public function forOrganization(string $organizationId): array
    {
        return Entitlement::query()
            ->where('organization_id', $organizationId)
            ->orderByDesc('created_at')
            ->get()
            ->map(fn (Entitlement $entitlement): array => [
                'id' => (string) $entitlement->getKey(),
                'product_id' => (string) $entitlement->product_id,
                'capability' => (string) $entitlement->capability,
                'status' => (string) $entitlement->status,
                'starts_at' => $entitlement->starts_at->toIso8601String(),
            ])
            ->values()
            ->all();
    }
}
