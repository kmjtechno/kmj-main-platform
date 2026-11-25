<?php

declare(strict_types=1);

namespace Tests\Feature\CodeBridge;

use App\Models\User;
use App\Services\CodeBridge\HostedTeamSeatAllocator;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use KMJ\MainPlatform\Entitlements\Services\EntitlementIssuer;
use KMJ\MainPlatform\Entitlements\Services\EntitlementPolicyRegistry;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class HostedTeamSeatAllocatorTest extends TestCase
{
    use RefreshDatabase;

    public function test_missing_commercial_capacity_cannot_allocate_a_seat(): void
    {
        $this->assertDenied('CODEBRIDGE_SEAT_CAPACITY_REQUIRED', (string) Str::uuid(), (string) Str::uuid());
        $this->assertDatabaseCount('codebridge_hosted_team_capacity', 0);
        $this->assertDatabaseCount('codebridge_hosted_seat_assignments', 0);
        $this->assertDatabaseCount('codebridge_usage_executions', 0);
    }

    public function test_synthetic_settlement_allocation_is_idempotent_and_bounded(): void
    {
        $fixture = $this->fixture();
        $allocator = app(HostedTeamSeatAllocator::class);
        $members = $fixture['members'];
        $capacity = $fixture['capacity'];

        $this->assertDenied('CODEBRIDGE_SEAT_LIVE_SETTLEMENT_REQUIRED', $capacity, $members[0]);
        $this->assertDatabaseCount('codebridge_hosted_seat_assignments', 0);

        // Synthetic live-shaped records in the disposable test DB ONLY.
        DB::table('commerce_provider_orders')->where('commercial_order_id', $fixture['order'])->update(['environment' => 'live']);
        $first = $allocator->allocateTrusted($capacity, $members[0]);
        self::assertSame($first, $allocator->allocateTrusted($capacity, $members[0]));
        $allocator->allocateTrusted($capacity, $members[1]);
        $allocator->allocateTrusted($capacity, $members[2]);
        $this->assertDenied('CODEBRIDGE_SEAT_CAPACITY_EXHAUSTED', $capacity, $members[3]);
        $this->assertDatabaseCount('codebridge_hosted_seat_assignments', 3);

        DB::table('codebridge_hosted_seat_assignments')->where('id', $first)->update(['ends_at' => now()->subMinute()]);
        $this->assertDenied('CODEBRIDGE_SEAT_ASSIGNMENT_CONFLICT', $capacity, $members[0]);
        $this->assertDenied('CODEBRIDGE_SEAT_CAPACITY_EXHAUSTED', $capacity, $members[3]);

        DB::table('entitlements')->where('id', $fixture['entitlement'])->update(['status' => 'revoked']);
        $this->assertDenied('CODEBRIDGE_SEAT_FULFILLMENT_REQUIRED', $capacity, $members[1]);
        $this->assertDatabaseCount('codebridge_hosted_seat_assignments', 3);
        $this->assertDatabaseCount('codebridge_usage_executions', 0);
    }

    private function assertDenied(string $reason, string $capacity, string $membership): void
    {
        try {
            app(HostedTeamSeatAllocator::class)->allocateTrusted($capacity, $membership);
            self::fail('Allocation should be denied.');
        } catch (DomainException $exception) {
            self::assertSame($reason, $exception->getMessage());
        }
    }

    /** @return array{capacity: string, order: string, entitlement: string, members: list<string>} */
    private function fixture(): array
    {
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $org = (string) app(OrganizationCreator::class)->create('Capacity test', (int) $owner->getKey())->getKey();
        $product = Product::query()->firstOrCreate(
            ['slug' => 'kmj-codebridge'],
            ['name' => 'KMJ CodeBridge', 'status' => 'active'],
        );
        $product->forceFill(['status' => 'active'])->save();
        $orders = app(CommercialOrderService::class);
        $order = (string) $orders->request($org, (string) $product->getKey(), (int) $owner->getKey(), 'capacity-test-order')->getKey();
        $orders->confirm($order, (int) $owner->getKey(), 'INR', 209700, 'razorpay:pay_capacity_test');
        $policy = app(EntitlementPolicyRegistry::class)->ensure((string) $product->getKey(), 'capacity-test', 'product.access');
        $entitlement = (string) app(EntitlementIssuer::class)->issue($org, $policy, 'commercial-order:'.$order)->getKey();
        $license = (string) Str::uuid();
        $capacity = (string) Str::uuid();
        DB::table('kslp_licenses')->insert([
            'id' => $license, 'customer_id' => $org, 'product' => 'KMJ_CODEBRIDGE', 'plan' => 'team',
            'status' => 'active', 'sequence' => 1, 'starts_at' => now()->subDay(), 'expires_at' => now()->addDay(),
            'created_at' => now(), 'updated_at' => now(),
        ]);
        DB::table('codebridge_hosted_team_capacity')->insert([
            'id' => $capacity, 'commercial_order_id' => $order, 'entitlement_id' => $entitlement, 'license_id' => $license,
            'offer_version' => 'synthetic-test-only', 'seat_quantity' => 3, 'total_minor' => 209700, 'currency' => 'INR',
            'starts_at' => now()->subHour(), 'ends_at' => now()->addHour(), 'created_at' => now(), 'updated_at' => now(),
        ]);
        DB::table('commerce_provider_orders')->insert([
            'commercial_order_id' => $order, 'provider' => 'razorpay', 'provider_order_id' => 'order_capacity_test',
            'amount_minor' => 209700, 'currency' => 'INR', 'environment' => 'sandbox', 'created_at' => now(), 'updated_at' => now(),
        ]);
        DB::table('payment_webhook_events')->insert([
            'provider' => 'razorpay', 'event_id' => 'event_capacity_test', 'event_type' => 'payment.captured',
            'provider_order_id' => 'order_capacity_test', 'provider_payment_id' => 'pay_capacity_test',
            'payload_sha256' => str_repeat('a', 64), 'processing_status' => 'reconciled', 'processing_note' => 'CONFIRMED',
            'received_at' => now(), 'created_at' => now(), 'updated_at' => now(),
        ]);
        $members = [];
        for ($i = 0; $i < 4; $i++) {
            $member = User::factory()->create(['email_verified_at' => now()]);
            $id = (string) Str::uuid();
            DB::table('organization_memberships')->insert([
                'id' => $id, 'organization_id' => $org, 'user_id' => $member->getKey(),
                'role' => 'member', 'created_at' => now(), 'updated_at' => now(),
            ]);
            $members[] = $id;
        }

        return ['capacity' => $capacity, 'order' => $order, 'entitlement' => $entitlement, 'members' => $members];
    }
}
