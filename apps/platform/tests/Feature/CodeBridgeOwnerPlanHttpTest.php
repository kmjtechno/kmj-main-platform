<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

final class CodeBridgeOwnerPlanHttpTest extends TestCase
{
    use RefreshDatabase;

    public function test_guest_and_non_owner_cannot_activate_an_owner_plan(): void
    {
        [$license, $tenant] = $this->professionalLicense();
        $body = $this->payload($license, $tenant);

        $this->postJson('/operator/codebridge/owner-plan/activate', $body)->assertUnauthorized();

        $user = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($user)->withSession(['auth.password_confirmed_at' => time()])
            ->postJson('/operator/codebridge/owner-plan/activate', $body)->assertForbidden();

        self::assertSame('professional', DB::table('kslp_licenses')->where('id', $license)->value('plan'));
    }

    public function test_owner_activates_existing_license_and_preserves_activation_with_audit(): void
    {
        [$license, $tenant] = $this->professionalLicense();
        $activationCount = DB::table('kslp_activations')->where('license_id', $license)->count();
        $body = $this->payload($license, $tenant);

        $response = $this->actingAs($this->platformOwner())->withSession(['auth.password_confirmed_at' => time()])
            ->postJson('/operator/codebridge/owner-plan/activate', $body)
            ->assertOk()->assertHeader('Cache-Control', 'no-store, private')
            ->assertJsonPath('plan', 'owner_admin')
            ->assertJsonPath('devices', 2147483647)
            ->assertJsonPath('concurrent_jobs', 16)
            ->assertJsonPath('changed', true);

        self::assertSame($license, $response->json('license_id'));
        self::assertSame('owner_admin', DB::table('kslp_licenses')->where('id', $license)->value('plan'));
        self::assertSame(2, (int) DB::table('kslp_licenses')->where('id', $license)->value('sequence'));
        self::assertSame($activationCount, DB::table('kslp_activations')->where('license_id', $license)->count());
        self::assertSame(1, DB::table('kslp_license_events')->where('license_id', $license)
            ->where('action', 'codebridge_owner_plan_activated')->count());

        $policy = DB::table('plans')->where('code', 'codebridge.owner_admin')->first();
        self::assertNotNull($policy);
        self::assertSame(['read' => true, 'write' => true, 'execute' => true], json_decode($policy->features, true));
        self::assertSame(['devices' => 2147483647, 'concurrent_jobs' => 16], json_decode($policy->limits, true));

        $this->postJson('/operator/codebridge/owner-plan/activate', $body)->assertOk()
            ->assertJsonPath('changed', false);
        self::assertSame(2, (int) DB::table('kslp_licenses')->where('id', $license)->value('sequence'));
        self::assertSame(1, DB::table('kslp_license_events')->where('license_id', $license)
            ->where('action', 'codebridge_owner_plan_activated')->count());
    }

    public function test_cross_tenant_and_wrong_product_cannot_be_upgraded(): void
    {
        [$license, $tenant] = $this->professionalLicense();
        $this->actingAs($this->platformOwner())->withSession(['auth.password_confirmed_at' => time()])
            ->postJson('/operator/codebridge/owner-plan/activate', $this->payload($license, 'another-tenant'))
            ->assertStatus(409);

        DB::table('kslp_licenses')->where('id', $license)->update(['product' => 'KMJ_CLOUDOS']);
        $this->postJson('/operator/codebridge/owner-plan/activate', $this->payload($license, $tenant))
            ->assertStatus(409);
        self::assertSame('professional', DB::table('kslp_licenses')->where('id', $license)->value('plan'));
        self::assertSame(0, DB::table('plans')->where('code', 'codebridge.owner_admin')->count());
    }

    public function test_existing_conflicting_policy_fails_closed(): void
    {
        [$license, $tenant, $product] = $this->professionalLicense();
        $now = now();
        DB::table('plans')->insert([
            'id' => (string) Str::uuid(),
            'product_id' => $product,
            'code' => 'codebridge.owner_admin',
            'name' => 'Conflicting plan',
            'pricing_model' => 'license',
            'status' => 'active',
            'trial_days' => 0,
            'features' => json_encode(['read' => true]),
            'limits' => json_encode(['devices' => 1, 'concurrent_jobs' => 1]),
            'created_at' => $now,
            'updated_at' => $now,
        ]);

        $this->actingAs($this->platformOwner())->withSession(['auth.password_confirmed_at' => time()])
            ->postJson('/operator/codebridge/owner-plan/activate', $this->payload($license, $tenant))
            ->assertStatus(409)->assertJsonPath('error', 'CODEBRIDGE_OWNER_POLICY_CONFLICT');
        self::assertSame('professional', DB::table('kslp_licenses')->where('id', $license)->value('plan'));
        self::assertSame(0, DB::table('kslp_license_events')->where('license_id', $license)->count());
    }

    /** @return array{string,string,string} */
    private function professionalLicense(): array
    {
        $now = now();
        $tenant = 'owner-tenant';
        $product = (string) Str::uuid();
        $license = (string) Str::uuid();
        DB::table('products')->insert([
            'id' => $product, 'slug' => 'codebridge', 'name' => 'CodeBridge',
            'status' => 'active', 'lifecycle' => 'available', 'is_public' => false,
            'sort_order' => 100, 'purchase_enabled' => false, 'licensing_enabled' => true,
            'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('kslp_licenses')->insert([
            'id' => $license, 'customer_id' => $tenant, 'product' => 'KMJ_CODEBRIDGE',
            'plan' => 'professional', 'status' => 'active', 'sequence' => 1,
            'starts_at' => $now->copy()->subDay(), 'expires_at' => $now->copy()->addYear(),
            'grace_until' => $now->copy()->addYear()->addDays(2),
            'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('kslp_activations')->insert([
            'id' => (string) Str::uuid(), 'license_id' => $license,
            'server_identity' => 'ed25519:owner-test',
            'machine_identity_hash' => str_repeat('a', 64),
            'idempotency_key' => 'owner-'.Str::uuid(),
            'activated_at' => $now, 'created_at' => $now, 'updated_at' => $now,
        ]);

        return [$license, $tenant, $product];
    }

    /** @return array<string,string> */
    private function payload(string $license, string $tenant): array
    {
        return [
            'license_id' => $license,
            'tenant_id' => $tenant,
            'reason' => 'Owner approved secure CodeBridge plan activation',
        ];
    }

    private function platformOwner(): User
    {
        $user = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        DB::table('passkeys')->insert([
            'user_id' => $user->id,
            'name' => 'Owner passkey',
            'credential_id' => 'codebridge-owner-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $user;
    }
}
