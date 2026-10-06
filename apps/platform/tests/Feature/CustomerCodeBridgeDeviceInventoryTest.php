<?php

namespace Tests\Feature;

use App\Models\User;
use App\Services\AuthorityBootstrapper;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use KMJ\MainPlatform\Catalog\Services\ProductCatalog;
use KMJ\MainPlatform\Entitlements\Services\EntitlementIssuer;
use KMJ\MainPlatform\Entitlements\Services\EntitlementPolicyRegistry;
use Tests\TestCase;

final class CustomerCodeBridgeDeviceInventoryTest extends TestCase
{
    use RefreshDatabase;

    public function test_customer_sees_only_own_enrolled_devices_and_last_approved_project(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);
        $stranger = User::factory()->create(['email_verified_at' => now()]);
        $mine = app(AuthorityBootstrapper::class)->createOrganizationWithSandboxAccess('My Business', $user->id);
        $theirs = app(AuthorityBootstrapper::class)->createOrganizationWithSandboxAccess('Another Business', $stranger->id);

        $product = app(ProductCatalog::class)->ensureSandboxProduct('kmj-codebridge', 'KMJ CodeBridge');
        $policy = app(EntitlementPolicyRegistry::class)->ensure(
            $product->getKey(),
            'codebridge.test.customer-access',
            'codebridge.service.access',
        );

        foreach ([$mine, $theirs] as $organization) {
            app(EntitlementIssuer::class)->issue(
                $organization->getKey(),
                $policy,
                'customer-codebridge:'.$organization->getKey(),
            );
        }

        $this->enrollFixture($mine->getKey(), 'mine-vps', 'kmj-main-platform');
        $this->enrollFixture($theirs->getKey(), 'hidden-vps', 'confidential-project');

        $this->actingAs($user)
            ->get('/services/kmj-codebridge')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('services/codebridge')
                ->where('organization.name', 'My Business')
                ->has('service.enrolled_devices', 1)
                ->where('service.enrolled_devices.0.device_id', 'mine-vps')
                ->where('service.enrolled_devices.0.last_paired_project', 'kmj-main-platform')
                ->where('service.managed_devices', 1)
                ->etc());

        $response = $this->actingAs($user)->get('/services/kmj-codebridge');
        self::assertStringNotContainsString('hidden-vps', $response->getContent());
        self::assertStringNotContainsString('confidential-project', $response->getContent());
        self::assertStringNotContainsString('test-secret-credential', $response->getContent());
    }

    private function enrollFixture(string $tenantId, string $deviceId, string $projectId): void
    {
        $license = (string) Str::uuid();
        $activation = (string) Str::uuid();
        $now = now();

        DB::table('kslp_licenses')->insert([
            'id' => $license,
            'customer_id' => $tenantId,
            'product' => 'KMJ_CODEBRIDGE',
            'plan' => 'professional',
            'status' => 'active',
            'sequence' => 1,
            'starts_at' => $now->copy()->subMinute(),
            'expires_at' => $now->copy()->addYear(),
            'grace_until' => $now->copy()->addYear()->addDays(2),
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('kslp_activations')->insert([
            'id' => $activation,
            'license_id' => $license,
            'server_identity' => 'ed25519:device-test',
            'machine_identity_hash' => hash('sha256', $deviceId),
            'idempotency_key' => 'device-inventory:'.$deviceId,
            'activated_at' => $now,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('codebridge_device_credentials')->insert([
            'id' => (string) Str::uuid(),
            'license_id' => $license,
            'activation_id' => $activation,
            'tenant_id' => $tenantId,
            'device_id' => $deviceId,
            'server_identity' => 'ed25519:device-test',
            'token_hash' => hash('sha256', 'test-secret-credential-'.$deviceId),
            'lease_sequence' => 0,
            'expires_at_epoch' => time() + 3600,
        ]);
        DB::table('codebridge_device_pairings')->insert([
            'id' => (string) Str::uuid(),
            'device_code_hash' => hash('sha256', 'device-code-'.$deviceId),
            'user_code_hash' => hash('sha256', 'user-code-'.$deviceId),
            'device_id' => $deviceId,
            'device_name' => $deviceId,
            'platform' => 'linux',
            'arch' => 'x64',
            'project_id' => $projectId,
            'project_name' => $projectId,
            'requested_permissions' => json_encode(['read']),
            'code_challenge' => str_repeat('a', 43),
            'status' => 'consumed',
            'tenant_id' => $tenantId,
            'license_id' => $license,
            'activation_id' => $activation,
            'expires_at' => $now->copy()->addMinutes(15),
            'approved_at' => $now,
            'consumed_at' => $now,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
    }
}
