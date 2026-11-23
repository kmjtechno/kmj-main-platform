<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\OmniDesk\OmniDeskAutomaticTrialExpiry;
use App\Services\Licensing\OmniDesk\OmniDeskAutomaticTrialProvisioner;
use App\Services\Licensing\OmniDeskLicenseContract;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Catalog\Models\Plan;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class OmniDeskAutomaticTrialExpiryTest extends TestCase
{
    use RefreshDatabase;

    /** @return array{actor:User,organization_id:string} */
    private function eligible(): array
    {
        $actor = User::factory()->create(['email_verified_at' => now()]);
        $org = app(OrganizationCreator::class)->create('Trial expiry lab', $actor->id);
        $product = Product::query()->create([
            'slug' => OmniDeskLicenseContract::PRODUCT_SLUG,
            'name' => 'KMJ OmniDesk',
            'status' => 'active',
            'lifecycle' => 'public-beta',
            'is_public' => true,
            'licensing_enabled' => true,
            'purchase_enabled' => false,
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

        return ['actor' => $actor, 'organization_id' => (string) $org->getKey()];
    }

    /** @return array{license_id:string,entitlement_id:string} */
    private function issuedTrial(): array
    {
        $f = $this->eligible();
        $trial = app(OmniDeskAutomaticTrialProvisioner::class)->provision(
            $f['actor'],
            $f['organization_id'],
        );

        return ['license_id' => $trial['license_id'], 'entitlement_id' => $trial['entitlement_id']];
    }

    /** @param array{license_id:string,entitlement_id:string} $trial */
    private function makeDue(array $trial): void
    {
        $expired = now()->subDay();
        DB::table('kslp_licenses')->where('id', $trial['license_id'])
            ->update(['expires_at' => $expired]);
        DB::table('entitlements')->where('id', $trial['entitlement_id'])
            ->update(['ends_at' => $expired]);
    }

    public function test_due_first_party_trial_expires_atomically_with_both_audit_ledgers(): void
    {
        $trial = $this->issuedTrial();
        $this->makeDue($trial);

        self::assertSame(
            ['expired' => 1, 'blocked' => 0, 'skipped' => 0],
            app(OmniDeskAutomaticTrialExpiry::class)->expireDue(),
        );
        $this->assertDatabaseHas('kslp_licenses', [
            'id' => $trial['license_id'],
            'status' => 'expired',
            'sequence' => 2,
            'revoked_at' => null,
        ]);
        $this->assertDatabaseHas('entitlements', [
            'id' => $trial['entitlement_id'], 'status' => 'expired',
        ]);
        $this->assertDatabaseHas('kslp_license_events', [
            'license_id' => $trial['license_id'],
            'actor_id' => 'kmj-licensing-hub-scheduler',
            'action' => 'omnidesk_trial_auto_expired',
        ]);
        $this->assertDatabaseHas('entitlement_ledger', [
            'entitlement_id' => $trial['entitlement_id'],
            'event_type' => 'entitlement.expired',
        ]);
        $this->assertDatabaseCount('kslp_license_events', 2);
        $this->assertDatabaseCount('entitlement_ledger', 2);
        $this->assertDatabaseCount('kslp_activations', 0);
        $this->assertDatabaseCount('commerce_orders', 0);
    }

    public function test_rerun_is_idempotent_and_cannot_restart_expired_trial(): void
    {
        $trial = $this->issuedTrial();
        $this->makeDue($trial);
        $expiry = app(OmniDeskAutomaticTrialExpiry::class);
        self::assertSame(1, $expiry->expireDue()['expired']);
        self::assertSame(
            ['expired' => 0, 'blocked' => 0, 'skipped' => 0],
            $expiry->expireDue(),
        );
        $this->assertDatabaseCount('kslp_license_events', 2);
        $this->assertDatabaseCount('entitlement_ledger', 2);
        $this->assertDatabaseCount('kslp_licenses', 1);
        $this->assertDatabaseCount('entitlements', 1);
    }

    public function test_future_trial_remains_active_without_audit_side_effects(): void
    {
        $trial = $this->issuedTrial();
        self::assertSame(
            ['expired' => 0, 'blocked' => 0, 'skipped' => 0],
            app(OmniDeskAutomaticTrialExpiry::class)->expireDue(),
        );
        $this->assertDatabaseHas('kslp_licenses', [
            'id' => $trial['license_id'], 'status' => 'active', 'sequence' => 1,
        ]);
        $this->assertDatabaseCount('kslp_license_events', 1);
        $this->assertDatabaseCount('entitlement_ledger', 1);
    }

    public function test_unknown_trial_issuer_fingerprint_is_blocked_without_mutation(): void
    {
        $trial = $this->issuedTrial();
        $this->makeDue($trial);
        DB::table('kslp_licenses')->where('id', $trial['license_id'])
            ->update(['trial_subject_hash' => hash('sha256', 'some-other-issuer')]);

        self::assertSame(
            ['expired' => 0, 'blocked' => 1, 'skipped' => 0],
            app(OmniDeskAutomaticTrialExpiry::class)->expireDue(),
        );
        $this->assertDatabaseHas('kslp_licenses', [
            'id' => $trial['license_id'], 'status' => 'active',
        ]);
        $this->assertDatabaseHas('entitlements', [
            'id' => $trial['entitlement_id'], 'status' => 'active',
        ]);
        $this->assertDatabaseCount('kslp_license_events', 1);
        $this->assertDatabaseCount('entitlement_ledger', 1);
    }

    public function test_mismatched_entitlement_expiry_is_blocked_without_partial_write(): void
    {
        $trial = $this->issuedTrial();
        $this->makeDue($trial);
        DB::table('entitlements')->where('id', $trial['entitlement_id'])
            ->update(['ends_at' => now()->subDays(2)]);

        self::assertSame(1, app(OmniDeskAutomaticTrialExpiry::class)->expireDue()['blocked']);
        $this->assertDatabaseHas('kslp_licenses', [
            'id' => $trial['license_id'], 'status' => 'active',
        ]);
        $this->assertDatabaseHas('entitlements', [
            'id' => $trial['entitlement_id'], 'status' => 'active',
        ]);
        $this->assertDatabaseCount('kslp_license_events', 1);
        $this->assertDatabaseCount('entitlement_ledger', 1);
    }

    public function test_revoked_license_is_not_overwritten_by_automatic_expiry(): void
    {
        $trial = $this->issuedTrial();
        $this->makeDue($trial);
        DB::table('kslp_licenses')->where('id', $trial['license_id'])
            ->update(['status' => 'revoked', 'revoked_at' => now()]);

        self::assertSame(0, app(OmniDeskAutomaticTrialExpiry::class)->expireDue()['expired']);
        $this->assertDatabaseHas('kslp_licenses', [
            'id' => $trial['license_id'], 'status' => 'revoked',
        ]);
        $this->assertDatabaseCount('kslp_license_events', 1);
    }

    public function test_command_requires_explicit_owner_rollout_then_runs_without_paid_or_device_mutation(): void
    {
        $trial = $this->issuedTrial();
        $this->makeDue($trial);

        config()->set('omnidesk-licensing.auto_expire_trials', false);
        self::assertSame(0, Artisan::call('licensing:expire-omnidesk-trials'));
        $this->assertDatabaseHas('kslp_licenses', [
            'id' => $trial['license_id'], 'status' => 'active',
        ]);

        config()->set('omnidesk-licensing.auto_expire_trials', true);
        self::assertSame(2, Artisan::call('licensing:expire-omnidesk-trials', ['--limit' => '0']));
        self::assertSame(0, Artisan::call('licensing:expire-omnidesk-trials', ['--limit' => '50']));
        $this->assertDatabaseHas('kslp_licenses', [
            'id' => $trial['license_id'], 'status' => 'expired',
        ]);
        $this->assertDatabaseCount('commerce_orders', 0);
        $this->assertDatabaseCount('kslp_activations', 0);
    }
}
