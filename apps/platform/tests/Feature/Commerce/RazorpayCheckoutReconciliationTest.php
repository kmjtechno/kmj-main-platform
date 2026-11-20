<?php

declare(strict_types=1);

namespace Tests\Feature\Commerce;

use App\Models\User;
use App\Services\Payments\RazorpayCheckoutOrders;
use App\Services\Payments\RazorpayWebhookReconciler;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use InvalidArgumentException;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Models\CommercialOrder;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class RazorpayCheckoutReconciliationTest extends TestCase
{
    use RefreshDatabase;

    private const AMOUNT = 249900;

    private function vault(): void
    {
        DB::table('payment_gateway_settings')->insert([
            'provider' => 'razorpay',
            'environment' => 'sandbox',
            'merchant_status' => 'not_verified',
            'international_requested' => false,
            'encrypted_client_id' => Crypt::encryptString('rzp_test_ABC123'),
            'encrypted_client_secret' => Crypt::encryptString('sandbox-secret-value'),
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function commercialOrder(string $key = 'request:rzp-checkout:1'): CommercialOrder
    {
        $requester = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Checkout Lab '.$key, $requester->id);
        $product = Product::query()->create([
            'slug' => 'checkout-lab-'.md5($key),
            'name' => 'Checkout Lab',
            'status' => 'preview',
        ]);

        return app(CommercialOrderService::class)->request($organization->getKey(), $product->getKey(), $requester->id, $key);
    }

    /** @param array<string, mixed> $payment */
    private function fakeProvider(string $providerOrderId = 'order_TEST1', array $payment = [], int $paymentStatus = 200): void
    {
        Http::fake([
            'api.razorpay.com/v1/orders' => fn (Request $request) => Http::response([
                'id' => $providerOrderId,
                'receipt' => $request['receipt'],
                'currency' => 'INR',
                'amount' => $request['amount'],
                'status' => 'created',
                'amount_paid' => 0,
                'amount_due' => $request['amount'],
            ]),
            'api.razorpay.com/v1/payments/*' => Http::response(array_merge([
                'id' => 'pay_ABC123',
                'order_id' => $providerOrderId,
                'status' => 'captured',
                'captured' => true,
                'currency' => 'INR',
                'amount' => self::AMOUNT,
                'amount_refunded' => 0,
            ], $payment), $paymentStatus),
        ]);
    }

    private function inbox(string $eventId, string $type = 'payment.captured', ?string $orderId = 'order_TEST1', string $paymentId = 'pay_ABC123'): void
    {
        DB::table('payment_webhook_events')->insert([
            'provider' => 'razorpay',
            'event_id' => $eventId,
            'event_type' => $type,
            'provider_order_id' => $orderId,
            'provider_payment_id' => $paymentId,
            'payload_sha256' => hash('sha256', $eventId),
            'processing_status' => 'received',
            'received_at' => now(),
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    public function test_open_creates_one_sandbox_order_link_and_is_idempotent(): void
    {
        $this->vault();
        $this->fakeProvider();
        $order = $this->commercialOrder();
        $service = app(RazorpayCheckoutOrders::class);

        $first = $service->open($order->getKey(), self::AMOUNT);
        $second = $service->open($order->getKey(), self::AMOUNT);

        $this->assertSame('order_TEST1', $first['provider_order_id']);
        $this->assertSame($first, $second);
        $this->assertSame(1, DB::table('commerce_provider_orders')->count());
        Http::assertSentCount(1);
        $this->assertDatabaseCount('entitlements', 0);
    }

    public function test_open_rejects_bad_amount_conflicts_and_non_requested_orders(): void
    {
        $this->vault();
        $this->fakeProvider();
        $order = $this->commercialOrder();
        $service = app(RazorpayCheckoutOrders::class);

        try {
            $service->open($order->getKey(), 50);
            $this->fail('Amount below the provider minimum must be refused.');
        } catch (InvalidArgumentException) {
            $this->addToAssertionCount(1);
        }

        $service->open($order->getKey(), self::AMOUNT);
        $this->expectException(DomainException::class);
        $service->open($order->getKey(), self::AMOUNT + 100);
    }

    public function test_open_without_vault_credentials_fails_closed(): void
    {
        Http::fake();
        $order = $this->commercialOrder();

        try {
            app(RazorpayCheckoutOrders::class)->open($order->getKey(), self::AMOUNT);
            $this->fail('Missing vault must not open an order.');
        } catch (DomainException $exception) {
            $this->assertSame('RAZORPAY_SANDBOX_CREDENTIALS_NOT_READY', $exception->getMessage());
        }
        Http::assertNothingSent();
        $this->assertSame(0, DB::table('commerce_provider_orders')->count());
    }

    public function test_verified_captured_event_confirms_the_linked_order_without_entitlement(): void
    {
        $this->vault();
        $this->fakeProvider();
        $order = $this->commercialOrder();
        app(RazorpayCheckoutOrders::class)->open($order->getKey(), self::AMOUNT);
        $this->inbox('evt_1');

        $totals = app(RazorpayWebhookReconciler::class)->reconcilePending();

        $this->assertSame(1, $totals['reconciled']);
        $confirmed = $order->refresh();
        $this->assertSame('confirmed', $confirmed->status);
        $this->assertSame('razorpay:pay_ABC123', $confirmed->confirmation_reference);
        $this->assertSame(self::AMOUNT, $confirmed->amount_minor);
        $this->assertSame('reconciled', DB::table('payment_webhook_events')->value('processing_status'));
        $this->assertDatabaseCount('entitlements', 0);

        // Already processed rows are never picked up again.
        $again = app(RazorpayWebhookReconciler::class)->reconcilePending();
        $this->assertSame(['reconciled' => 0, 'unmatched' => 0, 'rejected' => 0, 'retry_later' => 0], $again);
    }

    public function test_event_for_unknown_provider_order_is_unmatched_and_changes_nothing(): void
    {
        $this->vault();
        $this->fakeProvider();
        $order = $this->commercialOrder();
        $this->inbox('evt_2', orderId: 'order_UNKNOWN9');

        $totals = app(RazorpayWebhookReconciler::class)->reconcilePending();

        $this->assertSame(1, $totals['unmatched']);
        $this->assertSame('requested', $order->refresh()->status);
        $this->assertSame('unmatched', DB::table('payment_webhook_events')->value('processing_status'));
    }

    public function test_amount_mismatch_with_the_server_expected_amount_is_rejected(): void
    {
        $this->vault();
        $this->fakeProvider(payment: ['amount' => 100]);
        $order = $this->commercialOrder();
        app(RazorpayCheckoutOrders::class)->open($order->getKey(), self::AMOUNT);
        $this->inbox('evt_3');

        $totals = app(RazorpayWebhookReconciler::class)->reconcilePending();

        $this->assertSame(1, $totals['rejected']);
        $this->assertSame('requested', $order->refresh()->status);
        $this->assertSame('AMOUNT_MISMATCH', DB::table('payment_webhook_events')->value('processing_note'));
    }

    public function test_payment_belonging_to_another_provider_order_is_rejected(): void
    {
        $this->vault();
        $this->fakeProvider(payment: ['order_id' => 'order_SOMEONEELSE']);
        $order = $this->commercialOrder();
        app(RazorpayCheckoutOrders::class)->open($order->getKey(), self::AMOUNT);
        $this->inbox('evt_4');

        $totals = app(RazorpayWebhookReconciler::class)->reconcilePending();

        $this->assertSame(1, $totals['rejected']);
        $this->assertSame('requested', $order->refresh()->status);
    }

    public function test_provider_outage_keeps_the_event_for_a_later_retry(): void
    {
        $this->vault();
        $this->fakeProvider(paymentStatus: 500);
        $order = $this->commercialOrder();
        app(RazorpayCheckoutOrders::class)->open($order->getKey(), self::AMOUNT);
        $this->inbox('evt_5');

        $totals = app(RazorpayWebhookReconciler::class)->reconcilePending();

        $this->assertSame(1, $totals['retry_later']);
        $this->assertSame('requested', $order->refresh()->status);
        $this->assertSame('received', DB::table('payment_webhook_events')->value('processing_status'));
    }

    public function test_non_trigger_events_are_left_untouched(): void
    {
        $this->vault();
        $this->fakeProvider();
        $this->inbox('evt_6', type: 'payment.failed');

        $totals = app(RazorpayWebhookReconciler::class)->reconcilePending();

        $this->assertSame(['reconciled' => 0, 'unmatched' => 0, 'rejected' => 0, 'retry_later' => 0], $totals);
        $this->assertSame('received', DB::table('payment_webhook_events')->value('processing_status'));
    }
}
