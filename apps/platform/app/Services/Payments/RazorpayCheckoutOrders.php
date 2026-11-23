<?php

declare(strict_types=1);

namespace App\Services\Payments;

use App\Services\Licensing\OmniDeskLicenseContract;
use DomainException;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;
use KMJ\MainPlatform\Commerce\Models\CommercialOrder;

/**
 * Opens (once) a Razorpay SANDBOX order for a requested commercial order and records the
 * binding. The expected amount is a server-supplied fact, never read from a browser.
 * No payment is taken and no entitlement or license is granted here.
 */
final class RazorpayCheckoutOrders
{
    public function __construct(
        private readonly OwnerPaymentGatewaySettings $settings,
        private readonly RazorpaySandboxOrderClient $client,
    ) {}

    /**
     * @return array{provider_order_id: string, amount_minor: int, currency: string}
     */
    public function open(string $commercialOrderId, int $expectedAmountMinor): array
    {
        if ($expectedAmountMinor < 100 || $expectedAmountMinor > 100000000) {
            throw new InvalidArgumentException('RAZORPAY_EXPECTED_AMOUNT_INVALID');
        }

        return DB::transaction(function () use ($commercialOrderId, $expectedAmountMinor): array {
            $order = CommercialOrder::query()->whereKey($commercialOrderId)->lockForUpdate()->firstOrFail();
            if ((string) $order->getAttribute('status') !== 'requested') {
                throw new DomainException('RAZORPAY_ORDER_NOT_OPENABLE');
            }

            // OmniDesk paid checkouts MUST have an immutable, server-approved
            // plan/price/term before any payment provider order is created.
            // Do not infer a subscription from client-supplied amounts.
            $omniDeskProductId = DB::table('products')
                ->where('slug', OmniDeskLicenseContract::PRODUCT_SLUG)
                ->value('id');
            if ($omniDeskProductId !== null
                && (string) $order->getAttribute('product_id') === (string) $omniDeskProductId) {
                $snapshot = DB::table('commerce_order_plan_snapshots')
                    ->where('commercial_order_id', $commercialOrderId)->first();
                if ($snapshot === null
                    || (string) $snapshot->product_id !== (string) $omniDeskProductId
                    || (string) $snapshot->organization_id !== (string) $order->getAttribute('organization_id')
                    || (int) $snapshot->amount_minor !== $expectedAmountMinor
                    || (string) $snapshot->currency !== 'INR') {
                    throw new DomainException('OMNIDESK_CHECKOUT_PLAN_OR_PRICE_MISMATCH');
                }
            }

            $existing = DB::table('commerce_provider_orders')
                ->where('commercial_order_id', $commercialOrderId)->where('provider', 'razorpay')->first();
            if ($existing !== null) {
                if ((int) $existing->amount_minor !== $expectedAmountMinor) {
                    throw new DomainException('RAZORPAY_ORDER_AMOUNT_CONFLICT');
                }

                return $this->shape($existing->provider_order_id, (int) $existing->amount_minor, (string) $existing->currency);
            }

            try {
                $credentials = $this->settings->sandboxCredentials('razorpay');
            } catch (InvalidArgumentException) {
                throw new DomainException('RAZORPAY_SANDBOX_CREDENTIALS_NOT_READY');
            }

            // The commercial order id is the receipt, so provider records trace back to our order.
            $created = $this->client->create(
                (string) $order->getKey(),
                $expectedAmountMinor,
                'INR',
                $credentials['client_id'],
                $credentials['client_secret'],
            );

            DB::table('commerce_provider_orders')->insert([
                'commercial_order_id' => $order->getKey(),
                'provider' => 'razorpay',
                'provider_order_id' => $created['order_id'],
                'amount_minor' => $created['amount_minor'],
                'currency' => $created['currency'],
                'environment' => 'sandbox',
                'created_at' => now(),
                'updated_at' => now(),
            ]);

            return $this->shape($created['order_id'], $created['amount_minor'], $created['currency']);
        });
    }

    /** @return array{provider_order_id: string, amount_minor: int, currency: string} */
    private function shape(string $providerOrderId, int $amountMinor, string $currency): array
    {
        return ['provider_order_id' => $providerOrderId, 'amount_minor' => $amountMinor, 'currency' => $currency];
    }
}
