<?php

namespace Tests\Feature\Commerce;

use App\Models\User;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Contracts\PaymentProviderAdapter;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use KMJ\MainPlatform\Commerce\Services\PaymentReconciler;
use KMJ\MainPlatform\Commerce\ValueObjects\ProviderPaymentConfirmation;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class PaymentReconciliationTest extends TestCase
{
    use RefreshDatabase;

    public function test_confirmed_provider_evidence_reconciles_idempotently_without_granting_entitlement(): void
    {
        $requester = User::factory()->create();
        $operator = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Provider Reconciliation Lab', $requester->id);
        $product = Product::query()->create([
            'slug' => 'provider-reconciliation-preview',
            'name' => 'Provider Reconciliation Preview',
            'status' => 'preview',
        ]);

        $orders = app(CommercialOrderService::class);
        $order = $orders->request(
            $organization->getKey(),
            $product->getKey(),
            $requester->id,
            'request:provider-reconciliation:1',
        );

        $adapter = new class implements PaymentProviderAdapter
        {
            public function provider(): string
            {
                return 'fixture-pay';
            }

            public function confirmation(string $providerReference): ProviderPaymentConfirmation
            {
                return new ProviderPaymentConfirmation('fixture-pay', $providerReference, 'INR', 249900);
            }
        };

        $reconciler = app(PaymentReconciler::class);
        $confirmed = $reconciler->reconcileConfirmed($order->getKey(), $operator->id, $adapter, 'pay-001');

        self::assertSame('confirmed', $confirmed->status);
        self::assertSame('INR', $confirmed->currency);
        self::assertSame(249900, $confirmed->amount_minor);
        self::assertSame('fixture-pay:pay-001', $confirmed->confirmation_reference);
        $this->assertDatabaseCount('entitlements', 0);
        $this->assertDatabaseHas('commerce_ledger', [
            'order_id' => $order->getKey(),
            'actor_user_id' => $operator->id,
            'event_type' => 'commerce.order.confirmed',
        ]);

        $replayed = $reconciler->reconcileConfirmed($order->getKey(), $operator->id, $adapter, 'pay-001');
        self::assertSame($order->getKey(), $replayed->getKey());
        $this->assertDatabaseCount('commerce_ledger', 2);
        $this->assertDatabaseCount('entitlements', 0);
    }

    public function test_provider_evidence_mismatch_is_rejected_fail_closed(): void
    {
        $requester = User::factory()->create();
        $operator = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Mismatch Lab', $requester->id);
        $product = Product::query()->create([
            'slug' => 'mismatch-preview',
            'name' => 'Mismatch Preview',
            'status' => 'preview',
        ]);

        $orders = app(CommercialOrderService::class);
        $order = $orders->request(
            $organization->getKey(),
            $product->getKey(),
            $requester->id,
            'request:mismatch:1',
        );

        $adapter = new class implements PaymentProviderAdapter
        {
            public function provider(): string
            {
                return 'fixture-pay';
            }

            public function confirmation(string $providerReference): ProviderPaymentConfirmation
            {
                return new ProviderPaymentConfirmation('other-provider', $providerReference, 'INR', 1000);
            }
        };

        try {
            app(PaymentReconciler::class)->reconcileConfirmed($order->getKey(), $operator->id, $adapter, 'pay-mismatch');
            self::fail('Expected mismatched provider evidence to be rejected.');
        } catch (DomainException $exception) {
            self::assertStringContainsString('does not match', $exception->getMessage());
        }

        self::assertSame('requested', $order->refresh()->status);
        $this->assertDatabaseCount('commerce_ledger', 1);
        $this->assertDatabaseCount('entitlements', 0);
    }
}
