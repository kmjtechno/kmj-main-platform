<?php

namespace Tests\Feature\Commerce;

use App\Models\User;
use App\Services\Commerce\OrderRefundRecorder;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class OrderRefundRecorderTest extends TestCase
{
    use RefreshDatabase;

    /** @return array{0:User,1:string,2:string} owner, confirmed order id, other (requested) order id */
    private function fixture(): array
    {
        $owner = User::factory()->create(['is_platform_owner' => true, 'email_verified_at' => now()]);
        DB::table('passkeys')->insert([
            'user_id' => $owner->id, 'name' => 'Owner passkey',
            'credential_id' => 'refund-test-credential-'.$owner->id, 'credential' => '{}',
            'created_at' => now(), 'updated_at' => now(),
        ]);
        $requester = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Refund Lab', $requester->id);
        $product = Product::query()->create(['slug' => 'refund-lab', 'name' => 'Refund Lab', 'status' => 'preview']);
        $orders = app(CommercialOrderService::class);
        $order = $orders->request($organization->getKey(), $product->getKey(), $requester->id, 'request:refund-lab:1');
        $orders->confirm($order->getKey(), $owner->id, 'INR', 100000, 'manual-receipt-refund-1');
        $pending = $orders->request($organization->getKey(), $product->getKey(), $requester->id, 'request:refund-lab:2');

        return [$owner, (string) $order->getKey(), (string) $pending->getKey()];
    }

    public function test_partial_refunds_accumulate_and_cannot_exceed_confirmed_amount(): void
    {
        [$owner, $orderId] = $this->fixture();
        $recorder = app(OrderRefundRecorder::class);

        $first = $recorder->record($owner->id, $orderId, 40000, 'customer request', 'refund-key-0001', 'rfnd_test_1');
        self::assertSame(40000, $first['refunded_total_minor']);
        $second = $recorder->record($owner->id, $orderId, 60000, 'balance', 'refund-key-0002');
        self::assertSame(100000, $second['refunded_total_minor']);

        try {
            $recorder->record($owner->id, $orderId, 1, 'over', 'refund-key-0003');
            self::fail('Over-refund must be rejected');
        } catch (DomainException $e) {
            self::assertSame('REFUND_RECORD_EXCEEDS_CONFIRMED_AMOUNT', $e->getMessage());
        }
        $this->assertDatabaseCount('commerce_order_refund_records', 2);
        $this->assertDatabaseHas('operator_action_audits', ['action' => 'order.refund.record']);
    }

    public function test_same_request_key_is_idempotent_and_cannot_be_reused_for_another_amount(): void
    {
        [$owner, $orderId] = $this->fixture();
        $recorder = app(OrderRefundRecorder::class);

        $a = $recorder->record($owner->id, $orderId, 25000, 'goodwill', 'refund-key-idem1');
        $b = $recorder->record($owner->id, $orderId, 25000, 'goodwill', 'refund-key-idem1');
        self::assertSame($a['id'], $b['id']);
        self::assertTrue($b['reused']);
        $this->assertDatabaseCount('commerce_order_refund_records', 1);

        $this->expectExceptionMessage('REFUND_RECORD_KEY_REUSED');
        $recorder->record($owner->id, $orderId, 30000, 'goodwill', 'refund-key-idem1');
    }

    public function test_only_platform_owner_may_record_and_unconfirmed_orders_are_refused(): void
    {
        [$owner, $orderId, $pendingId] = $this->fixture();
        $other = User::factory()->create();
        $recorder = app(OrderRefundRecorder::class);

        try {
            $recorder->record($other->id, $orderId, 100, 'nope', 'refund-key-other1');
            self::fail('Non-owner must be rejected');
        } catch (DomainException $e) {
            self::assertSame('REFUND_RECORD_NOT_AUTHORIZED', $e->getMessage());
        }

        $this->expectExceptionMessage('REFUND_RECORD_ORDER_NOT_CONFIRMED');
        $recorder->record($owner->id, $pendingId, 100, 'unpaid', 'refund-key-pend1');
    }

    public function test_owner_without_passkey_or_verified_email_is_refused(): void
    {
        [$owner, $orderId] = $this->fixture();
        DB::table('passkeys')->where('user_id', $owner->id)->delete();

        $this->expectExceptionMessage('REFUND_RECORD_NOT_AUTHORIZED');
        app(OrderRefundRecorder::class)->record($owner->id, $orderId, 100, 'no passkey', 'refund-key-nopk1');
    }

    public function test_route_records_for_super_admin_only_and_maps_errors(): void
    {
        [$owner, $orderId] = $this->fixture();
        $url = "/operator/orders/{$orderId}/refund-record";
        $body = ['amount_minor' => 30000, 'reason' => 'customer request', 'request_key' => 'route-refund-0001'];

        $this->postJson($url, $body)->assertUnauthorized();

        $regular = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($regular)->withSession(['auth.password_confirmed_at' => time()])
            ->postJson($url, $body)->assertForbidden();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->postJson($url, $body)->assertCreated()
            ->assertJsonPath('refunded_total_minor', 30000);
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->postJson($url, [...$body, 'amount_minor' => 99000, 'request_key' => 'route-refund-0002'])
            ->assertStatus(422)->assertJsonPath('code', 'REFUND_RECORD_EXCEEDS_CONFIRMED_AMOUNT');
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->postJson($url, ['amount_minor' => 'abc'])->assertStatus(422);
    }

    public function test_recording_a_refund_changes_neither_order_status_nor_entitlements(): void
    {
        [$owner, $orderId] = $this->fixture();
        app(OrderRefundRecorder::class)->record($owner->id, $orderId, 100000, 'full', 'refund-key-full1');

        $this->assertDatabaseHas('commerce_orders', ['id' => $orderId, 'status' => 'confirmed']);
        $this->assertDatabaseCount('entitlements', 0);
    }
}
