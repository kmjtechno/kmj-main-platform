<?php

declare(strict_types=1);

namespace Tests\Feature\Payments;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class SandboxWebhookReceiverTest extends TestCase
{
    use RefreshDatabase;

    private function configure(string $provider, bool $withWebhookSecret = true): void
    {
        DB::table('payment_gateway_settings')->insert([
            'provider' => $provider,
            'environment' => 'sandbox',
            'merchant_status' => 'not_verified',
            'international_requested' => false,
            'encrypted_client_id' => Crypt::encryptString(
                $provider === 'razorpay' ? 'rzp_test_1234567890' : 'CF_TEST_1234567890'
            ),
            'encrypted_client_secret' => Crypt::encryptString('sandbox-client-secret'),
            'encrypted_webhook_secret' => $withWebhookSecret
                ? Crypt::encryptString('sandbox-webhook-secret') : null,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function razorpayEvent(string $eventId = 'evt_1234567890', int $amount = 100): array
    {
        $body = json_encode([
            'event' => 'payment.captured',
            'payload' => ['payment' => ['entity' => [
                'id' => 'pay_ABC123',
                'order_id' => 'order_DEF456',
                'amount' => $amount,
            ]]],
        ], JSON_THROW_ON_ERROR);

        return [$body, [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_X_RAZORPAY_SIGNATURE' => hash_hmac('sha256', $body, 'sandbox-webhook-secret'),
            'HTTP_X_RAZORPAY_EVENT_ID' => $eventId,
        ]];
    }

    private function deliver(string $provider, string $body, array $server): \Illuminate\Testing\TestResponse
    {
        return $this->call('POST', '/api/payments/webhooks/'.$provider, [], [], [], $server, $body);
    }

    public function test_unconfigured_sandbox_rejects_webhook_without_side_effects(): void
    {
        [$body, $headers] = $this->razorpayEvent();
        $this->deliver('razorpay', $body, $headers)->assertStatus(503);
        $this->assertDatabaseCount('payment_webhook_inbox', 0);
    }

    public function test_razorpay_requires_separate_webhook_secret_and_valid_raw_body_signature(): void
    {
        $this->configure('razorpay', false);
        [$body, $headers] = $this->razorpayEvent();
        $this->deliver('razorpay', $body, $headers)->assertStatus(503);
        DB::table('payment_gateway_settings')->where('provider', 'razorpay')->update([
            'encrypted_webhook_secret' => Crypt::encryptString('sandbox-webhook-secret'),
        ]);
        $this->deliver('razorpay', $body.' ', $headers)->assertStatus(401);
        $this->assertDatabaseCount('payment_webhook_inbox', 0);
    }

    public function test_razorpay_valid_signed_event_is_durable_idempotent_and_never_fulfills(): void
    {
        $this->configure('razorpay');
        [$body, $headers] = $this->razorpayEvent();

        $this->deliver('razorpay', $body, $headers)->assertStatus(202)
            ->assertJsonPath('requires_reconciliation', true);
        $this->deliver('razorpay', $body, $headers)->assertStatus(200);
        $this->assertDatabaseCount('payment_webhook_inbox', 1);
        $record = DB::table('payment_webhook_inbox')->first();
        self::assertSame('received_unreconciled', $record->state);
        self::assertSame(hash('sha256', $body), $record->body_sha256);
        self::assertSame('sandbox', $record->environment);
        $this->assertDatabaseCount('entitlements', 0);

        [$modified, $modifiedHeaders] = $this->razorpayEvent('evt_1234567890', 200);
        $this->deliver('razorpay', $modified, $modifiedHeaders)->assertStatus(409);
        $this->assertDatabaseCount('payment_webhook_inbox', 1);
    }

    public function test_cashfree_is_bound_to_its_own_sandbox_client_secret(): void
    {
        $this->configure('cashfree');
        $body = json_encode([
            'type' => 'PAYMENT_SUCCESS_WEBHOOK',
            'data' => [
                'order' => ['order_id' => 'kmj_order_001'],
                'payment' => ['cf_payment_id' => '1453002795', 'payment_status' => 'SUCCESS'],
            ],
        ], JSON_THROW_ON_ERROR);
        $timestamp = '1739510400';
        $signature = base64_encode(hash_hmac('sha256', $timestamp.$body, 'sandbox-client-secret', true));
        $headers = [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_X_WEBHOOK_TIMESTAMP' => $timestamp,
            'HTTP_X_WEBHOOK_SIGNATURE' => $signature,
        ];

        $this->deliver('cashfree', $body, $headers)->assertStatus(202);
        $this->deliver('cashfree', $body, $headers)->assertStatus(200);
        $this->assertDatabaseCount('payment_webhook_inbox', 1);
        $this->assertDatabaseCount('entitlements', 0);
    }

    public function test_live_configuration_is_inactive_and_unknown_gateway_not_exposed(): void
    {
        $this->configure('razorpay');
        DB::table('payment_gateway_settings')->where('provider', 'razorpay')
            ->update(['environment' => 'live']);
        [$body, $headers] = $this->razorpayEvent();
        $this->deliver('razorpay', $body, $headers)->assertStatus(503);
        $this->deliver('stripe', $body, $headers)->assertNotFound();
        $this->assertDatabaseCount('payment_webhook_inbox', 0);
    }
}
