<?php

declare(strict_types=1);

namespace App\Services\Licensing\CodeBridge;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

final class CodeBridgeOwnerPlanService
{
    public const PLAN = 'owner_admin';
    public const DEVICE_LIMIT = 2147483647;
    public const CONCURRENT_JOBS = 16;

    /**
     * Promote an existing, active CodeBridge Professional license without
     * re-enrolling devices, changing activation identities, or minting a lease.
     * This method must only be called from the platform-owner protected route.
     *
     * @return array{license_id:string,plan:string,devices:int,concurrent_jobs:int,changed:bool}
     */
    public function activate(string $licenseId, string $tenantId, string $actor, string $reason): array
    {
        if (! preg_match('/\A[A-Za-z0-9_-]{1,64}\z/D', $tenantId) || strlen(trim($reason)) < 10) {
            throw new DomainException('CODEBRIDGE_OWNER_REQUEST_INVALID');
        }

        return DB::transaction(function () use ($licenseId, $tenantId, $actor, $reason): array {
            $license = DB::table('kslp_licenses')->where('id', $licenseId)->lockForUpdate()->first();
            $now = now();

            if (! $license
                || $license->product !== 'KMJ_CODEBRIDGE'
                || $license->customer_id !== $tenantId
                || $license->status !== 'active'
                || $license->revoked_at !== null
                || $license->starts_at > $now
                || $license->expires_at <= $now
                || ! in_array($license->plan, ['professional', self::PLAN], true)) {
                throw new DomainException('CODEBRIDGE_OWNER_LICENSE_NOT_ELIGIBLE');
            }

            $product = DB::table('products')->where('slug', 'codebridge')->where('status', 'active')->first();
            if (! $product || ! $product->licensing_enabled) {
                throw new DomainException('CODEBRIDGE_OWNER_PRODUCT_UNAVAILABLE');
            }

            $code = 'codebridge.'.self::PLAN;
            $features = ['read' => true, 'write' => true, 'execute' => true];
            $limits = ['devices' => self::DEVICE_LIMIT, 'concurrent_jobs' => self::CONCURRENT_JOBS];

            DB::table('plans')->insertOrIgnore([
                'id' => (string) Str::uuid(),
                'product_id' => $product->id,
                'code' => $code,
                'name' => 'KMJ CodeBridge Owner/Admin',
                'pricing_model' => 'license',
                'status' => 'active',
                'trial_days' => 0,
                'features' => json_encode($features, JSON_THROW_ON_ERROR),
                'limits' => json_encode($limits, JSON_THROW_ON_ERROR),
                'created_at' => $now,
                'updated_at' => $now,
            ]);

            $policy = DB::table('plans')->where('code', $code)->first();
            if (! $policy
                || $policy->product_id !== $product->id
                || $policy->status !== 'active'
                || json_decode((string) $policy->features, true) !== $features
                || json_decode((string) $policy->limits, true) !== $limits) {
                throw new DomainException('CODEBRIDGE_OWNER_POLICY_CONFLICT');
            }

            $changed = $license->plan !== self::PLAN;
            if ($changed) {
                DB::table('kslp_licenses')->where('id', $licenseId)->update([
                    'plan' => self::PLAN,
                    'sequence' => DB::raw('sequence + 1'),
                    'updated_at' => $now,
                ]);
                DB::table('kslp_license_events')->insert([
                    'license_id' => $licenseId,
                    'actor_id' => $actor,
                    'action' => 'codebridge_owner_plan_activated',
                    'reason' => trim($reason),
                    'correlation_id' => (string) Str::uuid(),
                    'metadata' => json_encode([
                        'from' => 'professional',
                        'to' => self::PLAN,
                        'devices' => self::DEVICE_LIMIT,
                        'concurrent_jobs' => self::CONCURRENT_JOBS,
                    ], JSON_THROW_ON_ERROR),
                    'created_at' => $now,
                ]);
            }

            return [
                'license_id' => $licenseId,
                'plan' => self::PLAN,
                'devices' => self::DEVICE_LIMIT,
                'concurrent_jobs' => self::CONCURRENT_JOBS,
                'changed' => $changed,
            ];
        }, 3);
    }
}
