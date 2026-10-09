<?php

declare(strict_types=1);

namespace Tests\Unit\Payments;

use App\Services\Payments\RazorpaySignatureVerifier;
use PHPUnit\Framework\TestCase;

final class RazorpaySignatureVerifierTest extends TestCase
{
    private RazorpaySignatureVerifier $verifier;

    protected function setUp(): void
    {
        parent::setUp();
        $this->verifier = new RazorpaySignatureVerifier;
    }

    public function test_checkout_accepts_only_a_valid_signature_for_the_trusted_server_order(): void
    {
        $signature = hash_hmac('sha256', 'order_ABC123|pay_DEF456', 'server-secret');

        self::assertTrue($this->verifier->verifyCheckout(
            'order_ABC123',
            'order_ABC123',
            'pay_DEF456',
            $signature,
            'server-secret',
        ));
        self::assertFalse($this->verifier->verifyCheckout(
            'order_ANOTHER', 'order_ABC123', 'pay_DEF456', $signature, 'server-secret',
        ));
        self::assertFalse($this->verifier->verifyCheckout(
            'order_ABC123', 'order_ABC123', 'pay_CHANGED', $signature, 'server-secret',
        ));
        self::assertFalse($this->verifier->verifyCheckout(
            'order_ABC123', 'order_ABC123', 'pay_DEF456', $signature, 'incorrect-secret',
        ));
    }

    public function test_checkout_rejects_malformed_ids_signatures_and_missing_secret(): void
    {
        $signature = hash_hmac('sha256', 'order_ABC123|pay_DEF456', 'server-secret');
        foreach ([
            ['order_ABC123', 'order_ABC123', 'bad', $signature, 'server-secret'],
            ['order_ABC123', 'order_ABC123', 'pay_DEF456', 'bad', 'server-secret'],
            ['order_ABC123', 'order_ABC123', 'pay_DEF456', strtoupper($signature), 'server-secret'],
            ['order_ABC123', 'order_ABC123', 'pay_DEF456', $signature, ''],
            ['order_ABC123', 'order_ABC123 ', 'pay_DEF456', $signature, 'server-secret'],
            ['order_ABC123', 'order_ABC123', 'pay_DEF456', $signature."\n", 'server-secret'],
            ['', 'order_ABC123', 'pay_DEF456', $signature, 'server-secret'],
        ] as $candidate) {
            self::assertFalse($this->verifier->verifyCheckout(...$candidate));
        }
    }

    public function test_webhook_authenticates_exact_raw_request_bytes(): void
    {
        $raw = "{\"event\":\"payment.captured\",\"id\":\"evt_001\"}\n";
        $signature = hash_hmac('sha256', $raw, 'webhook-secret');
        self::assertTrue($this->verifier->verifyWebhook($raw, $signature, 'webhook-secret'));
        self::assertFalse($this->verifier->verifyWebhook(trim($raw), $signature, 'webhook-secret'));
        self::assertFalse($this->verifier->verifyWebhook($raw, $signature, 'wrong-secret'));
        self::assertFalse($this->verifier->verifyWebhook($raw, 'wrong', 'webhook-secret'));
    }

    public function test_webhook_fails_closed_for_empty_body_missing_secret_and_oversized_body(): void
    {
        $raw = '{}';
        $signature = hash_hmac('sha256', $raw, 'webhook-secret');
        self::assertFalse($this->verifier->verifyWebhook('', $signature, 'webhook-secret'));
        self::assertFalse($this->verifier->verifyWebhook($raw, $signature, ''));
        self::assertFalse($this->verifier->verifyWebhook(str_repeat('x', 262145), $signature, 'webhook-secret'));
    }

    public function test_checkout_and_webhook_signing_keys_are_separate(): void
    {
        $raw = '{"event":"payment.captured"}';
        $signature = hash_hmac('sha256', $raw, 'api-secret');
        self::assertFalse($this->verifier->verifyWebhook($raw, $signature, 'different-webhook-secret'));
    }
}
