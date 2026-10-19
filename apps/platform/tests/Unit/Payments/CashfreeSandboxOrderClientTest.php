<?php

declare(strict_types=1);

namespace Tests\Unit\Payments;

use App\Services\Payments\CashfreeSandboxOrderClient;
use DomainException;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

final class CashfreeSandboxOrderClientTest extends TestCase
{
    private CashfreeSandboxOrderClient $client;

    protected function setUp(): void
    {
        parent::setUp();
        Http::preventStrayRequests();
        $this->client = new CashfreeSandboxOrderClient;
    }

    private function create(): array
    {
        return $this->client->create(
            'kmj_test_order_001',
            199900,
            'INR',
            'kmj_user1',
            '9876543210',
            'test-app-id',
            'test-client-secret',
        );
    }

    public function test_creates_only_a_sandbox_order_with_a_server_owned_exact_amount(): void
    {
        Http::fake(['sandbox.cashfree.com/pg/orders' => Http::response([
            'order_id' => 'kmj_test_order_001',
            'order_currency' => 'INR',
            'order_amount' => 1999.00,
            'payment_session_id' => 'session_1234567890EXAMPLE',
        ], 200)]);

        self::assertSame([
            'order_id' => 'kmj_test_order_001',
            'payment_session_id' => 'session_1234567890EXAMPLE',
        ], $this->create());

        Http::assertSent(function (Request $request): bool {
            return $request->method() === 'POST'
                && $request->url() === 'https://sandbox.cashfree.com/pg/orders'
                && $request->hasHeader('x-api-version', '2025-01-01')
                && $request->hasHeader('x-client-id', 'test-app-id')
                && $request->hasHeader('x-client-secret', 'test-client-secret')
                && $request->hasHeader('x-idempotency-key')
                && $request['order_id'] === 'kmj_test_order_001'
                && $request['order_amount'] === 1999.0
                && $request['order_currency'] === 'INR';
        });
    }

    public function test_invalid_parameters_are_rejected_before_any_provider_request(): void
    {
        Http::fake();
        foreach ([
            ['wrong order!', 199900, 'INR', 'kmj_user1', '9876543210', 'id', 'secret'],
            ['kmj_test_order_001', 0, 'INR', 'kmj_user1', '9876543210', 'id', 'secret'],
            ['kmj_test_order_001', 199900, 'USD', 'kmj_user1', '9876543210', 'id', 'secret'],
            ['kmj_test_order_001', 199900, 'INR', 'bad id', '9876543210', 'id', 'secret'],
            ['kmj_test_order_001', 199900, 'INR', 'kmj_user1', 'bad', 'id', 'secret'],
            ['kmj_test_order_001', 199900, 'INR', 'kmj_user1', '9876543210', '', 'secret'],
            ['kmj_test_order_001', 199900, 'INR', 'kmj_user1', '9876543210', 'id', ''],
            ['kmj_test_order_001', 199900, 'INR', 'kmj_user1', '9876543210', "id\r\nInjected", 'secret'],
            ['kmj_test_order_001', 199900, 'INR', 'kmj_user1', '9876543210', 'id', "secret\r\nInjected"],
            ['kmj_test_order_001', 199900, 'INR', 'kmj_user1', '9876543210', "id\0bad", 'secret'],
            ['kmj_test_order_001', 199900, 'INR', 'kmj_user1', '9876543210', 'id', "secret\x7Fbad"],
            ['kmj_test_order_001', 199900, 'INR', 'kmj_user1', '9876543210', str_repeat('i', 256), 'secret'],
            ['kmj_test_order_001', 199900, 'INR', 'kmj_user1', '9876543210', 'id', str_repeat('s', 1025)],
        ] as $parameters) {
            try {
                $this->client->create(...$parameters);
                self::fail('Expected strict sandbox-order rejection.');
            } catch (DomainException $exception) {
                self::assertSame('CASHFREE_SANDBOX_INVALID_ORDER', $exception->getMessage());
            }
        }
        Http::assertNothingSent();
    }

    public function test_provider_mismatch_never_returns_checkout_session(): void
    {
        foreach ([
            ['order_id' => 'another_order', 'order_currency' => 'INR', 'order_amount' => 1999, 'payment_session_id' => 'session_1234567890EXAMPLE'],
            ['order_id' => 'kmj_test_order_001', 'order_currency' => 'USD', 'order_amount' => 1999, 'payment_session_id' => 'session_1234567890EXAMPLE'],
            ['order_id' => 'kmj_test_order_001', 'order_currency' => 'INR', 'order_amount' => 2000, 'payment_session_id' => 'session_1234567890EXAMPLE'],
            ['order_id' => 'kmj_test_order_001', 'order_currency' => 'INR', 'order_amount' => 1999, 'payment_session_id' => ''],
        ] as $response) {
            Http::fake(['sandbox.cashfree.com/pg/orders' => Http::response($response)]);
            try {
                $this->create();
                self::fail('Mismatched payment session must not be accepted.');
            } catch (DomainException $exception) {
                self::assertSame('CASHFREE_SANDBOX_ORDER_MISMATCH', $exception->getMessage());
            }
        }
    }

    public function test_provider_server_failure_does_not_return_payment_session(): void
    {
        Http::fake(['sandbox.cashfree.com/pg/orders' => Http::response(['message' => 'unavailable'], 503)]);
        $this->expectExceptionMessage('CASHFREE_SANDBOX_PROVIDER_UNAVAILABLE');
        $this->create();
    }
}
