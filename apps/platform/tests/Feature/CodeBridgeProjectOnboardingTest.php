<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

final class CodeBridgeProjectOnboardingTest extends TestCase
{
    use RefreshDatabase;

    private const URL = '/services/kmj-codebridge/projects';

    public function test_guest_and_non_member_cannot_request_project_grants(): void
    {
        $this->post(self::URL, ['tenant_id' => (string) Str::uuid(), 'project_id' => 'kmj-omnidesk'])
            ->assertRedirect('/login');

        $user = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($user)->withSession(['auth.password_confirmed_at' => time()])
            ->post(self::URL, ['tenant_id' => (string) Str::uuid(), 'project_id' => 'kmj-omnidesk'])
            ->assertForbidden();

        $this->assertDatabaseCount('codebridge_project_onboarding_requests', 0);
    }

    public function test_allowed_owner_request_is_tenant_scoped_idempotent_and_never_activates_agent(): void
    {
        [$owner, $tenant] = $this->fixture();
        $payload = ['tenant_id' => $tenant, 'project_id' => 'kmj-omnidesk'];

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post(self::URL, $payload)->assertRedirect('/services/kmj-codebridge');
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post(self::URL, $payload)->assertRedirect('/services/kmj-codebridge');

        $this->assertDatabaseCount('codebridge_project_onboarding_requests', 1);
        $this->assertDatabaseHas('codebridge_project_onboarding_requests', [
            'tenant_id' => $tenant,
            'project_id' => 'kmj-omnidesk',
            'repository' => 'kmjtechno/kmj-omnidesk',
            'host' => 'lenovo-p720',
            'status' => 'awaiting_agent_pairing',
            'requested_by' => $owner->id,
        ]);
        $this->assertDatabaseCount('codebridge_device_credentials', 0);
        $this->assertDatabaseCount('codebridge_device_pairings', 0);
    }

    public function test_unknown_repo_and_unconfirmed_password_are_rejected(): void
    {
        [$owner, $tenant] = $this->fixture();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post(self::URL, ['tenant_id' => $tenant, 'project_id' => '../other'])
            ->assertSessionHasErrors('project_id');

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time() - 15000])
            ->post(self::URL, ['tenant_id' => $tenant, 'project_id' => 'kmj-omnidesk'])
            ->assertStatus(423);

        $this->assertDatabaseCount('codebridge_project_onboarding_requests', 0);
    }

    public function test_lapsed_licence_refuses_onboarding_even_with_an_entitlement(): void
    {
        [$owner, $tenant] = $this->fixture();
        DB::table('kslp_licenses')->where('customer_id', $tenant)
            ->update(['expires_at' => now()->subMinute()]);

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post(self::URL, ['tenant_id' => $tenant, 'project_id' => 'kmj-omnidesk'])
            ->assertForbidden();

        $this->assertDatabaseCount('codebridge_project_onboarding_requests', 0);
    }

    public function test_redeemed_omnidesk_pairing_marks_request_registered_but_not_online(): void
    {
        config()->set('codebridge.enabled', true);
        config()->set('services.codebridge_gateway.url', 'https://gateway.example');
        [$owner, $tenant] = $this->fixture();

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post(self::URL, ['tenant_id' => $tenant, 'project_id' => 'kmj-omnidesk'])
            ->assertRedirect('/services/kmj-codebridge');

        $verifier = rtrim(strtr(base64_encode(random_bytes(32)), '+/', '-_'), '=');
        $challenge = rtrim(strtr(base64_encode(hash('sha256', $verifier, true)), '+/', '-_'), '=');
        $created = $this->postJson('/api/codebridge/v1/device-enrollments', [
            'product' => 'KMJ_CODEBRIDGE',
            'device' => ['id' => 'kmj-omnidesk-p720-test', 'name' => 'P720 OmniDesk',
                'platform' => 'win32', 'arch' => 'x64'],
            'project' => ['id' => 'kmj-omnidesk', 'name' => 'kmj-omnidesk'],
            'requested_permissions' => ['read', 'write', 'execute'],
            'code_challenge' => $challenge,
            'code_challenge_method' => 'S256',
        ])->assertCreated()->json();

        $this->actingAs($owner)
            ->post('/codebridge/pair', ['code' => $created['user_code'], 'tenant_id' => $tenant])
            ->assertRedirect();
        // Owner approval provisions a credential, but does not prove the
        // installed agent redeemed it or connected to the gateway.
        $this->assertDatabaseHas('codebridge_project_onboarding_requests', [
            'tenant_id' => $tenant, 'project_id' => 'kmj-omnidesk',
            'status' => 'awaiting_agent_pairing',
        ]);

        $this->postJson('/api/codebridge/v1/device-enrollments/token', [
            'product' => 'KMJ_CODEBRIDGE',
            'device_code' => $created['device_code'],
            'code_verifier' => $verifier,
            'device_id' => 'kmj-omnidesk-p720-test',
        ])->assertOk();

        $this->assertDatabaseHas('codebridge_project_onboarding_requests', [
            'tenant_id' => $tenant, 'project_id' => 'kmj-omnidesk',
            'status' => 'registered_not_live_verified',
        ]);
        $this->assertDatabaseHas('codebridge_device_pairings', [
            'tenant_id' => $tenant, 'project_id' => 'kmj-omnidesk',
            'status' => 'consumed',
        ]);
    }

    /** @return array{0: User, 1: string} */
    private function fixture(): array
    {
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $tenant = (string) Str::uuid();
        $product = (string) Str::uuid();
        $policy = (string) Str::uuid();
        $now = now();

        DB::table('organizations')->insert([
            'id' => $tenant, 'name' => 'OmniDesk Test Organization',
            'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('organization_memberships')->insert([
            'id' => (string) Str::uuid(), 'organization_id' => $tenant,
            'user_id' => $owner->id, 'role' => 'owner',
            'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('products')->insert([
            'id' => $product, 'slug' => 'kmj-codebridge', 'name' => 'KMJ CodeBridge',
            'status' => 'active', 'lifecycle' => 'available',
            'is_public' => false, 'sort_order' => 1,
            'purchase_enabled' => false, 'licensing_enabled' => true,
            'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('plans')->insert([
            'id' => (string) Str::uuid(), 'product_id' => $product,
            'code' => 'codebridge.professional', 'name' => 'CodeBridge Professional',
            'pricing_model' => 'license', 'status' => 'active', 'trial_days' => 0,
            'features' => json_encode(['read' => true, 'write' => true, 'execute' => true]),
            'limits' => json_encode(['devices' => 5]),
            'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('entitlement_policies')->insert([
            'id' => $policy, 'product_id' => $product,
            'code' => 'test.codebridge.'.$tenant, 'capability' => 'codebridge',
            'status' => 'active', 'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('entitlements')->insert([
            'id' => (string) Str::uuid(), 'organization_id' => $tenant,
            'product_id' => $product, 'policy_id' => $policy,
            'capability' => 'codebridge', 'status' => 'active',
            'idempotency_key' => 'cb-project-'.Str::uuid(),
            'starts_at' => $now, 'ends_at' => null,
            'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('kslp_licenses')->insert([
            'id' => (string) Str::uuid(), 'customer_id' => $tenant,
            'product' => 'KMJ_CODEBRIDGE', 'plan' => 'professional',
            'status' => 'active', 'sequence' => 1,
            'starts_at' => $now->copy()->subMinute(),
            'expires_at' => $now->copy()->addYear(),
            'grace_until' => $now->copy()->addYear()->addDays(2),
            'created_at' => $now, 'updated_at' => $now,
        ]);

        return [$owner, $tenant];
    }
}
