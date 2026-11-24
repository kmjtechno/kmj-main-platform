<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\AuthorityBootstrapper;
use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use App\Services\Licensing\Kslp\KslpResellerSettlementReadinessInspector;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use Tests\TestCase;

final class KslpResellerSettlementReadinessInspectorTest extends TestCase
{
    use RefreshDatabase;

    /** @return array{0: string, 1: string, 2: string} */
    private function seedOrder(User $actor, string $suffix): array
    {
        $org = app(AuthorityBootstrapper::class)->createOrganizationWithSandboxAccess(
            'Funding Inspector '.$suffix,
            $actor->id
        );
        $orgId = (string) $org->getKey();
        $issuer = app(KslpIssuerSubscriptionAuthority::class);
        $issuer->subscribe($orgId, 'professional', 2, 5);
        $licensed = $issuer->registerProduct($orgId, 'FUNDING.'.$suffix, 'Funding App '.$suffix);
        $product = Product::query()->create([
            'slug' => 'funding-inspector-'.strtolower($suffix),
            'name' => 'Funding Inspector Purchase '.$suffix,
            'status' => 'preview',
        ]);
        $order = app(CommercialOrderService::class)->request(
            $orgId, (string) $product->getKey(), $actor->id, 'funding-inspector-'.$suffix
        );

        return [$orgId, (string) $licensed['id'], (string) $order->getKey()];
    }

    /** @param array<string, mixed> $overrides */
    private function providerLink(string $orderId, array $overrides = []): void
    {
        DB::table('commerce_provider_orders')->insert(array_merge([
            'commercial_order_id' => $orderId,
            'provider' => 'razorpay',
            'provider_order_id' => 'order_FUNDING1',
            'amount_minor' => 25000,
            'currency' => 'INR',
            'environment' => 'sandbox',
            'created_at' => now(),
            'updated_at' => now(),
        ], $overrides));
    }

    /** @param array<string, mixed> $overrides */
    private function receipt(array $overrides = []): void
    {
        DB::table('payment_webhook_events')->insert(array_merge([
            'provider' => 'razorpay',
            'event_id' => 'evt_FUNDING1',
            'event_type' => 'payment.captured',
            'provider_order_id' => 'order_FUNDING1',
            'provider_payment_id' => 'pay_FUNDING1',
            'payload_sha256' => hash('sha256', 'sanitized-test-inbox'),
            'processing_status' => 'reconciled',
            'received_at' => now(),
            'created_at' => now(),
            'updated_at' => now(),
        ], $overrides));
    }

    public function test_pending_and_manually_confirmed_orders_cannot_fund_reseller_credit(): void
    {
        $actor = User::factory()->create(['email_verified_at' => now()]);
        [$org, $product, $order] = $this->seedOrder($actor, 'ALPHA');
        $initialEntitlements = DB::table('entitlements')->count();
        $inspector = app(KslpResellerSettlementReadinessInspector::class);

        $pending = $inspector->inspect($actor->id, $org, $product, $order);
        self::assertContains('COMMERCIAL_ORDER_NOT_CONFIRMED', $pending['blocked_reasons']);
        self::assertContains('TRUSTED_PROVIDER_ORDER_LINK_MISSING', $pending['blocked_reasons']);

        app(CommercialOrderService::class)->confirm(
            $order, $actor->id, 'INR', 25000, 'owner-manual-reference'
        );
        $confirmed = $inspector->inspect($actor->id, $org, $product, $order);
        self::assertNotContains('COMMERCIAL_ORDER_NOT_CONFIRMED', $confirmed['blocked_reasons']);
        self::assertContains('LIVE_MERCHANT_SETTLEMENT_UNVERIFIED', $confirmed['blocked_reasons']);
        self::assertContains('PRODUCT_ORDER_SKU_MAPPING_UNVERIFIED', $confirmed['blocked_reasons']);
        self::assertSame('blocked_source_review_only', $confirmed['status']);
        self::assertFalse($confirmed['verified_live_settlement']);
        self::assertFalse($confirmed['paid_issuance_enabled']);
        self::assertNull($confirmed['available_credits']);
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('entitlements', $initialEntitlements);
    }

    public function test_matching_reconciled_sandbox_webhook_still_never_authorizes_live_credits(): void
    {
        $actor = User::factory()->create(['email_verified_at' => now()]);
        [$org, $product, $order] = $this->seedOrder($actor, 'BETA');
        $initialEntitlements = DB::table('entitlements')->count();
        app(CommercialOrderService::class)->confirm(
            $order, $actor->id, 'INR', 25000, 'razorpay:pay_FUNDING1'
        );
        $this->providerLink($order);
        $this->receipt();

        $evidence = app(KslpResellerSettlementReadinessInspector::class)
            ->inspect($actor->id, $org, $product, $order);

        self::assertSame(1, $evidence['linked_provider_orders']);
        self::assertSame(1, $evidence['reconciled_webhook_receipts']);
        self::assertSame(0, $evidence['reversal_signals']);
        self::assertContains('PROVIDER_NOT_LIVE', $evidence['blocked_reasons']);
        self::assertContains('LIVE_MERCHANT_SETTLEMENT_UNVERIFIED', $evidence['blocked_reasons']);
        self::assertFalse($evidence['verified_live_settlement']);
        self::assertFalse($evidence['paid_issuance_enabled']);
        self::assertNull($evidence['available_credits']);
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('entitlements', $initialEntitlements);
    }

    public function test_refund_signal_and_wrong_provider_amount_are_exposed_as_blockers_only(): void
    {
        $actor = User::factory()->create(['email_verified_at' => now()]);
        [$org, $product, $order] = $this->seedOrder($actor, 'GAMMA');
        app(CommercialOrderService::class)->confirm(
            $order, $actor->id, 'INR', 25000, 'razorpay:pay_FUNDING1'
        );
        $this->providerLink($order, ['amount_minor' => 24900]);
        $this->receipt([
            'event_type' => 'payment.refunded',
            'processing_status' => 'received',
        ]);

        $evidence = app(KslpResellerSettlementReadinessInspector::class)
            ->inspect($actor->id, $org, $product, $order);

        self::assertSame(1, $evidence['reversal_signals']);
        self::assertContains('PAYMENT_REVERSAL_SIGNAL_PRESENT', $evidence['blocked_reasons']);
        self::assertContains('PROVIDER_LINK_FINANCIAL_MISMATCH', $evidence['blocked_reasons']);
        self::assertContains('RECONCILED_PROVIDER_RECEIPT_MISSING', $evidence['blocked_reasons']);
        self::assertFalse($evidence['paid_issuance_enabled']);
        $this->assertDatabaseCount('kslp_licenses', 0);
    }

    public function test_forged_live_link_with_reconciled_inbox_stays_blocked_without_real_settlement(): void
    {
        $actor = User::factory()->create(['email_verified_at' => now()]);
        [$org, $product, $order] = $this->seedOrder($actor, 'ZETA');
        $initialEntitlements = DB::table('entitlements')->count();
        app(CommercialOrderService::class)->confirm(
            $order, $actor->id, 'INR', 25000, 'razorpay:pay_FUNDING1'
        );
        // Forged local rows cannot substitute for independent live merchant,
        // refund, KYC, price/SKU or product-signature validation.
        $this->providerLink($order, ['environment' => 'live']);
        $this->receipt();

        $evidence = app(KslpResellerSettlementReadinessInspector::class)
            ->inspect($actor->id, $org, $product, $order);

        self::assertNotContains('PROVIDER_NOT_LIVE', $evidence['blocked_reasons']);
        self::assertContains('LIVE_MERCHANT_SETTLEMENT_UNVERIFIED', $evidence['blocked_reasons']);
        self::assertContains('PRODUCT_ORDER_SKU_MAPPING_UNVERIFIED', $evidence['blocked_reasons']);
        self::assertContains('REFUND_CHARGEBACK_LIFECYCLE_NOT_READY', $evidence['blocked_reasons']);
        self::assertFalse($evidence['verified_live_settlement']);
        self::assertFalse($evidence['paid_issuance_enabled']);
        self::assertNull($evidence['available_credits']);
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('entitlements', $initialEntitlements);
    }

    public function test_other_tenant_is_denied_before_any_payment_inspection(): void
    {
        $ownerA = User::factory()->create(['email_verified_at' => now()]);
        $ownerB = User::factory()->create(['email_verified_at' => now()]);
        [$orgA, $productA, $orderA] = $this->seedOrder($ownerA, 'DELTA');
        [, , $orderB] = $this->seedOrder($ownerB, 'EPSILON');
        $inspector = app(KslpResellerSettlementReadinessInspector::class);

        try {
            $inspector->inspect($ownerB->id, $orgA, $productA, $orderA);
            self::fail('Foreign tenant must not see payment metadata.');
        } catch (DomainException $exception) {
            self::assertSame('KSLP_RESELLER_FUNDING_ACCESS_DENIED', $exception->getMessage());
        }

        try {
            $inspector->inspect($ownerA->id, $orgA, $productA, $orderB);
            self::fail('Foreign order must not be enumerated.');
        } catch (DomainException $exception) {
            self::assertSame('KSLP_RESELLER_FUNDING_SCOPE_DENIED', $exception->getMessage());
        }
    }
}
