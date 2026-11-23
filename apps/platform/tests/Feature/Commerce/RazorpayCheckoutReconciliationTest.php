<?php

declare(strict_types=1);

namespace Tests\Feature\Commerce;

use App\Models\User;
use App\Services\Payments\RazorpayCheckoutOrders;
use App\Services\Payments\RazorpayWebhookReconciler;
use DomainException;
use Illuminate\Database\QueryException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Artisan;
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

    public function test_provider_create_http_runs_outside_the_locked_database_transaction(): void
    {
        $this->vault();
        $order = $this->commercialOrder('request:rzp-checkout:no-network-lock');
        $testTransactionDepth = DB::transactionLevel();
        Http::fake([
            'api.razorpay.com/v1/orders' => function (Request $request) use ($testTransactionDepth) {
                $this->assertSame($testTransactionDepth, DB::transactionLevel(), 'Provider HTTP must not hold a new order transaction.');

                return Http::response([
                    'id' => 'order_TEST1',
                    'receipt' => $request['receipt'],
                    'currency' => 'INR',
                    'amount' => $request['amount'],
                    'status' => 'created',
                    'amount_paid' => 0,
                    'amount_due' => $request['amount'],
                ]);
            },
        ]);

        $created = app(RazorpayCheckoutOrders::class)->open($order->getKey(), self::AMOUNT);

        $this->assertSame('order_TEST1', $created['provider_order_id']);
        $this->assertDatabaseHas('commerce_provider_order_intents', [
            'commercial_order_id' => $order->getKey(),
            'provider' => 'razorpay',
            'amount_minor' => self::AMOUNT,
            'creation_status' => 'linked',
        ]);
        Http::assertSentCount(1);
        $this->assertDatabaseCount('entitlements', 0);
    }

    public function test_provider_success_then_local_link_failure_never_creates_second_provider_order(): void
    {
        $this->vault();
        $order = $this->commercialOrder('request:rzp-checkout:provider-success-db-fail');
        $collider = $this->commercialOrder('request:rzp-checkout:other-order');
        $testTransactionDepth = DB::transactionLevel();
        Http::fake([
            'api.razorpay.com/v1/orders' => function (Request $request) use ($collider, $testTransactionDepth) {
                // Assert no extra order lock above the RefreshDatabase test transaction.
                $this->assertSame($testTransactionDepth, DB::transactionLevel());
                // Inject a real unique constraint failure after provider success.
                DB::table('commerce_provider_orders')->insert([
                    'commercial_order_id' => $collider->getKey(),
                    'provider' => 'razorpay',
                    'provider_order_id' => 'order_TEST1',
                    'amount_minor' => self::AMOUNT,
                    'currency' => 'INR',
                    'environment' => 'sandbox',
                    'created_at' => now(),
                    'updated_at' => now(),
                ]);

                return Http::response([
                    'id' => 'order_TEST1',
                    'receipt' => $request['receipt'],
                    'currency' => 'INR',
                    'amount' => $request['amount'],
                    'status' => 'created',
                    'amount_paid' => 0,
                    'amount_due' => $request['amount'],
                ]);
            },
        ]);

        $service = app(RazorpayCheckoutOrders::class);
        try {
            $service->open($order->getKey(), self::AMOUNT);
            $this->fail('Local provider-link conflict must not be hidden.');
        } catch (QueryException) {
            $this->addToAssertionCount(1);
        }

        $this->assertDatabaseHas('commerce_provider_order_intents', [
            'commercial_order_id' => $order->getKey(),
            'creation_status' => 'creating',
        ]);
        $this->assertDatabaseMissing('commerce_provider_orders', [
            'commercial_order_id' => $order->getKey(),
        ]);

        try {
            $service->open($order->getKey(), self::AMOUNT);
            $this->fail('A retry must not create another remote order after an uncertain outcome.');
        } catch (DomainException $exception) {
            $this->assertSame('RAZORPAY_ORDER_CREATION_PENDING_REVIEW', $exception->getMessage());
        }
        Http::assertSentCount(1);
        $this->assertDatabaseCount('entitlements', 0);
    }

    public function test_provider_unavailable_keeps_durable_reservation_and_blocks_duplicate_create(): void
    {
        $this->vault();
        $order = $this->commercialOrder('request:rzp-checkout:provider-unavailable');
        Http::fake(['api.razorpay.com/v1/orders' => Http::response([], 503)]);
        $service = app(RazorpayCheckoutOrders::class);

        try {
            $service->open($order->getKey(), self::AMOUNT);
            $this->fail('HTTP failure must never be mistaken for provider order creation.');
        } catch (DomainException $exception) {
            $this->assertSame('RAZORPAY_SANDBOX_PROVIDER_UNAVAILABLE', $exception->getMessage());
        }

        $this->assertDatabaseHas('commerce_provider_order_intents', [
            'commercial_order_id' => $order->getKey(),
            'creation_status' => 'creating',
        ]);

        try {
            $service->open($order->getKey(), self::AMOUNT);
            $this->fail('Uncertain external result must be reconciled before any retry.');
        } catch (DomainException $exception) {
            $this->assertSame('RAZORPAY_ORDER_CREATION_PENDING_REVIEW', $exception->getMessage());
        }
        Http::assertSentCount(1);
        $this->assertDatabaseCount('commerce_provider_orders', 0);
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

    public function test_event_for_unknown_provider_order_retries_then_expires_without_confirmation(): void
    {
        $this->vault();
        $this->fakeProvider();
        $order = $this->commercialOrder();
        $this->inbox('evt_2', orderId: 'order_UNKNOWN9');

        $first = app(RazorpayWebhookReconciler::class)->reconcilePending();

        $this->assertSame(1, $first['retry_later']);
        $this->assertSame('awaiting_link', DB::table('payment_webhook_events')->value('processing_status'));
        Http::assertNothingSent();

        // A foreign provider order cannot keep a verified inbox row forever.
        $this->travel(61)->minutes();
        $expired = app(RazorpayWebhookReconciler::class)->reconcilePending();

        $this->assertSame(1, $expired['unmatched']);
        $this->assertSame('LINK_WINDOW_EXPIRED', DB::table('payment_webhook_events')->value('processing_note'));
        $this->assertSame('requested', $order->refresh()->status);
        $this->assertSame('unmatched', DB::table('payment_webhook_events')->value('processing_status'));
        $this->assertDatabaseCount('entitlements', 0);
        Http::assertNothingSent();
    }

    public function test_signed_webhook_arriving_before_link_is_retried_and_reconciled_once(): void
    {
        $this->vault();
        $this->fakeProvider();
        $order = $this->commercialOrder('request:rzp-checkout:before-link');
        $this->inbox('evt_before_link');

        $reconciler = app(RazorpayWebhookReconciler::class);
        $first = $reconciler->reconcilePending();

        $this->assertSame(1, $first['retry_later']);
        $this->assertSame('awaiting_link', DB::table('payment_webhook_events')->value('processing_status'));
        $this->assertSame('requested', $order->refresh()->status);
        Http::assertNothingSent();

        app(RazorpayCheckoutOrders::class)->open($order->getKey(), self::AMOUNT);

        // Avoid retry storm: an event waiting for a link has a short backoff.
        $tooEarly = $reconciler->reconcilePending();
        $this->assertSame(['reconciled' => 0, 'unmatched' => 0, 'rejected' => 0, 'retry_later' => 0], $tooEarly);

        $this->travel(61)->seconds();
        $later = $reconciler->reconcilePending();

        $this->assertSame(1, $later['reconciled']);
        $this->assertSame('confirmed', $order->refresh()->status);
        $this->assertSame('razorpay:pay_ABC123', $order->confirmation_reference);
        $this->assertSame('reconciled', DB::table('payment_webhook_events')->value('processing_status'));
        $this->assertDatabaseCount('entitlements', 0);
        $this->assertSame(['reconciled' => 0, 'unmatched' => 0, 'rejected' => 0, 'retry_later' => 0], $reconciler->reconcilePending());
        Http::assertSentCount(2);
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

    public function test_scheduled_sandbox_payment_reconciler_confirms_verified_order_without_issuing_license(): void
    {
        $this->vault();
        $this->fakeProvider();
        $order = $this->commercialOrder('auto:reconcile:1');
        app(RazorpayCheckoutOrders::class)->open($order->getKey(), self::AMOUNT);
        $this->inbox('evt_AUTO1');

        self::assertSame(0, Artisan::call('payments:reconcile-razorpay-sandbox'));
        self::assertSame('confirmed', $order->refresh()->status);
        $this->assertDatabaseHas('payment_webhook_events', [
            'event_id' => 'evt_AUTO1',
            'processing_status' => 'reconciled',
            'processing_note' => 'CONFIRMED',
        ]);
        $this->assertDatabaseCount('entitlements', 0);
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('kslp_activations', 0);
        self::assertSame(0, Artisan::call('payments:reconcile-razorpay-sandbox'));
        $this->assertDatabaseCount('commerce_ledger', 2);
    }

    public function test_automatic_sandbox_reconciliation_without_owner_vault_credentials_is_safe_noop(): void
    {
        $order = $this->commercialOrder('auto:no-credentials');
        $this->inbox('evt_AUTONOKEY');

        self::assertSame(0, Artisan::call('payments:reconcile-razorpay-sandbox'));
        self::assertSame('requested', $order->refresh()->status);
        $this->assertDatabaseHas('payment_webhook_events', [
            'event_id' => 'evt_AUTONOKEY',
            'processing_status' => 'received',
        ]);
        $this->assertDatabaseCount('entitlements', 0);
        $this->assertDatabaseCount('kslp_licenses', 0);
    }

    public function test_reconciler_rejects_non_sandbox_order_link_without_calling_provider(): void
    {
        $this->vault();
        $this->fakeProvider();
        $order = $this->commercialOrder('auto:foreign-environment');
        app(RazorpayCheckoutOrders::class)->open($order->getKey(), self::AMOUNT);
        DB::table('commerce_provider_orders')
            ->where('commercial_order_id', $order->getKey())
            ->update(['environment' => 'live']);
        $this->inbox('evt_AUTOLIVE');

        Http::assertSentCount(1);
        self::assertSame(0, Artisan::call('payments:reconcile-razorpay-sandbox'));
        Http::assertSentCount(1);
        self::assertSame('requested', $order->refresh()->status);
        $this->assertDatabaseHas('payment_webhook_events', [
            'event_id' => 'evt_AUTOLIVE',
            'processing_status' => 'rejected',
            'processing_note' => 'PROVIDER_ENVIRONMENT_MISMATCH',
        ]);
        $this->assertDatabaseCount('entitlements', 0);
        $this->assertDatabaseCount('kslp_licenses', 0);
    }

    public function test_automatic_reconciler_invalid_limit_rejected_before_provider_access(): void
    {
        self::assertSame(2, Artisan::call('payments:reconcile-razorpay-sandbox', ['--limit' => '0']));
        $this->assertDatabaseCount('entitlements', 0);
        $this->assertDatabaseCount('kslp_licenses', 0);
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
