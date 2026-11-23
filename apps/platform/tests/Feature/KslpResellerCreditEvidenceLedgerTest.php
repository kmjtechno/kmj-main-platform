<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\AuthorityBootstrapper;
use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use App\Services\Licensing\Kslp\KslpResellerCreditEvidenceLedger;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use Tests\TestCase;

final class KslpResellerCreditEvidenceLedgerTest extends TestCase
{
    use RefreshDatabase;

    /** @return array{0: string, 1: string, 2: string} */
    private function seedIssuer(User $actor, string $suffix): array
    {
        $organization = app(AuthorityBootstrapper::class)
            ->createOrganizationWithSandboxAccess('Reseller Evidence '.$suffix, $actor->id);
        $organizationId = (string) $organization->getKey();

        $issuer = app(KslpIssuerSubscriptionAuthority::class);
        $issuer->subscribe($organizationId, 'professional', 2, 5);
        $licensedProduct = $issuer->registerProduct(
            $organizationId, 'EVIDENCE.'.$suffix, 'Evidence Application '.$suffix
        );

        $catalog = Product::query()->create([
            'slug' => 'evidence-order-'.strtolower($suffix),
            'name' => 'Reseller Funding Evidence '.$suffix,
            'status' => 'preview',
        ]);
        $order = app(CommercialOrderService::class)->request(
            $organizationId,
            (string) $catalog->getKey(),
            $actor->id,
            'reseller-evidence-order-'.$suffix,
        );

        return [$organizationId, (string) $licensedProduct['id'], (string) $order->getKey()];
    }

    public function test_pending_evidence_is_idempotent_and_even_manual_confirmation_mints_zero_credits(): void
    {
        $actor = User::factory()->create(['email_verified_at' => now()]);
        [$organizationId, $licensedProductId, $orderId] = $this->seedIssuer($actor, 'ALPHA');
        $ledger = app(KslpResellerCreditEvidenceLedger::class);

        $first = $ledger->queuePending($actor->id, $organizationId, $licensedProductId, $orderId, 'pending:alpha:one');
        $retry = $ledger->queuePending($actor->id, $organizationId, $licensedProductId, $orderId, 'pending:alpha:one');

        self::assertSame($first['sequence'], $retry['sequence']);
        self::assertSame('evidence_pending', $first['event_type']);
        self::assertSame('unverified', $first['evidence_state']);
        self::assertSame(0, (int) $first['credits_delta']);
        $this->assertDatabaseCount('kslp_reseller_credit_ledger', 1);
        self::assertSame(0, (int) DB::table('kslp_reseller_credit_ledger')->sum('credits_delta'));

        $order = app(CommercialOrderService::class)->confirm(
            $orderId, $actor->id, 'INR', 10000, 'manual-not-provider-verified'
        );
        self::assertSame('confirmed', $order->status);
        $snapshot = $ledger->snapshotForActor($actor->id, $organizationId);
        self::assertSame('funding_not_activated', $snapshot['status']);
        self::assertSame(1, $snapshot['pending_evidence_count']);
        self::assertNull($snapshot['available_credits']);
        self::assertFalse($snapshot['paid_issuance_enabled']);
        $this->assertDatabaseCount('kslp_licenses', 0);
    }

    public function test_foreign_actor_and_foreign_commercial_order_are_denied(): void
    {
        $ownerA = User::factory()->create(['email_verified_at' => now()]);
        $ownerB = User::factory()->create(['email_verified_at' => now()]);
        [$orgA, $productA] = $this->seedIssuer($ownerA, 'BETA');
        [$orgB, , $orderB] = $this->seedIssuer($ownerB, 'GAMMA');
        $ledger = app(KslpResellerCreditEvidenceLedger::class);

        try {
            $ledger->snapshotForActor($ownerB->id, $orgA);
            self::fail('A foreign user may not inspect reseller evidence.');
        } catch (DomainException $exception) {
            self::assertSame('KSLP_RESELLER_EVIDENCE_ACCESS_DENIED', $exception->getMessage());
        }

        try {
            $ledger->queuePending($ownerA->id, $orgA, $productA, $orderB, 'pending:foreign:order');
            self::fail('An order for another organization may not be attached.');
        } catch (DomainException $exception) {
            self::assertSame('KSLP_RESELLER_EVIDENCE_SCOPE_INVALID', $exception->getMessage());
        }

        self::assertSame(0, $ledger->snapshotForActor($ownerB->id, $orgB)['pending_evidence_count']);
        $this->assertDatabaseCount('kslp_reseller_credit_ledger', 0);
    }

    public function test_duplicate_order_and_reused_event_key_fail_closed_without_new_rows(): void
    {
        $actor = User::factory()->create(['email_verified_at' => now()]);
        [$org, $product, $order] = $this->seedIssuer($actor, 'DELTA');
        $ledger = app(KslpResellerCreditEvidenceLedger::class);

        $ledger->queuePending($actor->id, $org, $product, $order, 'pending:delta:original');

        try {
            $ledger->queuePending($actor->id, $org, $product, $order, 'pending:delta:different');
            self::fail('A different idempotency key cannot duplicate pending evidence.');
        } catch (DomainException $exception) {
            self::assertSame('KSLP_RESELLER_ORDER_ALREADY_QUEUED', $exception->getMessage());
        }

        $catalog = Product::query()->create([
            'slug' => 'evidence-order-delta-second',
            'name' => 'Second Requested Order',
            'status' => 'preview',
        ]);
        $anotherOrder = app(CommercialOrderService::class)->request(
            $org, (string) $catalog->getKey(), $actor->id, 'reseller-evidence-delta-second'
        );

        try {
            $ledger->queuePending(
                $actor->id, $org, $product, (string) $anotherOrder->getKey(), 'pending:delta:original'
            );
            self::fail('An idempotency key cannot be replayed against a different order.');
        } catch (DomainException $exception) {
            self::assertSame('KSLP_RESELLER_EVIDENCE_IDEMPOTENCY_CONFLICT', $exception->getMessage());
        }

        $this->assertDatabaseCount('kslp_reseller_credit_ledger', 1);
    }

    public function test_cancelled_order_cannot_be_queued_for_new_evidence(): void
    {
        $actor = User::factory()->create(['email_verified_at' => now()]);
        [$org, $product, $orderId] = $this->seedIssuer($actor, 'EPSILON');
        app(CommercialOrderService::class)->cancel($orderId, $actor->id);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('KSLP_RESELLER_ORDER_NOT_ELIGIBLE_FOR_REVIEW');

        app(KslpResellerCreditEvidenceLedger::class)
            ->queuePending($actor->id, $org, $product, $orderId, 'pending:cancelled:order');
    }
}
