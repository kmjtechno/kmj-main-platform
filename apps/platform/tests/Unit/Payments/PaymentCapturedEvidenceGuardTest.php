<?php

declare(strict_types=1);

namespace Tests\Unit\Payments;

use App\Services\Payments\PaymentCapturedEvidenceGuard;
use PHPUnit\Framework\TestCase;

final class PaymentCapturedEvidenceGuardTest extends TestCase
{
    /** @return array{provider: string, event_id: string, event_type: string, order_id: string, payment_id: string, requires_reconciliation: true} */
    private function event(string $provider = 'razorpay'): array
    {
        return [
            'provider' => $provider,
            'event_id' => hash('sha256', 'event-123'),
            'event_type' => $provider === 'cashfree' ? 'PAYMENT_SUCCESS_WEBHOOK' : 'payment.captured',
            'order_id' => 'order_ABC123',
            'payment_id' => 'pay_DEF456',
            'requires_reconciliation' => true,
        ];
    }

    /** @return array{provider: string, merchant_id: string, gateway_order_id: string, currency: string, amount_minor: int, internal_order_id: string} */
    private function quote(string $provider = 'razorpay'): array
    {
        return [
            'provider' => $provider,
            'merchant_id' => 'merchant_abc',
            'gateway_order_id' => 'order_ABC123',
            'currency' => 'INR',
            'amount_minor' => 19900,
            'internal_order_id' => 'internal-order-uuid',
        ];
    }

    /** @return array{provider: string, merchant_id: string, gateway_order_id: string, payment_id: string, currency: string, amount_minor: int, status: string} */
    private function fetched(string $provider = 'razorpay'): array
    {
        return [
            'provider' => $provider,
            'merchant_id' => 'merchant_abc',
            'gateway_order_id' => 'order_ABC123',
            'payment_id' => 'pay_DEF456',
            'currency' => 'INR',
            'amount_minor' => 19900,
            'status' => $provider === 'cashfree' ? 'SUCCESS' : 'captured',
        ];
    }

    public function test_only_exact_server_quote_and_provider_captured_evidence_match(): void
    {
        $guard = new PaymentCapturedEvidenceGuard;

        self::assertTrue($guard->matches($this->event(), $this->quote(), $this->fetched()));
        self::assertTrue($guard->matches($this->event('cashfree'), $this->quote('cashfree'), $this->fetched('cashfree')));
    }

    public function test_any_merchant_order_payment_currency_or_amount_mismatch_fails_closed(): void
    {
        $guard = new PaymentCapturedEvidenceGuard;
        foreach ([
            ['merchant_id' => 'other_merchant'],
            ['gateway_order_id' => 'order_OTHER'],
            ['payment_id' => 'pay_OTHER'],
            ['currency' => 'USD'],
            ['amount_minor' => 19901],
            ['amount_minor' => 0],
            ['status' => 'authorized'],
        ] as $changes) {
            self::assertFalse($guard->matches($this->event(), $this->quote(), array_replace($this->fetched(), $changes)));
        }

        foreach ([
            ['merchant_id' => 'other_merchant'],
            ['gateway_order_id' => 'order_OTHER'],
            ['currency' => 'USD'],
            ['currency' => 'inr'],
            ['amount_minor' => 19901],
            ['amount_minor' => 0],
            ['internal_order_id' => ''],
        ] as $changes) {
            self::assertFalse($guard->matches($this->event(), array_replace($this->quote(), $changes), $this->fetched()));
        }
    }

    public function test_wrong_event_type_and_cross_provider_replay_are_rejected(): void
    {
        $guard = new PaymentCapturedEvidenceGuard;
        self::assertFalse($guard->matches(array_replace($this->event(), ['event_type' => 'payment.failed']), $this->quote(), $this->fetched()));
        self::assertFalse($guard->matches(array_replace($this->event(), ['order_id' => 'order_OTHER']), $this->quote(), $this->fetched()));
        self::assertFalse($guard->matches(array_replace($this->event(), ['payment_id' => 'pay_OTHER']), $this->quote(), $this->fetched()));
        self::assertFalse($guard->matches($this->event('cashfree'), $this->quote(), $this->fetched()));
        self::assertFalse($guard->matches($this->event(), $this->quote(), array_replace($this->fetched(), ['provider' => 'cashfree'])));
        self::assertFalse($guard->matches($this->event('cashfree'), $this->quote('cashfree'), array_replace($this->fetched('cashfree'), ['status' => 'FAILED'])));
    }
}
