<?php

namespace App\Services\Licensing\Kslp;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

final class KslpIssuerSubscriptionAuthority
{
    public const TIERS = ['professional', 'business', 'enterprise', 'custom_oem'];

    public function subscribe(
        string $organizationId,
        string $tier,
        int $productLimit,
        int $monthlyIssueLimit,
        ?\DateTimeInterface $periodEnd = null,
    ): array {
        if (! in_array($tier, self::TIERS, true)) {
            throw new DomainException('KSLP_INVALID_ISSUER_TIER');
        }
        if ($productLimit < 1 || $monthlyIssueLimit < 1) {
            throw new DomainException('KSLP_ISSUER_POLICY_NOT_CONFIGURED');
        }

        return DB::transaction(function () use ($organizationId, $tier, $productLimit, $monthlyIssueLimit, $periodEnd): array {
            $now = now();
            $existing = DB::table('kslp_issuer_subscriptions')
                ->where('organization_id', $organizationId)
                ->lockForUpdate()
                ->first();

            $values = [
                'tier' => $tier,
                'status' => 'active',
                'product_limit' => $productLimit,
                'monthly_issue_limit' => $monthlyIssueLimit,
                'current_period_end' => $periodEnd,
                'updated_at' => $now,
            ];

            if ($existing) {
                DB::table('kslp_issuer_subscriptions')->where('id', $existing->id)->update($values);
            } else {
                DB::table('kslp_issuer_subscriptions')->insert([
                    'id' => (string) Str::uuid(),
                    'organization_id' => $organizationId,
                    ...$values,
                    'created_at' => $now,
                ]);
            }

            return (array) DB::table('kslp_issuer_subscriptions')
                ->where('organization_id', $organizationId)
                ->first();
        }, 3);
    }

    public function registerProduct(
        string $organizationId,
        string $code,
        string $name,
        array $features = [],
        array $limits = [],
    ): array {
        if (! preg_match('/^[A-Z0-9][A-Z0-9_.:-]{2,95}$/', $code)) {
            throw new DomainException('KSLP_INVALID_PRODUCT_CODE');
        }

        return DB::transaction(function () use ($organizationId, $code, $name, $features, $limits): array {
            $sub = DB::table('kslp_issuer_subscriptions')
                ->where('organization_id', $organizationId)
                ->lockForUpdate()
                ->first();

            $this->assertActive($sub);

            $count = DB::table('kslp_licensed_products')
                ->where('organization_id', $organizationId)
                ->count();

            if ($count >= (int) $sub->product_limit) {
                throw new DomainException('KSLP_ISSUER_PRODUCT_LIMIT');
            }

            $id = (string) Str::uuid();
            $now = now();

            DB::table('kslp_licensed_products')->insert([
                'id' => $id,
                'organization_id' => $organizationId,
                'product_code' => $code,
                'name' => $name,
                'status' => 'active',
                'default_features' => json_encode($features, JSON_THROW_ON_ERROR),
                'default_limits' => json_encode($limits, JSON_THROW_ON_ERROR),
                'created_at' => $now,
                'updated_at' => $now,
            ]);

            return (array) DB::table('kslp_licensed_products')->where('id', $id)->first();
        }, 3);
    }

    public function authorizeIssue(string $organizationId, string $productCode): array
    {
        $this->requireActive($organizationId);

        $product = DB::table('kslp_licensed_products')
            ->where('organization_id', $organizationId)
            ->where('product_code', $productCode)
            ->where('status', 'active')
            ->first();

        if (! $product) {
            throw new DomainException('KSLP_ISSUER_PRODUCT_NOT_AUTHORIZED');
        }

        return (array) $product;
    }

    private function requireActive(string $organizationId): object
    {
        $subscription = DB::table('kslp_issuer_subscriptions')
            ->where('organization_id', $organizationId)
            ->first();

        $this->assertActive($subscription);

        return $subscription;
    }

    private function assertActive(?object $subscription): void
    {
        if (! $subscription || $subscription->status !== 'active') {
            throw new DomainException('KSLP_ISSUER_SUBSCRIPTION_REQUIRED');
        }

        if ($subscription->current_period_end && now()->gt($subscription->current_period_end)) {
            throw new DomainException('KSLP_ISSUER_SUBSCRIPTION_EXPIRED');
        }
    }
}
