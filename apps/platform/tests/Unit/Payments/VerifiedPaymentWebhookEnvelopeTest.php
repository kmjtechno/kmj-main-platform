<?php

declare(strict_types=1);

namespace Tests\Unit\Payments;

use App\Services\Payments\CashfreeSignatureVerifier;
use App\Services\Payments\PaymentWebhookSignatureRouter;
use App\Services\Payments\RazorpaySignatureVerifier;
use App\Services\Payments\VerifiedPaymentWebhookEnvelope;
use PHPUnit\Framework\TestCase;

final class VerifiedPaymentWebhookEnvelopeTest extends TestCase
{
    private VerifiedPaymentWebhookEnvelope $inspector;

    protected function setUp(): void
    {
        parent::setUp();
        $this->inspector = new VerifiedPaymentWebhookEnvelope(
            new PaymentWebhookSignatureRouter(
                new RazorpaySignatureVerifier,
                new CashfreeSignatureVerifier,
            ),
        );
    }

    public function test_signed_razorpay_captured_event_has_stable_deduplication_identity_only(): void
    {
        $raw = json_encode([
            'event' => 'payment.captured',
            'payload' => ['payment' => ['entity' => [
                'id' => 'pay_ABC123',
                'order_id' => 'order_DEF456',
                'amount' => 100,
            ]]],
        ], JSON_THROW_ON_ERROR);
        $headers = [
            'x-razorpay-signature' => hash_hmac('sha256', $raw, 'webhook-secret'),
            'x-razorpay-event-id' => 'evt_12345678',
        ];
        $accepted = $this->inspector->inspect('razorpay', $raw, $headers, 'webhook-secret');
        self::assertSame('razorpay', $accepted['provider']);
        self::assertSame('payment.captured', $accepted['event_type']);
        self::assertSame('order_DEF456', $accepted['order_id']);
        self::assertSame('pay_ABC123', $accepted['payment_id']);
        self::assertTrue($accepted['requires_reconciliation']);
        self::assertSame($accepted['event_id'], $this->inspector->inspect('razorpay', $raw, $headers, 'webhook-secret')['event_id']);

        self::assertNull($this->inspector->inspect('razorpay', $raw, $headers, 'incorrect-secret'));
        self::assertNull($this->inspector->inspect('razorpay', $raw.' ', $headers, 'webhook-secret'));
        self::assertNull($this->inspector->inspect('razorpay', $raw, ['x-razorpay-signature' => $headers['x-razorpay-signature']], 'webhook-secret'));
    }

    public function test_signed_cashfree_success_is_only_pending_server_reconciliation(): void
    {
        $payload = [
            'type' => 'PAYMENT_SUCCESS_WEBHOOK',
            'data' => [
                'order' => ['order_id' => 'kmj_checkout_001', 'order_currency' => 'INR', 'order_amount' => 1999],
                'payment' => ['cf_payment_id' => '1453002795', 'payment_status' => 'SUCCESS'],
            ],
        ];
        $raw = json_encode($payload, JSON_THROW_ON_ERROR);
        $time = '1739510400';
        $headers = [
            'x-webhook-timestamp' => $time,
            'x-webhook-signature' => base64_encode(hash_hmac('sha256', $time.$raw, 'cf-secret', true)),
        ];
        $accepted = $this->inspector->inspect('cashfree', $raw, $headers, 'cf-secret');
        self::assertSame('cashfree', $accepted['provider']);
        self::assertSame('PAYMENT_SUCCESS_WEBHOOK', $accepted['event_type']);
        self::assertSame('kmj_checkout_001', $accepted['order_id']);
        self::assertSame('1453002795', $accepted['payment_id']);
        self::assertTrue($accepted['requires_reconciliation']);
        self::assertSame($accepted['event_id'], $this->inspector->inspect('cashfree', $raw, $headers, 'cf-secret')['event_id']);

        self::assertNull($this->inspector->inspect('cashfree', $raw, $headers, 'incorrect-secret'));
        self::assertNull($this->inspector->inspect('cashfree', $raw.' ', $headers, 'cf-secret'));

        $wrongStatus = $payload;
        $wrongStatus['data']['payment']['payment_status'] = 'FAILED';
        $tamperedRaw = json_encode($wrongStatus, JSON_THROW_ON_ERROR);
        $headers['x-webhook-signature'] = base64_encode(hash_hmac('sha256', $time.$tamperedRaw, 'cf-secret', true));
        self::assertNull($this->inspector->inspect('cashfree', $tamperedRaw, $headers, 'cf-secret'));
    }

    public function test_unsupported_malformed_and_overlong_events_never_pass(): void
    {
        self::assertNull($this->inspector->inspect('paypal', '{}', [], 'secret'));
        self::assertNull($this->inspector->inspect('cashfree', '{}', [], 'secret'));
        self::assertNull($this->inspector->inspect('razorpay', str_repeat('x', 262145), [], 'secret'));
    }

    public function test_razorpay_unknown_event_and_malformed_order_fail_even_when_signed(): void
    {
        foreach ([
            ['event' => 'refund.processed', 'order_id' => 'order_ABC123'],
            ['event' => 'payment.captured', 'order_id' => '../wrong'],
            ['event' => 'payment.captured', 'order_id' => 'order_ABC123', 'id' => 'invalid'],
        ] as $test) {
            $raw = json_encode([
                'event' => $test['event'],
                'payload' => ['payment' => ['entity' => [
                    'id' => $test['id'] ?? 'pay_ABC123',
                    'order_id' => $test['order_id'],
                ]]],
            ], JSON_THROW_ON_ERROR);
            $headers = [
                'x-razorpay-event-id' => 'evt_12345678',
                'x-razorpay-signature' => hash_hmac('sha256', $raw, 'secret'),
            ];
            self::assertNull($this->inspector->inspect('razorpay', $raw, $headers, 'secret'));
        }
    }
}
