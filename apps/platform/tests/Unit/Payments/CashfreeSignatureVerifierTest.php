<?php

declare(strict_types=1);

namespace Tests\Unit\Payments;

use App\Services\Payments\CashfreeSignatureVerifier;
use PHPUnit\Framework\TestCase;

final class CashfreeSignatureVerifierTest extends TestCase
{
    private CashfreeSignatureVerifier $verifier;

    protected function setUp(): void
    {
        parent::setUp();
        $this->verifier = new CashfreeSignatureVerifier;
    }

    public function test_valid_webhook_verifies_raw_body_and_timestamp(): void
    {
        $raw = '{"type":"PAYMENT_SUCCESS_WEBHOOK","data":{"order":{"order_id":"order_1"}}}';
        $timestamp = '1739510400';
        $signature = base64_encode(hash_hmac('sha256', $timestamp.$raw, 'cashfree-secret', true));

        self::assertTrue($this->verifier->verifyWebhook(
            $raw, $timestamp, $signature, 'cashfree-secret',
        ));
        self::assertFalse($this->verifier->verifyWebhook(
            $raw."\n", $timestamp, $signature, 'cashfree-secret',
        ));
        self::assertFalse($this->verifier->verifyWebhook(
            $raw, '1739510401', $signature, 'cashfree-secret',
        ));
        self::assertFalse($this->verifier->verifyWebhook(
            $raw, $timestamp, $signature, 'other-secret',
        ));
    }

    public function test_tampered_signature_empty_secret_or_invalid_base64_fails_closed(): void
    {
        $body = '{"type":"PAYMENT_SUCCESS_WEBHOOK"}';
        $timestamp = '1739510400';
        $signature = base64_encode(hash_hmac('sha256', $timestamp.$body, 'secret', true));

        foreach ([
            [$body, $timestamp, '', 'secret'],
            [$body, $timestamp, 'bad-signature', 'secret'],
            [$body, $timestamp, strtoupper($signature), 'secret'],
            [$body, $timestamp, $signature."\n", 'secret'],
            [$body, $timestamp, $signature, ''],
            ['', $timestamp, $signature, 'secret'],
            [str_repeat('a', 262145), $timestamp, $signature, 'secret'],
        ] as $input) {
            self::assertFalse($this->verifier->verifyWebhook(...$input));
        }
    }

    public function test_missing_or_malformed_timestamp_cannot_be_trusted(): void
    {
        $body = '{}';
        $signature = base64_encode(hash_hmac('sha256', '1739510400'.$body, 'secret', true));
        foreach (['', '0', '-1739510400', '1739510400 ', '1739510400\n', '1.739e9', 'abc', '99999999999999999'] as $timestamp) {
            self::assertFalse($this->verifier->verifyWebhook(
                $body, $timestamp, $signature, 'secret',
            ));
        }
    }

    public function test_valid_millisecond_timestamp_is_accepted_when_signed(): void
    {
        $body = '{"type":"PAYMENT_SUCCESS_WEBHOOK"}';
        $timestamp = '1739510400000';
        $signature = base64_encode(hash_hmac('sha256', $timestamp.$body, 'secret', true));

        self::assertTrue($this->verifier->verifyWebhook(
            $body, $timestamp, $signature, 'secret',
        ));
    }

    public function test_razorpay_hex_webhook_signature_is_not_cashfree_base64(): void
    {
        $body = '{"type":"PAYMENT_SUCCESS_WEBHOOK"}';
        $timestamp = '1739510400';
        $razorpayStyle = hash_hmac('sha256', $body, 'secret');

        self::assertFalse($this->verifier->verifyWebhook(
            $body, $timestamp, $razorpayStyle, 'secret',
        ));
    }
}
