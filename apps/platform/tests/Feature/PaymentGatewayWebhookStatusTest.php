<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Services\Payments\PaymentGatewayReadiness;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class PaymentGatewayWebhookStatusTest extends TestCase
{
    use RefreshDatabase;

    /** @return array<string, mixed> */
    private function razorpay(): array
    {
        $providers = collect(app(PaymentGatewayReadiness::class)->snapshot()['providers'])->keyBy('id');

        return (array) $providers->get('razorpay');
    }

    private function storeSecret(): void
    {
        DB::table('payment_gateway_settings')->insert([
            'provider' => 'razorpay',
            'environment' => 'sandbox',
            'merchant_status' => 'not_verified',
            'international_requested' => false,
            'encrypted_webhook_secret' => Crypt::encryptString('whsec_status_test'),
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function event(string $id, string $status = 'received'): void
    {
        DB::table('payment_webhook_events')->insert([
            'provider' => 'razorpay',
            'event_id' => $id,
            'event_type' => 'payment.captured',
            'payload_sha256' => hash('sha256', $id),
            'processing_status' => $status,
            'received_at' => now(),
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    public function test_console_publishes_the_kmj_receiver_url_and_no_delivery_claim_by_default(): void
    {
        $razorpay = $this->razorpay();

        $this->assertStringEndsWith('/webhooks/payments/razorpay', $razorpay['webhook_receiver_url']);
        $this->assertSame(0, $razorpay['webhook_events_received']);
        $this->assertNull($razorpay['webhook_last_received_at']);
        $this->assertFalse($razorpay['webhook_verification_configured']);
    }

    public function test_a_stored_secret_alone_never_claims_delivery(): void
    {
        $this->storeSecret();

        $razorpay = $this->razorpay();

        $this->assertTrue($razorpay['webhook_secret_stored']);
        $this->assertFalse($razorpay['webhook_verification_configured']);
    }

    public function test_delivery_is_proven_only_with_a_secret_and_a_received_signed_event(): void
    {
        $this->storeSecret();
        $this->event('evt_a');
        $this->event('conflict:abc', 'conflict');

        $razorpay = $this->razorpay();

        $this->assertSame(1, $razorpay['webhook_events_received']);
        $this->assertNotNull($razorpay['webhook_last_received_at']);
        $this->assertTrue($razorpay['webhook_verification_configured']);
        $this->assertStringNotContainsString('whsec_status_test', json_encode($razorpay, JSON_THROW_ON_ERROR));
    }

    public function test_events_without_a_stored_secret_do_not_claim_verification(): void
    {
        config()->set('payment-providers.providers.razorpay.webhook_secret', null);
        $this->event('evt_b');

        $this->assertFalse($this->razorpay()['webhook_verification_configured']);
    }
}
