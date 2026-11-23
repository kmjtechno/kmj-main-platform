<?php

declare(strict_types=1);

namespace App\Services\Commerce;

use App\Models\User;
use App\Services\Licensing\OmniDeskLicenseContract;
use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Catalog\Models\Plan;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Models\CommercialOrder;
use KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext;

/**
 * Locks buyer-selected catalog plan, currency, price and billing term BEFORE
 * any provider order is created. A confirmed generic order is never enough
 * to infer which software subscription a payment buys.
 *
 * This class does NOT capture money, fulfill entitlements or issue licenses.
 */
final class OmniDeskOrderPlanBinder
{
    private const PERMITTED_PLANS = [
        'omnidesk.professional',
        'omnidesk.business',
        'omnidesk.enterprise',
    ];

    private const PERMITTED_INTERVALS = ['monthly', 'yearly'];

    public function __construct(private readonly OrganizationCapabilityContext $capabilities) {}

    /**
     * @return array{commercial_order_id:string,plan_id:string,plan_code:string,currency:string,amount_minor:int,billing_interval:string}
     */
    public function bind(User $actor, string $orderId, string $planId): array
    {
        if (config('omnidesk-licensing.paid_plan_binding_enabled', false) !== true) {
            throw new DomainException('OMNIDESK_PLAN_BINDING_DISABLED');
        }
        if (! $actor->exists || ! $actor->hasVerifiedEmail()
            || ! Str::isUuid($orderId) || ! Str::isUuid($planId)) {
            throw new DomainException('OMNIDESK_PLAN_BINDING_FORBIDDEN');
        }

        return DB::transaction(function () use ($actor, $orderId, $planId): array {
            $order = CommercialOrder::query()->whereKey($orderId)->lockForUpdate()->first();
            if (! $order instanceof CommercialOrder
                || $order->getAttribute('status') !== 'requested'
                || (int) $order->getAttribute('requester_user_id') !== (int) $actor->getKey()) {
                throw new DomainException('OMNIDESK_PLAN_BINDING_FORBIDDEN');
            }

            $organizationId = (string) $order->getAttribute('organization_id');
            if (! $this->capabilities->allows((int) $actor->getKey(), $organizationId, 'commerce.purchase')) {
                throw new DomainException('OMNIDESK_PLAN_BINDING_FORBIDDEN');
            }

            $product = Product::query()->whereKey($order->getAttribute('product_id'))
                ->where('slug', OmniDeskLicenseContract::PRODUCT_SLUG)
                ->lockForUpdate()->first();
            if (! $product instanceof Product
                || $product->getAttribute('status') !== 'active'
                || ! $product->getAttribute('is_public')
                || ! $product->getAttribute('licensing_enabled')
                || ! $product->getAttribute('purchase_enabled')
                || ! in_array($product->getAttribute('lifecycle'), ['available', 'public-beta'], true)) {
                throw new DomainException('OMNIDESK_PLAN_NOT_APPROVED');
            }

            $plan = Plan::query()
                ->whereKey($planId)->where('product_id', $product->getKey())
                ->whereIn('code', self::PERMITTED_PLANS)
                ->where('status', 'active')
                ->where('pricing_model', 'subscription')
                ->whereIn('billing_interval', self::PERMITTED_INTERVALS)
                ->lockForUpdate()->first();

            if (! $plan instanceof Plan
                || $plan->getAttribute('currency') !== 'INR'
                || ! is_int($plan->getAttribute('amount_minor'))
                || $plan->getAttribute('amount_minor') < 100
                || $plan->getAttribute('amount_minor') > 100000000
                || (int) $plan->getAttribute('trial_days') !== 0) {
                throw new DomainException('OMNIDESK_PLAN_NOT_APPROVED');
            }

            $snapshot = [
                'commercial_order_id' => $orderId,
                'organization_id' => $organizationId,
                'product_id' => (string) $product->getKey(),
                'plan_id' => (string) $plan->getKey(),
                'plan_code' => (string) $plan->getAttribute('code'),
                'currency' => (string) $plan->getAttribute('currency'),
                'amount_minor' => (int) $plan->getAttribute('amount_minor'),
                'billing_interval' => (string) $plan->getAttribute('billing_interval'),
            ];

            $existingRow = DB::table('commerce_order_plan_snapshots')
                ->where('commercial_order_id', $orderId)->lockForUpdate()->first();
            if ($existingRow !== null) {
                /** @var array<string,mixed> $existing */
                $existing = (array) $existingRow;
                foreach ($snapshot as $key => $value) {
                    if ((string) ($existing[$key] ?? '') !== (string) $value) {
                        throw new DomainException('OMNIDESK_PLAN_BINDING_CONFLICT');
                    }
                }

                return $this->shape($snapshot);
            }

            // Forbid rewriting the plan after a provider has seen any order
            // for this commercial checkout, regardless of provider/currency.
            if (DB::table('commerce_provider_orders')
                ->where('commercial_order_id', $orderId)->exists()) {
                throw new DomainException('OMNIDESK_CHECKOUT_ALREADY_OPEN');
            }

            $now = now();
            DB::table('commerce_order_plan_snapshots')
                ->insert($snapshot + ['created_at' => $now, 'updated_at' => $now]);

            return $this->shape($snapshot);
        }, 3);
    }

    /**
     * @param array<string,string|int> $snapshot
     * @return array{commercial_order_id:string,plan_id:string,plan_code:string,currency:string,amount_minor:int,billing_interval:string}
     */
    private function shape(array $snapshot): array
    {
        return [
            'commercial_order_id' => (string) $snapshot['commercial_order_id'],
            'plan_id' => (string) $snapshot['plan_id'],
            'plan_code' => (string) $snapshot['plan_code'],
            'currency' => (string) $snapshot['currency'],
            'amount_minor' => (int) $snapshot['amount_minor'],
            'billing_interval' => (string) $snapshot['billing_interval'],
        ];
    }
}
