<?php

declare(strict_types=1);

namespace App\Services\Licensing\CodeBridge;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Catalog\Services\PlanCatalog;

final class CodeBridgeOwnerTierService
{
    /**
     * Upgrade one existing active CodeBridge license to the internal owner tier.
     * Expiry and activation state are preserved; only the plan and sequence change.
     *
     * @return array{license_id:string,tenant_id:string,plan:string,sequence:int}
     */
    public function upgrade(string $licenseId, string $tenantId, string $actor): array
    {
        return DB::transaction(function () use ($licenseId, $tenantId, $actor): array {
            $license = DB::table('kslp_licenses')
                ->where('id', $licenseId)
                ->where('customer_id', $tenantId)
                ->where('product', 'KMJ_CODEBRIDGE')
                ->lockForUpdate()
                ->first();

            if (
                ! $license
                || $license->status !== 'active'
                || $license->revoked_at !== null
                || strtotime((string) $license->starts_at) > time()
                || strtotime((string) $license->expires_at) <= time()
            ) {
                throw new DomainException('CODEBRIDGE_OWNER_UPGRADE_DENIED');
            }

            $policy = DB::table('plans')
                ->where('code', PlanCatalog::CODEBRIDGE_OWNER_CODE)
                ->where('status', 'active')
                ->first();

            if (! $policy) {
                throw new DomainException('CODEBRIDGE_OWNER_POLICY_UNAVAILABLE');
            }
            $features = json_decode((string) $policy->features, true, 32, JSON_THROW_ON_ERROR);
            $limits = json_decode((string) $policy->limits, true, 32, JSON_THROW_ON_ERROR);
            if (
                $policy->pricing_model !== 'internal'
                || $features !== ['read' => true, 'write' => true, 'execute' => true]
                || $limits !== [
                    'devices' => PlanCatalog::CODEBRIDGE_OWNER_DEVICES,
                    'concurrent_jobs' => PlanCatalog::CODEBRIDGE_OWNER_CONCURRENCY,
                ]
            ) {
                throw new DomainException('CODEBRIDGE_OWNER_POLICY_CONFLICT');
            }

            if ((string) $license->plan === 'owner') {
                return [
                    'license_id' => (string) $license->id,
                    'tenant_id' => (string) $license->customer_id,
                    'plan' => 'owner',
                    'sequence' => (int) $license->sequence,
                ];
            }

            $sequence = (int) $license->sequence + 1;
            DB::table('kslp_licenses')->where('id', $license->id)->update([
                'plan' => 'owner',
                'sequence' => $sequence,
                'updated_at' => now(),
            ]);

            DB::table('kslp_license_events')->insert([
                'license_id' => $license->id,
                'actor_id' => $actor,
                'action' => 'codebridge_owner_tier_upgraded',
                'reason' => 'Platform Owner explicitly upgraded CodeBridge to the internal owner tier',
                'correlation_id' => (string) Str::uuid(),
                'metadata' => json_encode([
                    'previous_plan' => (string) $license->plan,
                    'plan' => 'owner',
                    'policy' => PlanCatalog::CODEBRIDGE_OWNER_CODE,
                    'devices' => PlanCatalog::CODEBRIDGE_OWNER_DEVICES,
                    'concurrent_jobs' => PlanCatalog::CODEBRIDGE_OWNER_CONCURRENCY,
                    'features' => ['read', 'write', 'execute'],
                ], JSON_THROW_ON_ERROR),
                'created_at' => now(),
            ]);

            return [
                'license_id' => (string) $license->id,
                'tenant_id' => (string) $license->customer_id,
                'plan' => 'owner',
                'sequence' => $sequence,
            ];
        }, 3);
    }
}
