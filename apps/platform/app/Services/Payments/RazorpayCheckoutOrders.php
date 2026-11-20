<?php

declare(strict_types=1);

namespace App\Services\Payments;

use DomainException;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;
use KMJ\MainPlatform\Commerce\Models\CommercialOrder;

/**
 * Opens one SANDBOX provider order for a requested commercial order.
 *
 * Reserve the intent in a committed transaction BEFORE outbound HTTP, so a
 * provider-success/DB-failure cannot silently issue a second order on retry.
 * An incomplete intent is fail-closed and requires operator reconciliation.
 * No charge, entitlement or license is created by this service.
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

        // Only the reservation needs a DB lock. Never hold it while waiting
        // on an external payment provider's network response.
        $decision = DB::transaction(function () use ($commercialOrderId, $expectedAmountMinor): array {
            $order = CommercialOrder::query()->whereKey($commercialOrderId)->lockForUpdate()->firstOrFail();
            if ((string) $order->getAttribute('status') !== 'requested') {
                throw new DomainException('RAZORPAY_ORDER_NOT_OPENABLE');
            }

            $existing = DB::table('commerce_provider_orders')
                ->where('commercial_order_id', $commercialOrderId)->where('provider', 'razorpay')->first();
            if ($existing !== null) {
                if ((int) $existing->amount_minor !== $expectedAmountMinor) {
                    throw new DomainException('RAZORPAY_ORDER_AMOUNT_CONFLICT');
                }

                return ['linked' => $this->shape((string) $existing->provider_order_id, (int) $existing->amount_minor, (string) $existing->currency), 'credentials' => null];
            }

            $intent = DB::table('commerce_provider_order_intents')
                ->where('commercial_order_id', $commercialOrderId)->where('provider', 'razorpay')->first();
            if ($intent !== null) {
                if ((int) $intent->amount_minor !== $expectedAmountMinor) {
                    throw new DomainException('RAZORPAY_ORDER_AMOUNT_CONFLICT');
                }

                // A previous external call may have succeeded even if PHP
                // timed out or the subsequent DB link insert failed. Do not
                // call create again without provider-side reconciliation.
                throw new DomainException('RAZORPAY_ORDER_CREATION_PENDING_REVIEW');
            }

            try {
                $credentials = $this->settings->sandboxCredentials('razorpay');
            } catch (InvalidArgumentException) {
                throw new DomainException('RAZORPAY_SANDBOX_CREDENTIALS_NOT_READY');
            }

            DB::table('commerce_provider_order_intents')->insert([
                'commercial_order_id' => $order->getKey(),
                'provider' => 'razorpay',
                'amount_minor' => $expectedAmountMinor,
                'currency' => 'INR',
                'creation_status' => 'creating',
                'created_at' => now(),
                'updated_at' => now(),
            ]);

            return ['linked' => null, 'credentials' => $credentials];
        });

        if ($decision['linked'] !== null) {
            return $decision['linked'];
        }

        $credentials = $decision['credentials'];
        if ($credentials === null) {
            throw new DomainException('RAZORPAY_ORDER_CREATION_PENDING_REVIEW');
        }

        // The reservation has committed and is now durable. On network
        // timeout or DB failure, leave it unresolved; retry must NOT create
        // another provider order from an uncertain remote outcome.
        $created = $this->client->create(
            $commercialOrderId,
            $expectedAmountMinor,
            'INR',
            $credentials['client_id'],
            $credentials['client_secret'],
        );

        return DB::transaction(function () use ($commercialOrderId, $expectedAmountMinor, $created): array {
            $order = CommercialOrder::query()->whereKey($commercialOrderId)->lockForUpdate()->firstOrFail();
            if ((string) $order->getAttribute('status') !== 'requested') {
                throw new DomainException('RAZORPAY_ORDER_NOT_OPENABLE');
            }

            $intent = DB::table('commerce_provider_order_intents')
                ->where('commercial_order_id', $commercialOrderId)->where('provider', 'razorpay')->first();
            if ($intent === null || $intent->creation_status !== 'creating'
                || (int) $intent->amount_minor !== $expectedAmountMinor || $intent->currency !== 'INR') {
                throw new DomainException('RAZORPAY_ORDER_INTENT_MISMATCH');
            }

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

            DB::table('commerce_provider_order_intents')
                ->where('commercial_order_id', $commercialOrderId)->where('provider', 'razorpay')
                ->where('creation_status', 'creating')
                ->update(['creation_status' => 'linked', 'updated_at' => now()]);

            return $this->shape($created['order_id'], $created['amount_minor'], $created['currency']);
        });
    }

    /** @return array{provider_order_id: string, amount_minor: int, currency: string} */
    private function shape(string $providerOrderId, int $amountMinor, string $currency): array
    {
        return ['provider_order_id' => $providerOrderId, 'amount_minor' => $amountMinor, 'currency' => $currency];
    }
}
