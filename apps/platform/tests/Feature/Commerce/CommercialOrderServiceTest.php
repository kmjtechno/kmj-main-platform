<?php

namespace Tests\Feature\Commerce;

use App\Models\User;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use InvalidArgumentException;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class CommercialOrderServiceTest extends TestCase
{
    use RefreshDatabase;

    public function test_order_request_is_idempotent_and_does_not_grant_entitlement(): void
    {
        $user = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Revenue Lab', $user->id);
        $product = Product::query()->create([
            'slug' => 'revenue-preview',
            'name' => 'Revenue Preview Product',
            'status' => 'preview',
        ]);

        $orders = app(CommercialOrderService::class);
        $first = $orders->request(
            $organization->getKey(),
            $product->getKey(),
            $user->id,
            'request:revenue-preview:1',
        );
        $second = $orders->request(
            $organization->getKey(),
            $product->getKey(),
            $user->id,
            'request:revenue-preview:1',
        );

        self::assertSame($first->getKey(), $second->getKey());
        self::assertSame('requested', $first->status);
        $this->assertDatabaseCount('commerce_orders', 1);
        $this->assertDatabaseCount('commerce_ledger', 1);
        $this->assertDatabaseCount('entitlements', 0);
        $this->assertDatabaseHas('commerce_ledger', [
            'order_id' => $first->getKey(),
            'event_type' => 'commerce.order.requested',
        ]);
        $this->assertDatabaseHas('outbox_messages', [
            'event_type' => 'commerce.order.requested',
            'aggregate_type' => 'commercial_order',
            'aggregate_id' => $first->getKey(),
            'organization_id' => $organization->getKey(),
        ]);
        $this->assertDatabaseCount('outbox_messages', 1);
    }

    public function test_confirmation_records_commercial_fact_but_still_does_not_grant_entitlement(): void
    {
        $requester = User::factory()->create();
        $operator = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Paid Customer', $requester->id);
        $product = Product::query()->create([
            'slug' => 'commercial-preview',
            'name' => 'Commercial Preview Product',
            'status' => 'preview',
        ]);

        $orders = app(CommercialOrderService::class);
        $order = $orders->request(
            $organization->getKey(),
            $product->getKey(),
            $requester->id,
            'request:commercial-preview:1',
        );

        $confirmed = $orders->confirm(
            $order->getKey(),
            $operator->id,
            'INR',
            125000,
            'manual-receipt-001',
        );

        self::assertSame('confirmed', $confirmed->status);
        self::assertSame('INR', $confirmed->currency);
        self::assertSame(125000, $confirmed->amount_minor);
        self::assertSame('manual-receipt-001', $confirmed->confirmation_reference);
        $this->assertDatabaseCount('entitlements', 0);
        $this->assertDatabaseHas('commerce_ledger', [
            'order_id' => $order->getKey(),
            'actor_user_id' => $operator->id,
            'event_type' => 'commerce.order.confirmed',
        ]);

        $replayed = $orders->confirm(
            $order->getKey(),
            $operator->id,
            'INR',
            125000,
            'manual-receipt-001',
        );
        self::assertSame($order->getKey(), $replayed->getKey());
        $this->assertDatabaseCount('commerce_ledger', 2);
        $this->assertDatabaseHas('outbox_messages', [
            'event_type' => 'commerce.order.confirmed',
            'aggregate_type' => 'commercial_order',
            'aggregate_id' => $order->getKey(),
            'organization_id' => $organization->getKey(),
        ]);
        $this->assertDatabaseCount('outbox_messages', 2);
    }

    public function test_confirmation_rejects_zero_value_payment_evidence(): void
    {
        $requester = User::factory()->create();
        $operator = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Zero Value Guard', $requester->id);
        $product = Product::query()->create([
            'slug' => 'zero-value-guard',
            'name' => 'Zero Value Guard Product',
            'status' => 'preview',
        ]);

        $orders = app(CommercialOrderService::class);
        $order = $orders->request(
            $organization->getKey(),
            $product->getKey(),
            $requester->id,
            'request:zero-value-guard:1',
        );

        $this->expectException(InvalidArgumentException::class);
        $orders->confirm(
            $order->getKey(),
            $operator->id,
            'INR',
            0,
            'zero-value-reference',
        );
    }

    public function test_confirmation_reference_cannot_be_reused_for_another_order(): void
    {
        $requester = User::factory()->create();
        $operator = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Payment Evidence Guard', $requester->id);
        $product = Product::query()->create([
            'slug' => 'payment-evidence-guard',
            'name' => 'Payment Evidence Guard Product',
            'status' => 'preview',
        ]);

        $orders = app(CommercialOrderService::class);
        $first = $orders->request(
            $organization->getKey(),
            $product->getKey(),
            $requester->id,
            'request:payment-evidence-guard:1',
        );
        $second = $orders->request(
            $organization->getKey(),
            $product->getKey(),
            $requester->id,
            'request:payment-evidence-guard:2',
        );

        $orders->confirm(
            $first->getKey(),
            $operator->id,
            'INR',
            125000,
            'manual-receipt-unique-001',
        );

        $this->expectException(DomainException::class);
        $orders->confirm(
            $second->getKey(),
            $operator->id,
            'INR',
            125000,
            'manual-receipt-unique-001',
        );
    }

    public function test_idempotency_key_cannot_be_reused_for_different_commercial_request(): void
    {
        $user = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Idempotency Lab', $user->id);
        $firstProduct = Product::query()->create([
            'slug' => 'commerce-a',
            'name' => 'Commerce A',
            'status' => 'preview',
        ]);
        $secondProduct = Product::query()->create([
            'slug' => 'commerce-b',
            'name' => 'Commerce B',
            'status' => 'preview',
        ]);

        $orders = app(CommercialOrderService::class);
        $orders->request($organization->getKey(), $firstProduct->getKey(), $user->id, 'same-key');

        $this->expectException(DomainException::class);
        $orders->request($organization->getKey(), $secondProduct->getKey(), $user->id, 'same-key');
    }
}
