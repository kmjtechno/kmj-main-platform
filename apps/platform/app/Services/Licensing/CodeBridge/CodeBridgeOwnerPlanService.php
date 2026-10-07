<?php

declare(strict_types=1);

namespace App\Services\Licensing\CodeBridge;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

/**
 * Owner-managed CodeBridge plan. Never issues a lease, credential or privilege
 * directly: the existing authenticated KSLP renewal signs device-bound claims.
 */
final class CodeBridgeOwnerPlanService
{
    public const PLAN = 'admin';

    public const LIMITS = [
        'devices' => 2147483647,
        'concurrent_jobs' => 16,
    ];

    public const FEATURES = [
        'read' => true,
        'write' => true,
        'execute' => true,
    ];

    /** @return array{license_id:string,tenant_id:string,plan:string,sequence:int,changed:bool} */
    public function upgrade(string $licenseId, string $tenantId, string $actorId, string $reason): array
    {
        if (strlen(trim($reason)) < 10 || strlen($reason) > 500) {
            throw new DomainException('CODEBRIDGE_ADMIN_REASON_REQUIRED');
        }

        return DB::transaction(function () use ($licenseId, $tenantId, $actorId, $reason): array {
            $license = DB::table('kslp_licenses')
                ->where('id', $licenseId)
                ->where('customer_id', $tenantId)
                ->where('product', 'KMJ_CODEBRIDGE')
                ->lockForUpdate()
                ->first();

            if (! $license || $license->status !== 'active' || $license->revoked_at !== null
                || strtotime($license->starts_at) > time() || strtotime($license->expires_at) <= time()) {
                throw new DomainException('CODEBRIDGE_ADMIN_LICENSE_UNAVAILABLE');
            }
            if (! in_array($license->plan, ['professional', 'admin'], true)) {
                throw new DomainException('CODEBRIDGE_ADMIN_PLAN_TRANSITION_DENIED');
            }

            $product = DB::table('products')->where('slug', 'codebridge')->where('status', 'active')->first();
            if (! $product) {
                throw new DomainException('CODEBRIDGE_ADMIN_PRODUCT_UNAVAILABLE');
            }

            $code = 'codebridge.'.self::PLAN;
            $policy = DB::table('plans')->where('code', $code)->first();
            if (! $policy) {
                DB::table('plans')->insert([
                    'id' => (string) Str::uuid(),
                    'product_id' => $product->id,
                    'code' => $code,
                    'name' => 'CodeBridge Owner Admin',
                    'pricing_model' => 'license',
                    'status' => 'active',
                    'trial_days' => 0,
                    'features' => json_encode(self::FEATURES, JSON_THROW_ON_ERROR),
                    'limits' => json_encode(self::LIMITS, JSON_THROW_ON_ERROR),
                    'created_at' => now(),
                    'updated_at' => now(),
                ]);
            } elseif ($policy->product_id !== $product->id
                || $policy->status !== 'active'
                || json_decode((string) $policy->features, true) !== self::FEATURES
                || json_decode((string) $policy->limits, true) !== self::LIMITS) {
                throw new DomainException('CODEBRIDGE_ADMIN_POLICY_CONFLICT');
            }

            $changed = $license->plan !== self::PLAN;
            if ($changed) {
                DB::table('kslp_licenses')->where('id', $licenseId)->update([
                    'plan' => self::PLAN,
                    'sequence' => DB::raw('sequence + 1'),
                    'updated_at' => now(),
                ]);
                DB::table('kslp_license_events')->insert([
                    'license_id' => $licenseId,
                    'actor_id' => $actorId,
                    'action' => 'codebridge_owner_admin_upgraded',
                    'reason' => trim($reason),
                    'correlation_id' => (string) Str::uuid(),
                    'metadata' => json_encode([
                        'from' => 'professional',
                        'to' => self::PLAN,
                        'tenant_id' => $tenantId,
                    ], JSON_THROW_ON_ERROR),
                    'created_at' => now(),
                ]);
            }

            return [
                'license_id' => $licenseId,
                'tenant_id' => $tenantId,
                'plan' => self::PLAN,
                'sequence' => (int) DB::table('kslp_licenses')->where('id', $licenseId)->value('sequence'),
                'changed' => $changed,
            ];
        }, 3);
    }
}
