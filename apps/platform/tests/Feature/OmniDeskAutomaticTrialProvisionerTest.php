<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\OmniDesk\OmniDeskAutomaticTrialProvisioner;
use App\Services\Licensing\OmniDeskLicenseContract;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Catalog\Models\Plan;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class OmniDeskAutomaticTrialProvisionerTest extends TestCase
{
    use RefreshDatabase;

    /**
     * @return array{actor:User,organization_id:string,product_id:string}
     */
    private function eligible(): array
    {
        $actor = User::factory()->create(['email_verified_at' => now()]);
        $organization = app(OrganizationCreator::class)->create('Verified trial team', $actor->id);
        $product = Product::query()->create([
            'slug' => OmniDeskLicenseContract::PRODUCT_SLUG,
            'name' => 'KMJ OmniDesk',
            'status' => 'active',
            'lifecycle' => 'public-beta',
            'is_public' => true,
            'purchase_enabled' => false,
            'licensing_enabled' => true,
        ]);
        Plan::query()->create([
            'product_id' => $product->getKey(),
            'code' => OmniDeskAutomaticTrialProvisioner::TRIAL_PLAN,
            'name' => 'OmniDesk trial',
            'pricing_model' => 'trial',
            'billing_interval' => null,
            'currency' => null,
            'amount_minor' => null,
            'status' => 'active',
            'trial_days' => 14,
            'features' => [],
            'limits' => [],
        ]);
        EntitlementPolicy::query()->create([
            'product_id' => $product->getKey(),
            'code' => OmniDeskAutomaticTrialProvisioner::TRIAL_POLICY,
            'capability' => OmniDeskLicenseContract::CAPABILITY,
            'status' => 'active',
        ]);

        return [
            'actor' => $actor,
            'organization_id' => (string) $organization->getKey(),
            'product_id' => (string) $product->getKey(),
        ];
    }

    public function test_verified_owner_automatically_gets_one_time_bounded_trial_without_a_device_lease(): void
    {
        $f = $this->eligible();
        $service = app(OmniDeskAutomaticTrialProvisioner::class);
        $first = $service->provision($f['actor'], $f['organization_id']);
        $second = $service->provision($f['actor'], $f['organization_id']);

        self::assertFalse($first['already_exists']);
        self::assertTrue($second['already_exists']);
        self::assertSame($first['license_id'], $second['license_id']);
        self::assertSame($first['entitlement_id'], $second['entitlement_id']);
        self::assertSame('active', $second['status']);
        $this->assertDatabaseHas('kslp_licenses', [
            'id' => $first['license_id'],
            'customer_id' => $f['organization_id'],
            'product' => OmniDeskLicenseContract::PRODUCT_ID,
            'plan' => 'trial',
            'status' => 'active',
        ]);
        $this->assertDatabaseHas('entitlements', [
            'id' => $first['entitlement_id'],
            'organization_id' => $f['organization_id'],
            'product_id' => $f['product_id'],
            'capability' => OmniDeskLicenseContract::CAPABILITY,
        ]);
        $this->assertDatabaseCount('kslp_licenses', 1);
        $this->assertDatabaseCount('entitlements', 1);
        $this->assertDatabaseCount('kslp_activations', 0);
        $this->assertDatabaseCount('omnidesk_activation_bindings', 0);
        $this->assertDatabaseHas('kslp_license_events', [
            'license_id' => $first['license_id'],
            'action' => 'omnidesk_trial_auto_provisioned',
            'actor_id' => (string) $f['actor']->id,
        ]);
        $expiresAt = DB::table('kslp_licenses')->where('id', $first['license_id'])->value('expires_at');
        self::assertNotNull($expiresAt);
        $entitlementEnds = DB::table('entitlements')
            ->where('id', $first['entitlement_id'])->value('ends_at');
        self::assertNotNull($entitlementEnds);
        // PostgreSQL timestamps may serialize with an explicit UTC offset,
        // while the KSLP legacy timestamp is offset-naive.
        self::assertSame(
            Carbon::parse((string) $expiresAt)->getTimestamp(),
            Carbon::parse((string) $entitlementEnds)->getTimestamp(),
        );
    }

    public function test_revoked_trial_is_never_automatically_reissued_or_extended(): void
    {
        $f = $this->eligible();
        $service = app(OmniDeskAutomaticTrialProvisioner::class);
        $first = $service->provision($f['actor'], $f['organization_id']);
        $expiredAt = now()->subDay();
        DB::table('kslp_licenses')->where('id', $first['license_id'])->update([
            'status' => 'revoked',
            'revoked_at' => now(),
            'expires_at' => $expiredAt,
        ]);
        DB::table('entitlements')->where('id', $first['entitlement_id'])->update([
            'status' => 'revoked',
            'ends_at' => $expiredAt,
        ]);

        $replayed = $service->provision($f['actor'], $f['organization_id']);
        self::assertSame($first['license_id'], $replayed['license_id']);
        self::assertSame('restricted', $replayed['status']);
        self::assertTrue($replayed['already_exists']);
        $this->assertDatabaseCount('kslp_licenses', 1);
        $this->assertDatabaseCount('entitlements', 1);
        $this->assertDatabaseHas('kslp_licenses', [
            'id' => $first['license_id'], 'status' => 'revoked',
        ]);
    }

    public function test_pre_alpha_or_paused_trial_plan_fails_closed_without_issuance(): void
    {
        $f = $this->eligible();
        Product::query()->whereKey($f['product_id'])->update(['lifecycle' => 'pre-alpha']);

        try {
            app(OmniDeskAutomaticTrialProvisioner::class)->provision($f['actor'], $f['organization_id']);
            self::fail('Pre-alpha product must not auto-issue trial rights.');
        } catch (DomainException $e) {
            self::assertSame('OMNIDESK_TRIAL_NOT_ENABLED', $e->getMessage());
        }

        Product::query()->whereKey($f['product_id'])->update(['lifecycle' => 'public-beta']);
        Plan::query()->where('product_id', $f['product_id'])->update(['status' => 'paused']);

        try {
            app(OmniDeskAutomaticTrialProvisioner::class)->provision($f['actor'], $f['organization_id']);
            self::fail('Paused plan must not issue trial rights.');
        } catch (DomainException $e) {
            self::assertSame('OMNIDESK_TRIAL_NOT_ENABLED', $e->getMessage());
        }
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('entitlements', 0);
    }

    public function test_unverified_owner_and_regular_member_cannot_auto_issue_trial(): void
    {
        $f = $this->eligible();
        $service = app(OmniDeskAutomaticTrialProvisioner::class);
        $f['actor']->forceFill(['email_verified_at' => null])->save();

        try {
            $service->provision($f['actor'], $f['organization_id']);
            self::fail('Unverified user must be rejected.');
        } catch (DomainException $e) {
            self::assertSame('OMNIDESK_TRIAL_FORBIDDEN', $e->getMessage());
        }

        $f['actor']->forceFill(['email_verified_at' => now()])->save();
        OrganizationMembership::query()
            ->where('user_id', $f['actor']->id)
            ->where('organization_id', $f['organization_id'])
            ->update(['role' => 'member']);

        try {
            $service->provision($f['actor'], $f['organization_id']);
            self::fail('Read-only member must not mint trial rights.');
        } catch (DomainException $e) {
            self::assertSame('OMNIDESK_TRIAL_FORBIDDEN', $e->getMessage());
        }
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('entitlements', 0);
    }

    public function test_other_tenant_cannot_select_a_foreign_organization_for_trial(): void
    {
        $f = $this->eligible();
        $outsider = User::factory()->create(['email_verified_at' => now()]);
        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_TRIAL_FORBIDDEN');

        app(OmniDeskAutomaticTrialProvisioner::class)->provision($outsider, $f['organization_id']);
    }
}
