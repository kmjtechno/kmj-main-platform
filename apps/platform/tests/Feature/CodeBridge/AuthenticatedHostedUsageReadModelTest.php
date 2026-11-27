<?php

declare(strict_types=1);

namespace Tests\Feature\CodeBridge;

use App\Models\User;
use App\Services\CodeBridge\AuthenticatedHostedUsageReadModel;
use Carbon\CarbonImmutable;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class AuthenticatedHostedUsageReadModelTest extends TestCase
{
    use RefreshDatabase;

    private function clock(): CarbonImmutable
    {
        return CarbonImmutable::parse('2026-11-23T12:00:00Z');
    }

    private function organizationWithCodeBridgeEntitlement(User $user, string $name): string
    {
        $organization = app(OrganizationCreator::class)->create($name, (int) $user->getKey());
        $product = Product::query()->firstOrCreate(
            ['slug' => 'kmj-codebridge'],
            ['name' => 'KMJ CodeBridge', 'status' => 'active'],
        );
        $policy = EntitlementPolicy::query()->firstOrCreate(
            ['product_id' => $product->getKey(), 'code' => 'codebridge.monthly.read'],
            ['capability' => 'codebridge.use', 'status' => 'active'],
        );
        Entitlement::query()->create([
            'organization_id' => $organization->getKey(),
            'product_id' => $product->getKey(),
            'policy_id' => $policy->getKey(),
            'capability' => 'codebridge.use',
            'status' => 'active',
            'idempotency_key' => 'read-model-'.Str::uuid(),
            'starts_at' => $this->clock()->subMonth(),
            'ends_at' => $this->clock()->addMonth(),
        ]);

        return (string) $organization->getKey();
    }

    private function record(string $organizationId, string $subject, int $completed, int $reserved, string $period = '2026-11-01'): void
    {
        DB::table('codebridge_usage_periods')->insert([
            'organization_id' => $organizationId,
            'subject_key' => $subject,
            'period_start_utc' => $period,
            'plan_code' => 'team',
            'monthly_limit' => 300000,
            'completed_calls' => $completed,
            'reserved_calls' => $reserved,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    public function test_verified_member_gets_only_scoped_recorded_counts_without_fake_live_usage(): void
    {
        $member = User::factory()->create(['email_verified_at' => now()]);
        $outsider = User::factory()->create(['email_verified_at' => now()]);
        $own = $this->organizationWithCodeBridgeEntitlement($member, 'Owned CodeBridge org');
        $foreign = $this->organizationWithCodeBridgeEntitlement($outsider, 'Foreign CodeBridge org');
        $this->record($own, 'seat:alice', 2, 1);
        $this->record($own, 'seat:bob', 5, 3);
        $this->record($foreign, 'seat:foreign', 9876, 7);

        $snapshot = app(AuthenticatedHostedUsageReadModel::class)->forUser($member, $this->clock());

        $this->assertSame('source_only_unverified', $snapshot['status']);
        $this->assertSame('2026-11-01', $snapshot['period_start_utc']);
        $this->assertFalse($snapshot['meter_live']);
        $this->assertFalse($snapshot['device_receipts_verified']);
        $this->assertFalse($snapshot['billable']);
        $this->assertNull($snapshot['active_plan']);
        $this->assertNull($snapshot['remaining_calls']);
        $this->assertCount(1, $snapshot['organizations']);
        $this->assertSame($own, $snapshot['organizations'][0]['organization_id']);
        $this->assertSame(7, $snapshot['organizations'][0]['recorded_completed_calls']);
        $this->assertSame(4, $snapshot['organizations'][0]['recorded_reserved_calls']);
        $this->assertTrue($snapshot['organizations'][0]['recorded_only_not_verified']);
        $this->assertStringNotContainsString($foreign, json_encode($snapshot, JSON_THROW_ON_ERROR));
        // A legitimate random organization UUID may itself contain "9876".
        // Test numeric foreign usage fields, not an arbitrary JSON substring.
        $this->assertNotContains(9876, array_column($snapshot['organizations'], 'recorded_completed_calls'));
        $this->assertNotContains(7, array_column($snapshot['organizations'], 'recorded_reserved_calls'));
        $this->assertDatabaseCount('codebridge_usage_periods', 3);
    }

    public function test_unverified_customer_and_non_member_cannot_read_ledger(): void
    {
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $unverified = User::factory()->create(['email_verified_at' => null]);
        $stranger = User::factory()->create(['email_verified_at' => now()]);
        $org = $this->organizationWithCodeBridgeEntitlement($owner, 'Private org');
        $this->record($org, 'account', 17, 1);
        $readModel = app(AuthenticatedHostedUsageReadModel::class);

        $this->assertSame([], $readModel->forUser($unverified, $this->clock())['organizations']);
        $this->assertSame([], $readModel->forUser($stranger, $this->clock())['organizations']);
    }

    public function test_missing_monthly_row_is_unknown_and_old_month_is_not_reused(): void
    {
        $member = User::factory()->create(['email_verified_at' => now()]);
        $org = $this->organizationWithCodeBridgeEntitlement($member, 'No current usage');
        $this->record($org, 'account', 123, 3, '2026-10-01');
        $snapshot = app(AuthenticatedHostedUsageReadModel::class)->forUser($member, $this->clock());

        $this->assertCount(1, $snapshot['organizations']);
        $this->assertNull($snapshot['organizations'][0]['recorded_completed_calls']);
        $this->assertNull($snapshot['organizations'][0]['recorded_reserved_calls']);
        $this->assertFalse($snapshot['meter_live']);
    }

    public function test_expired_entitlement_denies_read_even_with_current_month_row(): void
    {
        $member = User::factory()->create(['email_verified_at' => now()]);
        $org = $this->organizationWithCodeBridgeEntitlement($member, 'Former subscriber');
        $this->record($org, 'account', 44, 2);
        DB::table('entitlements')->where('organization_id', $org)
            ->update(['ends_at' => $this->clock()->subDay()->toDateTimeString()]);

        $snapshot = app(AuthenticatedHostedUsageReadModel::class)->forUser($member, $this->clock());
        $this->assertSame([], $snapshot['organizations']);
    }
}
