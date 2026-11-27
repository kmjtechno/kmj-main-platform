<?php

namespace Tests\Feature\Commerce;

use App\Models\User;
use App\Services\Commerce\OrderRefundRecorder;
use App\Services\Commerce\RefundEntitlementRevoker;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Entitlements\Services\EntitlementIssuer;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class RefundEntitlementRevokerTest extends TestCase
{
    use RefreshDatabase;

    /** @return array{0:User,1:string,2:Entitlement,3:string,4:string,5:string} */
    private function fixture(): array
    {
        $owner = User::factory()->create(['is_platform_owner' => true, 'email_verified_at' => now()]);
        DB::table('passkeys')->insert([
            'user_id' => $owner->id, 'name' => 'Owner passkey',
            'credential_id' => 'revoke-test-credential-'.$owner->id, 'credential' => '{}',
            'created_at' => now(), 'updated_at' => now(),
        ]);
        $requester = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Revoke Lab', $requester->id);
        $product = Product::query()->create(['slug' => 'revoke-lab', 'name' => 'Revoke Lab', 'status' => 'preview']);
        $policy = EntitlementPolicy::query()->create([
            'product_id' => $product->getKey(),
            'code' => 'revoke-lab.default',
            'capability' => 'revoke.lab.access',
            'status' => 'active',
        ]);
        $entitlement = app(EntitlementIssuer::class)->issue($organization->getKey(), $policy, 'revoke-lab-entitlement');
        $orders = app(CommercialOrderService::class);
        $order = $orders->request($organization->getKey(), $product->getKey(), $requester->id, 'request:revoke-lab:1');
        $orders->confirm($order->getKey(), $owner->id, 'INR', 100000, 'manual-receipt-revoke-1');

        return [$owner, (string) $order->getKey(), $entitlement, (string) $organization->getKey(), (string) $product->getKey(), (string) $requester->id];
    }

    public function test_a_refund_record_alone_never_revokes_access(): void
    {
        [$owner, $orderId, $entitlement] = $this->fixture();

        app(OrderRefundRecorder::class)->record($owner->id, $orderId, 100000, 'full refund', 'revoke-key-0001');

        self::assertSame('active', $entitlement->fresh()->status);
    }

    public function test_revocation_requires_a_recorded_refund(): void
    {
        [$owner, $orderId, $entitlement] = $this->fixture();

        try {
            app(RefundEntitlementRevoker::class)->revoke($owner->id, $orderId);
            self::fail('Revocation without a refund record must be refused');
        } catch (DomainException $e) {
            self::assertSame('REFUND_REVOKE_REFUND_RECORD_REQUIRED', $e->getMessage());
        }
        self::assertSame('active', $entitlement->fresh()->status);
    }

    public function test_owner_revokes_after_refund_and_it_is_audited_and_idempotent(): void
    {
        [$owner, $orderId, $entitlement] = $this->fixture();
        app(OrderRefundRecorder::class)->record($owner->id, $orderId, 100000, 'full refund', 'revoke-key-0002');

        $result = app(RefundEntitlementRevoker::class)->revoke($owner->id, $orderId);
        self::assertSame(1, $result['revoked']);
        self::assertSame('revoked', $entitlement->fresh()->status);
        $this->assertDatabaseHas('operator_action_audits', ['action' => 'order.refund.entitlement_revoke']);

        $again = app(RefundEntitlementRevoker::class)->revoke($owner->id, $orderId);
        self::assertSame(0, $again['revoked']);
        self::assertSame(1, $again['already_revoked']);
    }

    public function test_non_owner_cannot_revoke(): void
    {
        [$owner, $orderId, $entitlement] = $this->fixture();
        app(OrderRefundRecorder::class)->record($owner->id, $orderId, 100000, 'full refund', 'revoke-key-0003');
        $other = User::factory()->create();

        try {
            app(RefundEntitlementRevoker::class)->revoke($other->id, $orderId);
            self::fail('Only the platform owner may revoke');
        } catch (DomainException $e) {
            self::assertSame('REFUND_REVOKE_NOT_AUTHORIZED', $e->getMessage());
        }
        self::assertSame('active', $entitlement->fresh()->status);
    }

    public function test_revocation_is_refused_while_another_paid_order_for_the_same_product_exists(): void
    {
        [$owner, $orderId, $entitlement, $organizationId, $productId, $requesterId] = $this->fixture();
        $orders = app(CommercialOrderService::class);
        $second = $orders->request($organizationId, $productId, (int) $requesterId, 'request:revoke-lab:2');
        $orders->confirm($second->getKey(), $owner->id, 'INR', 50000, 'manual-receipt-revoke-2');
        app(OrderRefundRecorder::class)->record($owner->id, $orderId, 100000, 'first order refunded', 'revoke-key-0004');

        try {
            app(RefundEntitlementRevoker::class)->revoke($owner->id, $orderId);
            self::fail('Another paid order must block revocation');
        } catch (DomainException $e) {
            self::assertSame('REFUND_REVOKE_OTHER_PAID_ORDER_EXISTS', $e->getMessage());
        }
        self::assertSame('active', $entitlement->fresh()->status);
    }
}
