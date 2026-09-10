<?php

namespace KMJ\MainPlatform\Entitlements\Services;

use InvalidArgumentException;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;

final class EntitlementPolicyRegistry
{
    public function ensure(string $productId, string $code, string $capability): EntitlementPolicy
    {
        $code = trim($code);
        $capability = trim($capability);

        if ($productId === '' || $code === '' || $capability === '') {
            throw new InvalidArgumentException('Product, policy code and capability are required.');
        }

        return EntitlementPolicy::query()->firstOrCreate(
            ['code' => $code],
            [
                'product_id' => $productId,
                'capability' => $capability,
                'status' => 'active',
            ],
        );
    }
}
