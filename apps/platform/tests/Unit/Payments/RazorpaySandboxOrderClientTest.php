<?php

declare(strict_types=1);

namespace Tests\Unit\Payments;

use App\Services\Payments\RazorpaySandboxOrderClient;
use DomainException;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

final class RazorpaySandboxOrderClientTest extends TestCase
{
    private RazorpaySandboxOrderClient $client;

    protected function setUp(): void
    {
        parent::setUp();
        Http::preventStrayRequests();
        $this->client = new RazorpaySandboxOrderClient;
    }

    private function create(string $key = 'rzp_test_ABC123', int $amount = 199900, string $currency = 'INR'): array
    {
        return $this->client->create(
            'kmj_receipt_001', $amount, $currency, $key, 'test-secret-123',
        );
    }

    private function providerOrder(): array
    {
        return [
            'id' => 'order_AAABBB123',
            'entity' => 'order',
            'amount' => 199900,
            'currency' => 'INR',
            'receipt' => 'kmj_receipt_001',
            'status' => 'created',
            'amount_paid' => 0,
            'amount_due' => 199900,
        ];
    }

    public function test_test_key_only_server_side_order_uses_minor_units_and_disables_partial_payments(): void
    {
        Http::fake(['api.razorpay.com/v1/orders' => Http::response($this->providerOrder(), 200)]);

        self::assertSame([
            'order_id' => 'order_AAABBB123',
            'amount_minor' => 199900,
            'currency' => 'INR',
        ], $this->create());

        Http::assertSent(fn (Request $request): bool => $request->method() === 'POST'
            && $request->url() === 'https://api.razorpay.com/v1/orders'
            && $request->hasHeader('Authorization', 'Basic '.base64_encode('rzp_test_ABC123:test-secret-123'))
            && $request['receipt'] === 'kmj_receipt_001'
            && $request['amount'] === 199900
            && $request['currency'] === 'INR'
            && $request['partial_payment'] === false);
    }

    public function test_live_key_and_invalid_order_never_issue_an_api_request(): void
    {
        Http::fake();
        foreach ([
            ['kmj_receipt_001', 199900, 'INR', 'rzp_live_ABC123', 'test-secret-123'],
            ['kmj_receipt_001', 0, 'INR', 'rzp_test_ABC123', 'test-secret-123'],
            ['kmj_receipt_001', 199900, 'USD', 'rzp_test_ABC123', 'test-secret-123'],
            ['../../wrong', 199900, 'INR', 'rzp_test_ABC123', 'test-secret-123'],
            ['kmj_receipt_001', 199900, 'INR', 'rzp_test_ABC123', ''],
            ['kmj_receipt_001', 199900, 'INR', 'rzp_test_ABC123', "secret\r\nInjected"],
        ] as $values) {
            try {
                $this->client->create(...$values);
                self::fail('Invalid sandbox order was not rejected.');
            } catch (DomainException $exception) {
                self::assertSame('RAZORPAY_SANDBOX_INVALID_ORDER', $exception->getMessage());
            }
        }
        Http::assertNothingSent();
    }

    public function test_amount_currency_receipt_and_provider_order_id_must_match(): void
    {
        $valid = $this->providerOrder();
        foreach ([
            ['amount' => 190000],
            ['currency' => 'USD'],
            ['receipt' => 'another_receipt'],
            ['status' => 'paid'],
            ['id' => 'evil_id'],
            ['amount_paid' => 1],
            ['amount_due' => 199899],
        ] as $mismatch) {
            Http::fake(['api.razorpay.com/v1/orders' => Http::response(array_replace($valid, $mismatch), 200)]);
            try {
                $this->create();
                self::fail('Mismatched provider order was accepted.');
            } catch (DomainException $exception) {
                self::assertSame('RAZORPAY_SANDBOX_ORDER_MISMATCH', $exception->getMessage());
            }
        }
    }

    public function test_provider_failure_does_not_create_checkout_session(): void
    {
        Http::fake(['api.razorpay.com/v1/orders' => Http::response(['error' => 'unavailable'], 503)]);
        $this->expectExceptionMessage('RAZORPAY_SANDBOX_PROVIDER_UNAVAILABLE');
        $this->create();
    }
}
