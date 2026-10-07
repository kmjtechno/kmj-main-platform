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

    private function fixture(string $tenant = 'owner-tenant', string $product = 'KMJ_CODEBRIDGE'): string
    {
        $now = now();
        $id = (string) Str::uuid();
        DB::table('kslp_licenses')->insert([
            'id' => $id,
            'customer_id' => $tenant,
            'product' => $product,
            'plan' => 'professional',
            'status' => 'active',
            'sequence' => 5,
            'starts_at' => $now->copy()->subDay(),
            'expires_at' => $now->copy()->addYear(),
            'grace_until' => $now->copy()->addYear()->addDays(2),
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        $productId = (string) Str::uuid();
        if (! DB::table('products')->where('slug', 'codebridge')->exists()) {
            DB::table('products')->insert([
                'id' => $productId,
                'slug' => 'codebridge',
                'name' => 'CodeBridge',
                'status' => 'active',
                'lifecycle' => 'available',
                'is_public' => false,
                'sort_order' => 100,
                'purchase_enabled' => false,
                'licensing_enabled' => true,
                'created_at' => $now,
                'updated_at' => $now,
            ]);
        }
        return $id;
    }

    private function owner(bool $passkey = true): User
    {
        $user = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        if ($passkey) {
            DB::table('passkeys')->insert([
                'user_id' => $user->id,
                'name' => 'Owner test passkey',
                'credential_id' => 'owner-plan-'.Str::uuid(),
                'credential' => '{}',
                'created_at' => now(),
                'updated_at' => now(),
            ]);
        }
        return $user;
    }

    private function payload(string $tenant = 'owner-tenant'): array
    {
        return [
            'tenant_id' => $tenant,
            'reason' => 'Owner approved CodeBridge development plan',
        ];
    }

    public function test_guest_regular_user_and_owner_without_passkey_cannot_upgrade(): void
    {
        $id = $this->fixture();
        $url = '/operator/codebridge/licenses/'.$id.'/owner-admin';
        $this->postJson($url, $this->payload())->assertUnauthorized();

        $user = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($user)->withSession(['auth.password_confirmed_at' => time()])
            ->postJson($url, $this->payload())->assertForbidden();

        $this->actingAs($this->owner(false))->withSession(['auth.password_confirmed_at' => time()])
            ->postJson($url, $this->payload())->assertForbidden();

        self::assertSame('professional', DB::table('kslp_licenses')->where('id', $id)->value('plan'));
        self::assertSame(0, DB::table('kslp_license_events')->count());
    }

    public function test_owner_upgrade_is_audited_idempotent_and_keeps_license_identity(): void
    {
        $id = $this->fixture();
        $owner = $this->owner();
        $url = '/operator/codebridge/licenses/'.$id.'/owner-admin';
        $session = ['auth.password_confirmed_at' => time()];
        $before = DB::table('kslp_licenses')->where('id', $id)->first();

        $this->actingAs($owner)->withSession($session)->postJson($url, $this->payload())
            ->assertOk()->assertHeader('Cache-Control', 'no-store, private')
            ->assertJson(['license_id' => $id, 'tenant_id' => 'owner-tenant', 'plan' => 'admin', 'sequence' => 6, 'changed' => true]);

        $after = DB::table('kslp_licenses')->where('id', $id)->first();
        self::assertSame('admin', $after->plan);
        self::assertSame($before->expires_at, $after->expires_at);
        self::assertSame($before->customer_id, $after->customer_id);
        self::assertSame(1, DB::table('kslp_license_events')->where('license_id', $id)->where('action', 'codebridge_owner_admin_upgraded')->count());

        $policy = DB::table('plans')->where('code', 'codebridge.admin')->first();
        self::assertNotNull($policy);
        self::assertSame(16, json_decode($policy->limits, true)['concurrent_jobs']);
        self::assertSame(2147483647, json_decode($policy->limits, true)['devices']);
        self::assertSame(['read' => true, 'write' => true, 'execute' => true], json_decode($policy->features, true));

        $this->actingAs($owner)->withSession($session)->postJson($url, $this->payload())
            ->assertOk()->assertJson(['changed' => false, 'sequence' => 6]);
        self::assertSame(1, DB::table('kslp_license_events')->where('license_id', $id)->count());
    }

    public function test_wrong_tenant_wrong_product_and_invalid_reason_fail_closed(): void
    {
        $id = $this->fixture();
        $other = $this->fixture('cloud-tenant', 'KMJ_CLOUDOS');
        $owner = $this->owner();
        $session = ['auth.password_confirmed_at' => time()];

        $this->actingAs($owner)->withSession($session)
            ->postJson('/operator/codebridge/licenses/'.$id.'/owner-admin', $this->payload('another-tenant'))
            ->assertStatus(409);
        $this->actingAs($owner)->withSession($session)
            ->postJson('/operator/codebridge/licenses/'.$other.'/owner-admin', $this->payload('cloud-tenant'))
            ->assertStatus(409);
        $this->actingAs($owner)->withSession($session)
            ->postJson('/operator/codebridge/licenses/'.$id.'/owner-admin', ['tenant_id' => 'owner-tenant', 'reason' => 'short'])
            ->assertUnprocessable();
        self::assertSame(0, DB::table('kslp_license_events')->count());
        self::assertSame('professional', DB::table('kslp_licenses')->where('id', $id)->value('plan'));
    }

    public function test_admin_upgrade_does_not_change_existing_credential_or_activation(): void
    {
        $id = $this->fixture();
        $now = now();
        $activationId = (string) Str::uuid();
        DB::table('kslp_activations')->insert([
            'id' => $activationId,
            'license_id' => $id,
            'server_identity' => 'ed25519:owner-test',
            'machine_identity_hash' => str_repeat('a', 64),
            'idempotency_key' => 'owner-'.Str::uuid(),
            'activated_at' => $now,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        $owner = $this->owner();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->postJson('/operator/codebridge/licenses/'.$id.'/owner-admin', $this->payload())
            ->assertOk();
        self::assertSame(1, DB::table('kslp_activations')->where('license_id', $id)->count());
        self::assertSame($activationId, DB::table('kslp_activations')->where('license_id', $id)->value('id'));
    }
}
