<?php

declare(strict_types=1);

namespace Tests\Unit\Payments;

use App\Services\Payments\PaymentCapturedEvidenceGuard;
use App\Services\Payments\ReadOnlySandboxPaymentLookup;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

final class ReadOnlySandboxPaymentLookupTest extends TestCase
{
    public function test_razorpay_captured_payment_is_read_only_and_usable_with_quote_guard(): void
    {
        Http::fake([
            'api.razorpay.com/v1/payments/*' => Http::response([
                'id' => 'pay_ABC123',
                'order_id' => 'order_XYZ123',
                'amount' => 12500,
                'currency' => 'INR',
                'status' => 'captured',
                'captured' => true,
                'amount_refunded' => 0,
            ], 200),
        ]);

        $evidence = app(ReadOnlySandboxPaymentLookup::class)
            ->razorpay('pay_ABC123', 'rzp_test_only', 'test-secret', 'merchant_abc');
        self::assertNotNull($evidence);
        self::assertSame('captured', $evidence['status']);
        self::assertSame(12500, $evidence['amount_minor']);

        $event = [
            'provider' => 'razorpay',
            'event_id' => 'event-proof',
            'event_type' => 'payment.captured',
            'order_id' => 'order_XYZ123',
            'payment_id' => 'pay_ABC123',
            'requires_reconciliation' => true,
        ];
        $quote = [
            'provider' => 'razorpay',
            'merchant_id' => 'merchant_abc',
            'gateway_order_id' => 'order_XYZ123',
            'currency' => 'INR',
            'amount_minor' => 12500,
            'internal_order_id' => 'internal_001',
        ];
        self::assertTrue(app(PaymentCapturedEvidenceGuard::class)->matches($event, $quote, $evidence));
        $quote['amount_minor'] = 12501;
        self::assertFalse(app(PaymentCapturedEvidenceGuard::class)->matches($event, $quote, $evidence));
        Http::assertSentCount(1);
        Http::assertSent(static fn ($request): bool => $request->method() === 'GET'
            && $request->url() === 'https://api.razorpay.com/v1/payments/pay_ABC123'
            && str_starts_with((string) $request->header('Authorization')[0], 'Basic '));
    }

    public function test_razorpay_authorized_or_refunded_payment_is_not_valid_evidence(): void
    {
        foreach ([
            ['status' => 'authorized', 'captured' => false, 'amount_refunded' => 0],
            ['status' => 'captured', 'captured' => true, 'amount_refunded' => 500],
        ] as $changes) {
            Http::fake([
                '*' => Http::response(array_replace([
                    'id' => 'pay_ABC123', 'order_id' => 'order_XYZ123',
                    'amount' => 12500, 'currency' => 'INR',
                ], $changes), 200),
            ]);
            self::assertNull(app(ReadOnlySandboxPaymentLookup::class)
                ->razorpay('pay_ABC123', 'rzp_test_only', 'secret', 'merchant_abc'));
        }
    }

    public function test_invalid_payment_identifier_or_missing_credentials_never_calls_provider(): void
    {
        Http::fake();
        $lookup = app(ReadOnlySandboxPaymentLookup::class);
        self::assertNull($lookup->razorpay('../other', 'id', 'secret', 'merchant'));
        self::assertNull($lookup->razorpay('pay_ABCD', '', 'secret', 'merchant'));
        self::assertNull($lookup->cashfree('../other', '1453002795', 'id', 'secret', 'merchant'));
        self::assertNull($lookup->cashfree('order_ABC', '1453002795', 'id', '', 'merchant'));
        Http::assertNothingSent();
    }

    public function test_cashfree_sandbox_rechecks_unique_success_payment_and_converts_paise(): void
    {
        Http::fake([
            'sandbox.cashfree.com/pg/orders/*/payments' => Http::response([
                ['cf_payment_id' => '111111111', 'payment_status' => 'FAILED', 'payment_currency' => 'INR', 'payment_amount' => 199.00],
                ['cf_payment_id' => '1453002795', 'payment_status' => 'SUCCESS', 'payment_currency' => 'INR', 'payment_amount' => 199.99],
            ], 200),
        ]);
        $result = app(ReadOnlySandboxPaymentLookup::class)
            ->cashfree('order_ABCD', '1453002795', 'cashfree-test-id', 'cashfree-test-secret', 'merchant_abc');
        self::assertNotNull($result);
        self::assertSame(19999, $result['amount_minor']);
        self::assertSame('order_ABCD', $result['gateway_order_id']);
        self::assertSame('SUCCESS', $result['status']);
        Http::assertSentCount(1);
        Http::assertSent(static fn ($request): bool => $request->method() === 'GET'
            && $request->url() === 'https://sandbox.cashfree.com/pg/orders/order_ABCD/payments'
            && $request->hasHeader('x-api-version', '2025-01-01'));
    }

    public function test_cashfree_duplicate_id_underpayment_or_non_inr_is_rejected(): void
    {
        foreach ([
            [['cf_payment_id' => '1453002795', 'payment_status' => 'SUCCESS', 'payment_currency' => 'USD', 'payment_amount' => 199]],
            [['cf_payment_id' => '1453002795', 'payment_status' => 'PENDING', 'payment_currency' => 'INR', 'payment_amount' => 199]],
            [['cf_payment_id' => '1453002795', 'payment_status' => 'SUCCESS', 'payment_currency' => 'INR', 'payment_amount' => 199.001]],
            [
                ['cf_payment_id' => '1453002795', 'payment_status' => 'SUCCESS', 'payment_currency' => 'INR', 'payment_amount' => 199],
                ['cf_payment_id' => '1453002795', 'payment_status' => 'SUCCESS', 'payment_currency' => 'INR', 'payment_amount' => 199],
            ],
        ] as $payments) {
            Http::fake(['*' => Http::response($payments, 200)]);
            self::assertNull(app(ReadOnlySandboxPaymentLookup::class)
                ->cashfree('order_ABCD', '1453002795', 'id', 'secret', 'merchant'));
        }
    }

    public function test_redirects_or_provider_errors_are_never_treated_as_success(): void
    {
        foreach ([302, 401, 404, 429, 500] as $status) {
            Http::fake(['*' => Http::response([], $status)]);
            self::assertNull(app(ReadOnlySandboxPaymentLookup::class)
                ->razorpay('pay_ABC123', 'rzp_test_only', 'secret', 'merchant'));
            self::assertNull(app(ReadOnlySandboxPaymentLookup::class)
                ->cashfree('order_ABCD', '1453002795', 'id', 'secret', 'merchant'));
        }
    }
}
