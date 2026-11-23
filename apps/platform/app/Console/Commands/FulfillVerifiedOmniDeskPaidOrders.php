<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Services\Commerce\OmniDeskVerifiedPaidFulfillment;
use App\Services\Licensing\OmniDeskLicenseContract;
use App\Services\Payments\OmniDeskVerifiedLivePaymentSource;
use DomainException;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use InvalidArgumentException;

final class FulfillVerifiedOmniDeskPaidOrders extends Command
{
    protected $signature = 'licensing:fulfill-omnidesk-paid {--limit=20}';

    protected $description = 'Bounded, verified LIVE settlement to first-party KSLP paid license ledger';

    public function handle(OmniDeskVerifiedPaidFulfillment $fulfillment): int
    {
        if (config('omnidesk-licensing.live_paid_fulfillment_enabled', false) !== true
            || config('payment-providers.live_charging_enabled', false) !== true) {
            $this->line('OMNIDESK_PAID_FULFILLMENT=DISABLED_NO_ISSUANCE');

            return self::SUCCESS;
        }

        if (! app()->bound(OmniDeskVerifiedLivePaymentSource::class)) {
            $this->error('OMNIDESK_PAID_FULFILLMENT=BLOCKED_LIVE_PROVIDER_UNBOUND');

            return self::FAILURE;
        }

        $limit = filter_var(
            $this->option('limit'),
            FILTER_VALIDATE_INT,
            ['options' => ['min_range' => 1, 'max_range' => 100]],
        );
        if ($limit === false) {
            $this->error('OMNIDESK_PAID_FULFILLMENT=INVALID_LIMIT');

            return self::INVALID;
        }

        foreach ([
            'commerce_orders', 'commerce_order_plan_snapshots', 'commerce_provider_orders',
            'payment_webhook_events', 'commerce_paid_fulfillments', 'entitlement_policies',
            'entitlements', 'kslp_licenses', 'kslp_license_events',
        ] as $table) {
            if (! Schema::hasTable($table)) {
                $this->error('OMNIDESK_PAID_FULFILLMENT=SCHEMA_NOT_READY');

                return self::FAILURE;
            }
        }

        // No user-submitted payment reference reaches this worker.
        $product = DB::table('products')
            ->where('slug', OmniDeskLicenseContract::PRODUCT_SLUG)
            ->value('id');
        if ($product === null) {
            $this->line('OMNIDESK_PAID_FULFILLMENT=NO_APPROVED_PRODUCT');

            return self::SUCCESS;
        }

        $orders = DB::table('commerce_orders')
            ->join('commerce_order_plan_snapshots as selected', 'selected.commercial_order_id', '=', 'commerce_orders.id')
            ->leftJoin('commerce_paid_fulfillments as fulfilled', 'fulfilled.commercial_order_id', '=', 'commerce_orders.id')
            ->where('commerce_orders.product_id', $product)
            ->where('commerce_orders.status', 'confirmed')
            ->whereNull('fulfilled.commercial_order_id')
            ->orderBy('commerce_orders.confirmed_at')
            ->limit($limit)
            ->pluck('commerce_orders.id');

        $source = app(OmniDeskVerifiedLivePaymentSource::class);
        $issued = $blocked = 0;
        foreach ($orders as $id) {
            try {
                $result = $fulfillment->fulfill((string) $id, $source);
                if (! $result['already_exists']) {
                    $issued++;
                }
            } catch (DomainException|InvalidArgumentException) {
                // A mismatch is NOT an invitation to fabricate provider facts.
                // The entire transactional fulfillment remains unchanged.
                $blocked++;
            }
        }

        $this->line(sprintf(
            'OMNIDESK_PAID_FULFILLMENT=RECONCILED issued=%d blocked=%d',
            $issued,
            $blocked,
        ));
        $this->line('SIGNED_DEVICE_LEASES=NOT_ISSUED');

        return $blocked === 0 ? self::SUCCESS : self::FAILURE;
    }
}
