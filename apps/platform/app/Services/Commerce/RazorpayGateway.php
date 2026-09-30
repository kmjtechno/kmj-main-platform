<?php

namespace App\Services\Commerce;

use App\Models\RazorpayPaymentAttempt;
use DomainException;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use InvalidArgumentException;
use KMJ\MainPlatform\Catalog\Models\Plan;
use KMJ\MainPlatform\Commerce\Contracts\PaymentProviderAdapter;
use KMJ\MainPlatform\Commerce\Models\CommercialOrder;
use KMJ\MainPlatform\Commerce\ValueObjects\ProviderPaymentConfirmation;
use Throwable;

final class RazorpayGateway implements PaymentProviderAdapter
{
    public function provider(): string
    {
        return 'razorpay';
    }

    public function publicKeyId(): string
    {
        $this->assertConfigured();

        return (string) config('services.razorpay.key_id');
    }

    public function initiate(
        CommercialOrder $order,
        Plan $plan,
        string $idempotencyKey,
    ): RazorpayPaymentAttempt {
        $this->assertConfigured();
        $idempotencyKey = trim($idempotencyKey);
        $currency = strtoupper(trim((string) $plan->getAttribute('currency')));
        $amountMinor = (int) $plan->getAttribute('amount_minor');

        if ($idempotencyKey === '' || strlen($idempotencyKey) > 160) {
            throw new InvalidArgumentException('A valid checkout idempotency key is required.');
        }

        if (
            (string) $order->getAttribute('status') !== 'requested'
            || (string) $plan->getAttribute('status') !== 'active'
            || (string) $plan->getAttribute('product_id') !== (string) $order->getAttribute('product_id')
            || ! preg_match('/^[A-Z]{3}$/', $currency)
            || $amountMinor < 1
        ) {
            throw new DomainException('Razorpay checkout facts are not eligible for provider order creation.');
        }

        $existing = RazorpayPaymentAttempt::query()->where('idempotency_key', $idempotencyKey)->first();

        if ($existing !== null) {
            $this->assertAttemptMatches($existing, $order, $plan, $currency, $amountMinor);

            if ($existing->provider_order_id === null) {
                throw new DomainException('Previous Razorpay initiation is ambiguous and requires reconciliation before retry.');
            }

            return $existing;
        }

        $receipt = 'kmj_'.substr(str_replace('-', '', (string) $order->getKey()), 0, 32);

        $attempt = DB::transaction(fn (): RazorpayPaymentAttempt => RazorpayPaymentAttempt::query()->create([
            'order_id' => $order->getKey(),
            'organization_id' => $order->getAttribute('organization_id'),
            'product_id' => $order->getAttribute('product_id'),
            'plan_id' => $plan->getKey(),
            'requester_user_id' => $order->getAttribute('requester_user_id'),
            'idempotency_key' => $idempotencyKey,
            'receipt' => $receipt,
            'currency' => $currency,
            'amount_minor' => $amountMinor,
            'status' => 'initiating',
        ]));

        try {
            $response = $this->client()->post('/orders', [
                'amount' => $amountMinor,
                'currency' => $currency,
                'receipt' => $receipt,
                'notes' => [
                    'kmj_order_id' => (string) $order->getKey(),
                    'kmj_product_id' => (string) $order->getAttribute('product_id'),
                    'kmj_plan_id' => (string) $plan->getKey(),
                ],
            ]);

            if (! $response->successful()) {
                throw new DomainException('Razorpay order creation was rejected.');
            }

            $data = $response->json();
            $providerOrderId = is_array($data) ? ($data['id'] ?? null) : null;

            if (
                ! is_string($providerOrderId)
                || ! preg_match('/^order_[A-Za-z0-9]+$/', $providerOrderId)
                || ($data['amount'] ?? null) !== $amountMinor
                || ($data['currency'] ?? null) !== $currency
                || ($data['receipt'] ?? null) !== $receipt
                || ($data['status'] ?? null) !== 'created'
            ) {
                throw new DomainException('Razorpay order response failed commercial fact verification.');
            }

            $attempt->forceFill([
                'provider_order_id' => $providerOrderId,
                'status' => 'created',
                'failure_code' => null,
            ])->save();

            return $attempt->refresh();
        } catch (Throwable $exception) {
            $attempt->forceFill([
                'status' => 'ambiguous',
                'failure_code' => $exception instanceof ConnectionException
                    ? 'provider_transport_ambiguous'
                    : 'provider_order_rejected',
            ])->save();

            throw new DomainException(
                'Razorpay initiation failed closed; do not retry automatically until provider state is reconciled.',
                previous: $exception,
            );
        }
    }

    public function confirmation(string $providerReference): ProviderPaymentConfirmation
    {
        $this->assertConfigured();
        $providerReference = trim($providerReference);

        if (! preg_match('/^pay_[A-Za-z0-9]+$/', $providerReference)) {
            throw new InvalidArgumentException('A valid Razorpay payment id is required.');
        }

        $response = $this->client()->get('/payments/'.$providerReference);

        if (! $response->successful()) {
            throw new DomainException('Razorpay payment evidence could not be fetched.');
        }

        $data = $response->json();
        $providerOrderId = is_array($data) ? ($data['order_id'] ?? null) : null;
        $attempt = is_string($providerOrderId)
            ? RazorpayPaymentAttempt::query()->where('provider_order_id', $providerOrderId)->first()
            : null;

        if (
            $attempt === null
            || ($data['id'] ?? null) !== $providerReference
            || ($data['status'] ?? null) !== 'captured'
            || ($data['captured'] ?? null) !== true
            || ($data['amount'] ?? null) !== $attempt->amount_minor
            || ($data['currency'] ?? null) !== $attempt->currency
        ) {
            throw new DomainException('Razorpay payment evidence does not match the stored KMJ checkout.');
        }

        $attempt->forceFill([
            'provider_payment_id' => $providerReference,
            'status' => 'captured',
            'captured_at' => $attempt->captured_at ?? now(),
            'failure_code' => null,
        ])->save();

        return new ProviderPaymentConfirmation(
            'razorpay',
            $providerReference,
            (string) $attempt->currency,
            (int) $attempt->amount_minor,
        );
    }

    private function client()
    {
        return Http::baseUrl(rtrim((string) config('services.razorpay.base_url'), '/'))
            ->withBasicAuth(
                (string) config('services.razorpay.key_id'),
                (string) config('services.razorpay.key_secret'),
            )
            ->acceptJson()
            ->asJson()
            ->timeout((float) config('services.razorpay.timeout_seconds', 10));
    }

    private function assertConfigured(): void
    {
        $baseUrl = rtrim((string) config('services.razorpay.base_url'), '/');

        if (
            ! (bool) config('services.razorpay.enabled', false)
            || trim((string) config('services.razorpay.key_id')) === ''
            || trim((string) config('services.razorpay.key_secret')) === ''
            || $baseUrl !== 'https://api.razorpay.com/v1'
        ) {
            throw new DomainException('Razorpay provider is disabled or not safely configured.');
        }
    }

    private function assertAttemptMatches(
        RazorpayPaymentAttempt $attempt,
        CommercialOrder $order,
        Plan $plan,
        string $currency,
        int $amountMinor,
    ): void {
        if (
            $attempt->order_id !== $order->getKey()
            || $attempt->organization_id !== $order->getAttribute('organization_id')
            || $attempt->product_id !== $order->getAttribute('product_id')
            || $attempt->plan_id !== $plan->getKey()
            || $attempt->requester_user_id !== $order->getAttribute('requester_user_id')
            || $attempt->currency !== $currency
            || $attempt->amount_minor !== $amountMinor
        ) {
            throw new DomainException('Razorpay idempotency key was already used for different commercial facts.');
        }
    }
}
