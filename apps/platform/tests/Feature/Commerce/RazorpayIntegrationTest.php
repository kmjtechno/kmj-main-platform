<?php

namespace Tests\Feature\Commerce;

use App\Models\RazorpayPaymentAttempt;
use App\Models\User;
use App\Services\Commerce\RazorpayGateway;
use App\Services\Commerce\RazorpayWebhookProcessor;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use KMJ\MainPlatform\Catalog\Models\Plan;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Models\CommercialOrder;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class RazorpayIntegrationTest extends TestCase
{
    use RefreshDatabase;

    public function test_provider_is_disabled_by_default_and_makes_no_http_request(): void
    {
        Http::fake();
        [$order, $plan] = $this->orderAndPlan();

        $this->expectException(DomainException::class);

        try {
            app(RazorpayGateway::class)->initiate($order, $plan, 'checkout-disabled');
        } finally {
            Http::assertNothingSent();
        }
    }

    public function test_checkout_is_plan_bound_and_idempotent(): void
    {
        $this->enableProvider();
        [$order, $plan] = $this->orderAndPlan();

        Http::fake([
            'https://api.razorpay.com/v1/orders' => Http::response([
                'id' => 'order_KMJ123',
                'amount' => 249900,
                'currency' => 'INR',
                'receipt' => 'kmj_'.substr(str_replace('-', '', (string) $order->getKey()), 0, 32),
                'status' => 'created',
            ], 200),
        ]);

        $gateway = app(RazorpayGateway::class);
        $first = $gateway->initiate($order, $plan, 'checkout-1');
        $second = $gateway->initiate($order, $plan, 'checkout-1');

        self::assertSame($first->getKey(), $second->getKey());
        self::assertSame('order_KMJ123', $first->provider_order_id);
        self::assertSame('created', $first->status);
        Http::assertSentCount(1);
    }

    public function test_ambiguous_provider_failure_cannot_be_retried_automatically(): void
    {
        $this->enableProvider();
        [$order, $plan] = $this->orderAndPlan();

        Http::fake([
            'https://api.razorpay.com/v1/orders' => Http::response([], 503),
        ]);

        try {
            app(RazorpayGateway::class)->initiate($order, $plan, 'checkout-ambiguous');
            self::fail('Expected provider failure.');
        } catch (DomainException) {
            self::assertSame(
                'ambiguous',
                RazorpayPaymentAttempt::query()->where('idempotency_key', 'checkout-ambiguous')->value('status'),
            );
        }

        Http::fake();

        $this->expectException(DomainException::class);

        try {
            app(RazorpayGateway::class)->initiate($order, $plan, 'checkout-ambiguous');
        } finally {
            Http::assertNothingSent();
        }
    }

    public function test_captured_payment_fetch_produces_verified_reconciliation_evidence(): void
    {
        $this->enableProvider();
        [$order, $plan] = $this->orderAndPlan();
        $attempt = $this->attempt($order, $plan);

        Http::fake([
            'https://api.razorpay.com/v1/payments/pay_KMJ123' => Http::response([
                'id' => 'pay_KMJ123',
                'order_id' => $attempt->provider_order_id,
                'amount' => 249900,
                'currency' => 'INR',
                'status' => 'captured',
                'captured' => true,
            ], 200),
        ]);

        $confirmation = app(RazorpayGateway::class)->confirmation('pay_KMJ123');

        self::assertSame('razorpay', $confirmation->provider);
        self::assertSame('pay_KMJ123', $confirmation->reference);
        self::assertSame('captured', $attempt->refresh()->status);
    }

    public function test_webhook_signature_replay_and_captured_fact_checks_fail_closed(): void
    {
        $this->enableProvider();
        [$order, $plan] = $this->orderAndPlan();
        $attempt = $this->attempt($order, $plan);
        $payload = json_encode([
            'event' => 'payment.captured',
            'payload' => [
                'payment' => [
                    'entity' => [
                        'id' => 'pay_WEBHOOK1',
                        'order_id' => $attempt->provider_order_id,
                        'amount' => 249900,
                        'currency' => 'INR',
                        'status' => 'captured',
                        'captured' => true,
                    ],
                ],
            ],
        ], JSON_THROW_ON_ERROR);
        $signature = hash_hmac('sha256', $payload, 'whsec_test');

        $processor = app(RazorpayWebhookProcessor::class);
        self::assertSame(
            ['status' => 'processed', 'event' => 'payment.captured'],
            $processor->process($payload, $signature, 'evt_capture_1'),
        );
        self::assertSame(
            ['status' => 'replayed', 'event' => 'payment.captured'],
            $processor->process($payload, $signature, 'evt_capture_1'),
        );
        self::assertSame('captured', $attempt->refresh()->status);
        $this->assertDatabaseCount('razorpay_webhook_events', 1);

        $this->expectException(DomainException::class);
        $processor->process($payload.' ', hash_hmac('sha256', $payload.' ', 'whsec_test'), 'evt_capture_1');
    }

    public function test_invalid_webhook_signature_records_nothing(): void
    {
        $this->enableProvider();

        try {
            app(RazorpayWebhookProcessor::class)->process(
                '{"event":"payment.captured"}',
                str_repeat('0', 64),
                'evt_invalid_1',
            );
            self::fail('Expected signature failure.');
        } catch (DomainException) {
            $this->assertDatabaseCount('razorpay_webhook_events', 0);
        }
    }

    private function enableProvider(): void
    {
        config()->set('services.razorpay.enabled', true);
        config()->set('services.razorpay.key_id', 'rzp_test_kmj');
        config()->set('services.razorpay.key_secret', 'test_secret_only');
        config()->set('services.razorpay.webhook_secret', 'whsec_test');
        config()->set('services.razorpay.base_url', 'https://api.razorpay.com/v1');
    }

    /** @return array{0: CommercialOrder, 1: Plan} */
    private function orderAndPlan(): array
    {
        $user = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Razorpay Test Org', $user->id);
        $product = Product::query()->create([
            'slug' => 'razorpay-test-product',
            'name' => 'Razorpay Test Product',
            'status' => 'active',
        ]);
        $plan = Plan::query()->create([
            'product_id' => $product->getKey(),
            'code' => 'razorpay-test-plan',
            'name' => 'Razorpay Test Plan',
            'pricing_model' => 'fixed',
            'currency' => 'INR',
            'amount_minor' => 249900,
            'status' => 'active',
        ]);
        $order = app(CommercialOrderService::class)->request(
            $organization->getKey(),
            $product->getKey(),
            $user->id,
            'razorpay-order-'.str_replace('-', '', (string) $organization->getKey()),
        );

        return [$order, $plan];
    }

    private function attempt($order, Plan $plan): RazorpayPaymentAttempt
    {
        return RazorpayPaymentAttempt::query()->create([
            'order_id' => $order->getKey(),
            'organization_id' => $order->getAttribute('organization_id'),
            'product_id' => $order->getAttribute('product_id'),
            'plan_id' => $plan->getKey(),
            'requester_user_id' => $order->getAttribute('requester_user_id'),
            'idempotency_key' => 'fixture-'.str_replace('-', '', (string) $order->getKey()),
            'receipt' => 'kmj_'.substr(str_replace('-', '', (string) $order->getKey()), 0, 32),
            'provider_order_id' => 'order_FIXTURE123',
            'currency' => 'INR',
            'amount_minor' => 249900,
            'status' => 'created',
        ]);
    }
}
