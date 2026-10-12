<?php

declare(strict_types=1);

namespace Tests\Feature\Payments;

use App\Services\Payments\VerifiedPaymentWebhookInbox;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;
use Tests\TestCase;

final class VerifiedPaymentWebhookInboxTest extends TestCase
{
    use RefreshDatabase;

    /** @return array{0: string, 1: array<string, string>} */
    private function signedRazorpay(string $eventId = 'evt_12345678', int $amount = 100): array
    {
        $raw = json_encode([
            'event' => 'payment.captured',
            'payload' => ['payment' => ['entity' => [
                'id' => 'pay_ABC123',
                'order_id' => 'order_DEF456',
                'amount' => $amount,
            ]]],
        ], JSON_THROW_ON_ERROR);

        return [$raw, [
            'x-razorpay-signature' => hash_hmac('sha256', $raw, 'verified-secret'),
            'x-razorpay-event-id' => $eventId,
        ]];
    }

    /** @return array{0: string, 1: array<string, string>} */
    private function signedCashfree(): array
    {
        $raw = json_encode([
            'type' => 'PAYMENT_SUCCESS_WEBHOOK',
            'data' => [
                'order' => ['order_id' => 'kmj_order_001'],
                'payment' => ['cf_payment_id' => '1453002795', 'payment_status' => 'SUCCESS'],
            ],
        ], JSON_THROW_ON_ERROR);

        $timestamp = '1739510400';

        return [$raw, [
            'x-webhook-timestamp' => $timestamp,
            'x-webhook-signature' => base64_encode(hash_hmac('sha256', $timestamp.$raw, 'verified-secret', true)),
        ]];
    }

    public function test_signed_event_is_recorded_once_without_commerce_or_entitlement_mutation(): void
    {
        [$raw, $headers] = $this->signedRazorpay();
        $inbox = app(VerifiedPaymentWebhookInbox::class);

        $first = $inbox->record('razorpay', $raw, $headers, 'verified-secret', 'merchant-A', 'sandbox');
        self::assertNotNull($first);
        self::assertTrue($first['is_new']);
        self::assertSame('received_unreconciled', $first['state']);
        self::assertSame(64, strlen($first['event_key']));

        $duplicate = $inbox->record('razorpay', $raw, $headers, 'verified-secret', 'merchant-A', 'sandbox');
        self::assertNotNull($duplicate);
        self::assertFalse($duplicate['is_new']);
        self::assertSame($first['event_key'], $duplicate['event_key']);

        $this->assertDatabaseCount('payment_webhook_inbox', 1);
        $this->assertDatabaseCount('commerce_orders', 0);
        $this->assertDatabaseCount('commerce_ledger', 0);
        $this->assertDatabaseCount('entitlements', 0);
        $record = DB::table('payment_webhook_inbox')->first();
        self::assertSame(hash('sha256', 'merchant-A'), $record->merchant_identity_hash);
        self::assertSame(hash('sha256', $raw), $record->body_sha256);
        self::assertSame('received_unreconciled', $record->state);
    }

    public function test_exact_event_id_is_scoped_by_merchant_and_environment(): void
    {
        [$raw, $headers] = $this->signedCashfree();
        $inbox = app(VerifiedPaymentWebhookInbox::class);

        self::assertTrue($inbox->record('cashfree', $raw, $headers, 'verified-secret', 'merchant-A', 'sandbox')['is_new']);
        self::assertTrue($inbox->record('cashfree', $raw, $headers, 'verified-secret', 'merchant-B', 'sandbox')['is_new']);
        self::assertTrue($inbox->record('cashfree', $raw, $headers, 'verified-secret', 'merchant-A', 'live')['is_new']);
        self::assertFalse($inbox->record('cashfree', $raw, $headers, 'verified-secret', 'merchant-B', 'sandbox')['is_new']);

        $this->assertDatabaseCount('payment_webhook_inbox', 3);
        $this->assertDatabaseCount('entitlements', 0);
    }

    public function test_invalid_signature_or_unsupported_provider_never_reaches_database(): void
    {
        [$raw, $headers] = $this->signedRazorpay();
        $inbox = app(VerifiedPaymentWebhookInbox::class);

        self::assertNull($inbox->record('razorpay', $raw, $headers, 'wrong-secret', 'merchant-A', 'sandbox'));
        self::assertNull($inbox->record('stripe', $raw, $headers, 'verified-secret', 'merchant-A', 'sandbox'));
        self::assertNull($inbox->record('razorpay', $raw.' ', $headers, 'verified-secret', 'merchant-A', 'sandbox'));
        $this->assertDatabaseCount('payment_webhook_inbox', 0);
    }

    public function test_same_provider_delivery_id_with_conflicting_signed_body_fails_closed(): void
    {
        $inbox = app(VerifiedPaymentWebhookInbox::class);
        [$firstRaw, $firstHeaders] = $this->signedRazorpay();
        [$secondRaw, $secondHeaders] = $this->signedRazorpay('evt_12345678', 200);

        $inbox->record('razorpay', $firstRaw, $firstHeaders, 'verified-secret', 'merchant-A', 'sandbox');
        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('Conflicting payment webhook identity replay.');
        try {
            $inbox->record('razorpay', $secondRaw, $secondHeaders, 'verified-secret', 'merchant-A', 'sandbox');
        } finally {
            $this->assertDatabaseCount('payment_webhook_inbox', 1);
        }
    }

    public function test_server_identity_must_be_explicitly_scoped(): void
    {
        [$raw, $headers] = $this->signedRazorpay();
        $this->expectException(InvalidArgumentException::class);
        app(VerifiedPaymentWebhookInbox::class)->record(
            'razorpay', $raw, $headers, 'verified-secret', '../foreign', 'live',
        );
    }
}
