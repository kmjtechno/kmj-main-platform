<?php

declare(strict_types=1);

namespace Tests\Feature\Commerce;

use App\Models\User;
use App\Services\Payments\RazorpayPaymentAdapter;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use InvalidArgumentException;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use KMJ\MainPlatform\Commerce\Services\PaymentReconciler;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

final class RazorpayPaymentAdapterTest extends TestCase
{
    use RefreshDatabase;

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

    /** @param array<string, mixed> $override */
    private function fakePayment(array $override = [], int $status = 200): void
    {
        Http::fake(['api.razorpay.com/v1/payments/*' => Http::response(array_merge([
            'id' => 'pay_ABC123',
            'status' => 'captured',
            'captured' => true,
            'currency' => 'INR',
            'amount' => 249900,
            'amount_refunded' => 0,
        ], $override), $status)]);
    }

    public function test_captured_payment_returns_provider_evidence_using_vault_test_keys(): void
    {
        $this->vault();
        $this->fakePayment();

        $confirmation = app(RazorpayPaymentAdapter::class)->confirmation('pay_ABC123');

        $this->assertSame('razorpay', $confirmation->provider);
        $this->assertSame('pay_ABC123', $confirmation->reference);
        $this->assertSame('INR', $confirmation->currency);
        $this->assertSame(249900, $confirmation->amountMinor);
        Http::assertSent(fn (Request $request): bool => $request->method() === 'GET'
            && $request->url() === 'https://api.razorpay.com/v1/payments/pay_ABC123'
            && str_starts_with($request->header('Authorization')[0] ?? '', 'Basic '));
    }

    /** @return array<string, array{0: array<string, mixed>}> */
    public static function unsettledPayments(): array
    {
        return [
            'authorized only' => [['status' => 'authorized', 'captured' => false]],
            'failed' => [['status' => 'failed', 'captured' => false]],
            'status captured but flag false' => [['captured' => false]],
            'different payment id' => [['id' => 'pay_OTHER999']],
            'refunded' => [['amount_refunded' => 100]],
            'zero amount' => [['amount' => 0]],
            'string amount' => [['amount' => '249900']],
            'missing currency' => [['currency' => null]],
        ];
    }

    /** @param array<string, mixed> $override */
    #[DataProvider('unsettledPayments')]
    public function test_anything_short_of_a_captured_unrefunded_exact_payment_fails_closed(array $override): void
    {
        $this->vault();
        $this->fakePayment($override);

        $this->expectException(DomainException::class);
        app(RazorpayPaymentAdapter::class)->confirmation('pay_ABC123');
    }

    public function test_confirmation_can_be_bound_to_the_expected_provider_order(): void
    {
        $this->vault();
        $this->fakePayment(['order_id' => 'order_MINE1']);
        $adapter = app(RazorpayPaymentAdapter::class);

        $this->assertSame(249900, $adapter->confirmationForProviderOrder('pay_ABC123', 'order_MINE1')->amountMinor);

        $this->expectException(DomainException::class);
        $adapter->confirmationForProviderOrder('pay_ABC123', 'order_OTHER2');
    }

    public function test_provider_error_and_missing_credentials_fail_closed(): void
    {
        $this->fakePayment([], 500);
        try {
            app(RazorpayPaymentAdapter::class)->confirmation('pay_ABC123');
            $this->fail('Missing vault must not be treated as confirmation.');
        } catch (DomainException $exception) {
            $this->assertSame('RAZORPAY_SANDBOX_CREDENTIALS_NOT_READY', $exception->getMessage());
        }

        $this->vault();
        try {
            app(RazorpayPaymentAdapter::class)->confirmation('pay_ABC123');
            $this->fail('A provider error must not be treated as confirmation.');
        } catch (DomainException $exception) {
            $this->assertSame('RAZORPAY_PROVIDER_UNAVAILABLE', $exception->getMessage());
        }
    }

    public function test_malformed_reference_never_reaches_the_provider(): void
    {
        $this->vault();
        Http::fake();

        foreach (['', 'order_ABC', 'pay_', 'pay_../x', "pay_AB\nC"] as $bad) {
            try {
                app(RazorpayPaymentAdapter::class)->confirmation($bad);
                $this->fail('Malformed reference accepted: '.json_encode($bad));
            } catch (InvalidArgumentException) {
                $this->addToAssertionCount(1);
            }
        }
        Http::assertNothingSent();
    }

    public function test_reconciler_confirms_order_from_provider_evidence_without_granting_entitlement(): void
    {
        $this->vault();
        $this->fakePayment();
        $requester = User::factory()->create();
        $operator = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Razorpay Adapter Lab', $requester->id);
        $product = Product::query()->create([
            'slug' => 'razorpay-adapter-preview',
            'name' => 'Razorpay Adapter Preview',
            'status' => 'preview',
        ]);
        $order = app(CommercialOrderService::class)->request(
            $organization->getKey(),
            $product->getKey(),
            $requester->id,
            'request:razorpay-adapter:1',
        );

        $confirmed = app(PaymentReconciler::class)->reconcileConfirmed(
            $order->getKey(),
            $operator->id,
            app(RazorpayPaymentAdapter::class),
            'pay_ABC123',
        );

        $this->assertSame('confirmed', $confirmed->status);
        $this->assertSame('razorpay:pay_ABC123', $confirmed->confirmation_reference);
        $this->assertSame(249900, $confirmed->amount_minor);
        $this->assertDatabaseCount('entitlements', 0);
    }
}
