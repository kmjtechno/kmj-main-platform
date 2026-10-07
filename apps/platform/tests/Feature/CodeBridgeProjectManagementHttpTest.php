<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

final class CodeBridgeProjectManagementHttpTest extends TestCase
{
    use RefreshDatabase;

    public function test_owner_can_queue_project_from_browser_for_existing_device(): void
    {
        [$user, $tenant, $license, $credentialId] = $this->fixture();
        $this->actingAs($user)
            ->post('/services/kmj-codebridge/projects', [
                'tenant_id' => $tenant,
                'device_id' => 'device1',
                'project_id' => 'kmj-main-platform',
                'project_name' => 'KMJ Main Platform',
                'repository' => 'kmjtechno/kmj-main-platform',
                'access_mode' => 'write',
                'gate_preset' => 'platform',
            ])
            ->assertRedirect();

        self::assertDatabaseHas('codebridge_device_project_grants', [
            'credential_id' => $credentialId,
            'tenant_id' => $tenant,
            'device_id' => 'device1',
            'project_id' => 'kmj-main-platform',
            'repository' => 'kmjtechno/kmj-main-platform',
            'gate_preset' => 'platform',
            'status' => 'requested',
        ]);
        self::assertDatabaseHas('codebridge_project_setup_jobs', [
            'tenant_id' => $tenant,
            'device_id' => 'device1',
            'project_id' => 'kmj-main-platform',
            'operation' => 'install',
            'state' => 'queued',
        ]);
        self::assertDatabaseHas('kslp_license_events', [
            'license_id' => $license,
            'action' => 'codebridge_project_requested',
        ]);
    }

    public function test_device_introspection_returns_all_authorized_project_grants(): void
    {
        [, $tenant, , $credentialId, $credential] = $this->fixture();

        foreach (['project1', 'kmj-main-platform'] as $index => $projectId) {
            DB::table('codebridge_device_project_grants')->insert([
                'id' => (string) Str::uuid(),
                'credential_id' => $credentialId,
                'tenant_id' => $tenant,
                'device_id' => 'device1',
                'project_id' => $projectId,
                'project_name' => $index === 0 ? 'CodeBridge' : 'KMJ Main Platform',
                'repository' => $index === 0 ? 'kmjtechno/kmj-codebridge' : 'kmjtechno/kmj-main-platform',
                'permissions' => json_encode(['read', 'write', 'execute']),
                'gate_preset' => 'standard',
                'status' => 'authorized',
                'revoked_at' => null,
                'created_at' => now()->addSeconds($index),
                'updated_at' => now()->addSeconds($index),
            ]);
        }

        config()->set('codebridge.enabled', true);

        $this->withToken($credential)
            ->postJson('/api/codebridge/v1/device-credentials/introspect')
            ->assertOk()
            ->assertJson([
                'active' => true,
                'device_id' => 'device1',
                'tenant_id' => $tenant,
                'projects' => ['project1', 'kmj-main-platform'],
                'permissions' => ['read', 'write', 'execute'],
            ]);
    }

    /** @return array{User,string,string,string,string} */
    private function fixture(): array
    {
        $user = User::factory()->create();
        $tenant = (string) Str::uuid();
        $license = (string) Str::uuid();
        $activation = (string) Str::uuid();
        $credentialId = (string) Str::uuid();
        $credential = rtrim(strtr(base64_encode(random_bytes(48)), '+/', '-_'), '=');
        $now = now();

        DB::table('organizations')->insert([
            'id' => $tenant,
            'name' => 'KMJ Test Org',
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('organization_memberships')->insert([
            'id' => (string) Str::uuid(),
            'organization_id' => $tenant,
            'user_id' => $user->id,
            'role' => 'owner',
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('kslp_licenses')->insert([
            'id' => $license,
            'customer_id' => $tenant,
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

        $product = (string) Str::uuid();
        DB::table('products')->insert([
            'id' => $product,
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
        DB::table('plans')->insert([
            'id' => (string) Str::uuid(),
            'product_id' => $product,
            'code' => 'codebridge.professional',
            'name' => 'CodeBridge Professional',
            'pricing_model' => 'license',
            'status' => 'active',
            'trial_days' => 0,
            'features' => json_encode(['read' => true, 'write' => true, 'execute' => true]),
            'limits' => json_encode(['devices' => 5]),
            'created_at' => $now,
            'updated_at' => $now,
        ]);

        DB::table('kslp_activations')->insert([
            'id' => $activation,
            'license_id' => $license,
            'server_identity' => 'codebridge-device:device1',
            'machine_identity_hash' => str_repeat('a', 64),
            'idempotency_key' => 'project-ui-fixture',
            'activated_at' => $now,
            'created_at' => $now,
            'updated_at' => $now,
        ]);

        DB::table('codebridge_device_credentials')->insert([
            'id' => $credentialId,
            'license_id' => $license,
            'activation_id' => $activation,
            'tenant_id' => $tenant,
            'device_id' => 'device1',
            'server_identity' => 'codebridge-device:device1',
            'token_hash' => hash('sha256', $credential),
            'lease_sequence' => 0,
            'expires_at_epoch' => time() + 3600,
            'revoked_at' => null,
        ]);

        return [$user, $tenant, $license, $credentialId, $credential];
    }
}
