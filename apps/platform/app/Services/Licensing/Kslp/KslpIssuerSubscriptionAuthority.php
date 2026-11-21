<?php

namespace App\Services\Licensing\Kslp;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

final class KslpIssuerSubscriptionAuthority
{
    public const TIERS = ['professional', 'business', 'enterprise', 'custom_oem'];

    /**
     * @return array<array-key, mixed>
     */
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

    /**
     * @param  array<array-key, mixed>  $features
     * @param  array<array-key, mixed>  $limits
     * @return array<array-key, mixed>
     */
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

            // Product codes are globally unique in the current schema.
            // Explain duplicates as a user-correctable validation error
            // instead of relying on an opaque database constraint failure.
            if (DB::table('kslp_licensed_products')->where('product_code', $code)->exists()) {
                throw new DomainException('KSLP_PRODUCT_CODE_TAKEN');
            }

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

    /**
     * Rename or suspend one issuer application without changing its immutable
     * product code or existing signed-license records.
     *
     * All mutations are serialized on the issuer row. The delegated-issue
     * transaction also locks that row and rechecks active product status,
     * so a pause cannot race a new key into existence after it commits.
     *
     * @return array<array-key, mixed>
     */
    public function manageProduct(
        string $organizationId,
        string $productId,
        string $operation,
        ?string $name,
        string $reason,
        int $actorId,
    ): array {
        if (! in_array($operation, ['rename', 'pause', 'resume'], true)) {
            throw new DomainException('KSLP_PRODUCT_ACTION_INVALID');
        }

        $reason = trim($reason);
        if (mb_strlen($reason) < 8 || mb_strlen($reason) > 240) {
            throw new DomainException('KSLP_PRODUCT_REASON_REQUIRED');
        }

        $nextName = $name === null ? null : trim($name);
        if ($operation === 'rename'
            && ($nextName === null || mb_strlen($nextName) < 2 || mb_strlen($nextName) > 160)) {
            throw new DomainException('KSLP_PRODUCT_NAME_INVALID');
        }

        return DB::transaction(function () use (
            $organizationId, $productId, $operation, $nextName, $reason, $actorId,
        ): array {
            $issuer = DB::table('kslp_issuer_subscriptions')
                ->where('organization_id', $organizationId)
                ->lockForUpdate()
                ->first();

            // A suspended / expired issuer may still shut an app down.
            // But renaming or reopening requires an active, unexpired issuer.
            if ($operation !== 'pause') {
                $this->assertActive($issuer);
            }

            $product = DB::table('kslp_licensed_products')
                ->where('organization_id', $organizationId)
                ->where('id', $productId)
                ->lockForUpdate()
                ->first();

            if ($product === null) {
                throw new DomainException('KSLP_ISSUER_PRODUCT_NOT_AUTHORIZED');
            }
            if (! in_array($product->status, ['active', 'paused'], true)) {
                throw new DomainException('KSLP_PRODUCT_STATE_UNRECOGNIZED');
            }

            $oldStatus = (string) $product->status;
            $oldName = (string) $product->name;
            $newStatus = match ($operation) {
                'pause' => 'paused',
                'resume' => 'active',
                default => $oldStatus,
            };
            $newName = $operation === 'rename' ? $nextName : $oldName;

            // Exact retry is idempotent and does not spam the audit ledger.
            if ($oldStatus === $newStatus && $oldName === $newName) {
                return (array) $product;
            }

            DB::table('kslp_licensed_products')
                ->where('organization_id', $organizationId)
                ->where('id', $productId)
                ->update([
                    'name' => $newName,
                    'status' => $newStatus,
                    'updated_at' => now(),
                ]);

            // A failed audit insert rolls back the state change. No plaintext
            // license keys, device fingerprints, or secrets are recorded.
            $now = now();
            DB::table('license_audit_events')->insert([
                'actor_id' => $actorId,
                'organization_id' => $organizationId,
                'action' => 'kslp_product_'.$operation,
                'status' => 'success',
                'metadata' => json_encode([
                    'product_id' => $productId,
                    'product_code' => (string) $product->product_code,
                    'old_status' => $oldStatus,
                    'new_status' => $newStatus,
                    'old_name' => $oldName,
                    'new_name' => $newName,
                    'reason' => $reason,
                ], JSON_THROW_ON_ERROR),
                'created_at' => $now,
                'updated_at' => $now,
            ]);

            return (array) DB::table('kslp_licensed_products')
                ->where('organization_id', $organizationId)
                ->where('id', $productId)
                ->first();
        }, 3);
    }

    /**
     * @return array<array-key, mixed>
     */
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

    private function requireActive(string $organizationId): \stdClass
    {
        $subscription = DB::table('kslp_issuer_subscriptions')
            ->where('organization_id', $organizationId)
            ->first();

        $this->assertActive($subscription);

        return $subscription;
    }

    private function assertActive(?\stdClass $subscription): void
    {
        if (! $subscription || $subscription->status !== 'active') {
            throw new DomainException('KSLP_ISSUER_SUBSCRIPTION_REQUIRED');
        }

        if ($subscription->current_period_end && now()->gt($subscription->current_period_end)) {
            throw new DomainException('KSLP_ISSUER_SUBSCRIPTION_EXPIRED');
        }
    }
}
