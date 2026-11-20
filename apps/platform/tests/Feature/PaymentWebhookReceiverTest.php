<?php

declare(strict_types=1);

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class PaymentWebhookReceiverTest extends TestCase
{
    use RefreshDatabase;

    private const SECRET = 'whsec_test_secret_value';

    private function storeSecret(string $provider, string $column = 'encrypted_webhook_secret'): void
    {
        DB::table('payment_gateway_settings')->insert([
            'provider' => $provider,
            'environment' => 'sandbox',
            'merchant_status' => 'not_verified',
            'international_requested' => false,
            $column => Crypt::encryptString(self::SECRET),
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    /** @return array<string, string> */
    private function razorpayServer(string $body, ?string $signature = null, string $eventId = 'evt_001'): array
    {
        return [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_X_RAZORPAY_SIGNATURE' => $signature ?? hash_hmac('sha256', $body, self::SECRET),
            'HTTP_X_RAZORPAY_EVENT_ID' => $eventId,
        ];
    }

    private function razorpayBody(): string
    {
        return json_encode([
            'event' => 'payment.captured',
            'payload' => ['payment' => ['entity' => [
                'id' => 'pay_ABC123',
                'order_id' => 'order_XYZ789',
                'email' => 'customer@example.test',
                'contact' => '+910000000000',
            ]]],
        ], JSON_THROW_ON_ERROR);
    }

    public function test_valid_razorpay_webhook_is_recorded_without_pii_or_settlement(): void
    {
        $this->storeSecret('razorpay');
        $body = $this->razorpayBody();

        $this->call('POST', '/webhooks/payments/razorpay', [], [], [], $this->razorpayServer($body), $body)
            ->assertOk()
            ->assertJson(['status' => 'ok']);

        $row = DB::table('payment_webhook_events')->first();
        $this->assertNotNull($row);
        $this->assertSame('razorpay', $row->provider);
        $this->assertSame('evt_001', $row->event_id);
        $this->assertSame('payment.captured', $row->event_type);
        $this->assertSame('order_XYZ789', $row->provider_order_id);
        $this->assertSame('pay_ABC123', $row->provider_payment_id);
        $this->assertSame(hash('sha256', $body), $row->payload_sha256);
        $this->assertSame('received', $row->processing_status);
        $this->assertStringNotContainsString('customer@example.test', json_encode($row, JSON_THROW_ON_ERROR));
    }

    public function test_replayed_event_is_acknowledged_but_stored_once(): void
    {
        $this->storeSecret('razorpay');
        $body = $this->razorpayBody();

        for ($i = 0; $i < 3; $i++) {
            $this->call('POST', '/webhooks/payments/razorpay', [], [], [], $this->razorpayServer($body), $body)
                ->assertOk();
        }

        $this->assertSame(1, DB::table('payment_webhook_events')->count());
    }

    public function test_bad_or_missing_signature_is_rejected_and_nothing_is_stored(): void
    {
        $this->storeSecret('razorpay');
        $body = $this->razorpayBody();

        $this->call('POST', '/webhooks/payments/razorpay', [], [], [], $this->razorpayServer($body, str_repeat('a', 64)), $body)
            ->assertUnauthorized();
        $this->call('POST', '/webhooks/payments/razorpay', [], [], [], ['CONTENT_TYPE' => 'application/json'], $body)
            ->assertUnauthorized();
        // Tampered body with a signature for the original bytes.
        $signature = hash_hmac('sha256', $body, self::SECRET);
        $this->call('POST', '/webhooks/payments/razorpay', [], [], [], $this->razorpayServer($body.' ', $signature), $body.' ')
            ->assertUnauthorized();

        $this->assertSame(0, DB::table('payment_webhook_events')->count());
    }

    public function test_unconfigured_secret_fails_closed(): void
    {
        config()->set('payment-providers.providers.razorpay.webhook_secret', null);
        $body = $this->razorpayBody();

        $this->call('POST', '/webhooks/payments/razorpay', [], [], [], $this->razorpayServer($body), $body)
            ->assertStatus(503);
        $this->assertSame(0, DB::table('payment_webhook_events')->count());
    }

    public function test_unknown_provider_is_not_found(): void
    {
        $this->call('POST', '/webhooks/payments/stripe', [], [], [], ['CONTENT_TYPE' => 'application/json'], '{}')
            ->assertNotFound();
    }

    public function test_signed_but_non_json_body_is_rejected(): void
    {
        $this->storeSecret('razorpay');
        $body = 'not-json';

        $this->call('POST', '/webhooks/payments/razorpay', [], [], [], $this->razorpayServer($body), $body)
            ->assertStatus(400);
        $this->assertSame(0, DB::table('payment_webhook_events')->count());
    }

    public function test_valid_cashfree_webhook_uses_client_secret_fallback(): void
    {
        $this->storeSecret('cashfree', 'encrypted_client_secret');
        $body = json_encode([
            'type' => 'PAYMENT_SUCCESS_WEBHOOK',
            'data' => ['order' => ['order_id' => 'order_cf_1'], 'payment' => ['cf_payment_id' => 998877]],
        ], JSON_THROW_ON_ERROR);
        $timestamp = (string) time();
        $signature = base64_encode(hash_hmac('sha256', $timestamp.$body, self::SECRET, true));

        $this->call('POST', '/webhooks/payments/cashfree', [], [], [], [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_X_WEBHOOK_TIMESTAMP' => $timestamp,
            'HTTP_X_WEBHOOK_SIGNATURE' => $signature,
        ], $body)->assertOk();

        $row = DB::table('payment_webhook_events')->first();
        $this->assertSame('cashfree', $row->provider);
        $this->assertSame('PAYMENT_SUCCESS_WEBHOOK', $row->event_type);
        $this->assertSame('998877', $row->provider_payment_id);
        $this->assertStringStartsWith('sha256:', $row->event_id);
    }

    public function test_webhook_receipt_never_creates_licenses_or_settlement_state(): void
    {
        $this->storeSecret('razorpay');
        $body = $this->razorpayBody();
        $tablesBefore = collect(DB::select("select name from sqlite_master where type = 'table'"))->count();

        $this->call('POST', '/webhooks/payments/razorpay', [], [], [], $this->razorpayServer($body), $body)->assertOk();

        $this->assertSame($tablesBefore, collect(DB::select("select name from sqlite_master where type = 'table'"))->count());
        $this->assertSame(0, DB::table('kslp_licenses')->count());
    }
}
