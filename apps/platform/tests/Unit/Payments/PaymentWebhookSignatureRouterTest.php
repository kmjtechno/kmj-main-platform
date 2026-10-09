<?php

declare(strict_types=1);

namespace Tests\Unit\Payments;

use App\Services\Payments\CashfreeSignatureVerifier;
use App\Services\Payments\PaymentWebhookSignatureRouter;
use App\Services\Payments\RazorpaySignatureVerifier;
use PHPUnit\Framework\TestCase;

final class PaymentWebhookSignatureRouterTest extends TestCase
{
    private PaymentWebhookSignatureRouter $router;

    protected function setUp(): void
    {
        parent::setUp();
        $this->router = new PaymentWebhookSignatureRouter(
            new RazorpaySignatureVerifier,
            new CashfreeSignatureVerifier,
        );
    }

    public function test_verified_cashfree_event_requires_correct_provider_headers_and_secret(): void
    {
        $body = '{"type":"PAYMENT_SUCCESS_WEBHOOK"}';
        $timestamp = '1739510400';
        $signature = base64_encode(hash_hmac('sha256', $timestamp.$body, 'cf-secret', true));
        $headers = [
            'x-webhook-signature' => $signature,
            'x-webhook-timestamp' => $timestamp,
        ];

        self::assertTrue($this->router->verify('cashfree', $body, $headers, 'cf-secret'));
        self::assertFalse($this->router->verify('cashfree', $body, $headers, 'wrong'));
        self::assertFalse($this->router->verify('razorpay', $body, $headers, 'cf-secret'));
        self::assertFalse($this->router->verify('cashfree', $body, ['x-webhook-signature' => $signature], 'cf-secret'));
    }

    public function test_verified_razorpay_event_requires_razorpay_specific_header(): void
    {
        $body = '{"event":"payment.captured"}';
        $signature = hash_hmac('sha256', $body, 'razorpay-webhook-secret');

        self::assertTrue($this->router->verify(
            'razorpay', $body, ['x-razorpay-signature' => $signature], 'razorpay-webhook-secret',
        ));
        self::assertFalse($this->router->verify(
            'cashfree', $body, ['x-razorpay-signature' => $signature], 'razorpay-webhook-secret',
        ));
        self::assertFalse($this->router->verify(
            'razorpay', $body.' ', ['x-razorpay-signature' => $signature], 'razorpay-webhook-secret',
        ));
    }

    public function test_future_gateway_is_not_enabled_by_an_arbitrary_header_or_shared_secret(): void
    {
        foreach (['paypal', 'stripe', 'paddle', 'cashfree ', '', 'CASHFREE', 'other'] as $provider) {
            self::assertFalse($this->router->verify($provider, '{}', [
                'x-webhook-signature' => str_repeat('a', 44),
                'x-webhook-timestamp' => '1739510400',
            ], 'secret'));
        }
        self::assertFalse($this->router->verify('razorpay', '{}', [
            'x-razorpay-signature' => str_repeat('0', 64),
        ], ''));
        self::assertFalse($this->router->verify('razorpay', '', [
            'x-razorpay-signature' => str_repeat('0', 64),
        ], 'secret'));
    }
}
