<?php

namespace Tests\Feature;

use App\Models\User;
use DateTimeInterface;
use Illuminate\Foundation\Testing\RefreshDatabase;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Catalog\Services\ProductCatalog;
use KMJ\MainPlatform\Commerce\Contracts\DomainEventRecorder as CommerceDomainEventRecorder;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use KMJ\MainPlatform\Entitlements\Contracts\DomainEventRecorder as EntitlementDomainEventRecorder;
use KMJ\MainPlatform\Entitlements\Services\EntitlementIssuer;
use KMJ\MainPlatform\Entitlements\Services\EntitlementPolicyRegistry;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use RuntimeException;
use Tests\TestCase;

final class DomainEventAtomicityTest extends TestCase
{
    use RefreshDatabase;

    public function test_commerce_write_rolls_back_when_outbox_recording_fails(): void
    {
        $user = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Atomic Commerce', $user->id);
        $product = Product::query()->create([
            'slug' => 'atomic-commerce',
            'name' => 'Atomic Commerce',
            'status' => 'preview',
        ]);

        $this->app->instance(CommerceDomainEventRecorder::class, $this->failingCommerceRecorder());

        try {
            app(CommercialOrderService::class)->request(
                $organization->getKey(),
                $product->getKey(),
                $user->id,
                'atomic-commerce-request',
            );
            self::fail('Expected outbox failure.');
        } catch (RuntimeException $exception) {
            self::assertSame('simulated outbox failure', $exception->getMessage());
        }

        $this->assertDatabaseCount('commerce_orders', 0);
        $this->assertDatabaseCount('commerce_ledger', 0);
        $this->assertDatabaseCount('outbox_messages', 0);
    }

    public function test_entitlement_write_rolls_back_when_outbox_recording_fails(): void
    {
        $user = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Atomic Entitlement', $user->id);
        $product = app(ProductCatalog::class)->ensureSandboxProduct('atomic-entitlement', 'Atomic Entitlement');
        $policy = app(EntitlementPolicyRegistry::class)->ensure(
            $product->getKey(),
            'atomic.entitlement',
            'atomic.entitlement.access',
        );

        $this->app->instance(EntitlementDomainEventRecorder::class, $this->failingEntitlementRecorder());

        try {
            app(EntitlementIssuer::class)->issue(
                $organization->getKey(),
                $policy,
                'atomic-entitlement-request',
            );
            self::fail('Expected outbox failure.');
        } catch (RuntimeException $exception) {
            self::assertSame('simulated outbox failure', $exception->getMessage());
        }

        $this->assertDatabaseCount('entitlements', 0);
        $this->assertDatabaseCount('entitlement_ledger', 0);
        $this->assertDatabaseCount('outbox_messages', 0);
    }

    private function failingCommerceRecorder(): CommerceDomainEventRecorder
    {
        return new class implements CommerceDomainEventRecorder
        {
            public function recordDomainEvent(
                string $eventType,
                string $aggregateType,
                string $aggregateId,
                array $payload,
                ?string $organizationId,
                string $idempotencyKey,
                DateTimeInterface $occurredAt,
            ): void {
                throw new RuntimeException('simulated outbox failure');
            }
        };
    }

    private function failingEntitlementRecorder(): EntitlementDomainEventRecorder
    {
        return new class implements EntitlementDomainEventRecorder
        {
            public function recordDomainEvent(
                string $eventType,
                string $aggregateType,
                string $aggregateId,
                array $payload,
                ?string $organizationId,
                string $idempotencyKey,
                DateTimeInterface $occurredAt,
            ): void {
                throw new RuntimeException('simulated outbox failure');
            }
        };
    }
}
