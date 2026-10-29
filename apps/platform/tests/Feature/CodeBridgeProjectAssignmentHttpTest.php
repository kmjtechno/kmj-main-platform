<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\CodeBridge\CodeBridgeCustomerDeviceDirectory;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

final class CodeBridgeProjectAssignmentHttpTest extends TestCase
{
    use RefreshDatabase;

    public function test_manager_can_request_project_without_creating_agent_grant(): void
    {
        [$owner, $tenant, $device] = $this->fixture('desktop-one');
        $url = $this->url($tenant, $device);
        $payload = $this->payload();

        $this->actingAs($owner)->post($url, $payload)->assertRedirect();
        $this->assertDatabaseHas('codebridge_project_assignments', [
            'tenant_id' => $tenant, 'device_id' => $device,
            'project_id' => 'kmj-calibration-studio',
            'status' => 'pending_local_setup',
        ]);
        $directory = app(CodeBridgeCustomerDeviceDirectory::class);
        $devices = $directory->forTenant($tenant, time());
        self::assertCount(1, $devices);
        self::assertSame([['id' => 'existing-project', 'name' => 'Existing']], $devices[0]['projects']);
        self::assertSame('pending_local_setup', $devices[0]['pending_projects'][0]['status']);
        self::assertSame('kmj-calibration-studio', $devices[0]['pending_projects'][0]['id']);
        self::assertSame('not_verified', $devices[0]['connection_status']);

        // A repeated browser submit must not generate a second assignment.
        $this->actingAs($owner)->post($url, $payload)->assertRedirect();
        self::assertSame(1, DB::table('codebridge_project_assignments')->count());
    }

    public function test_cross_tenant_and_revoked_device_requests_are_rejected(): void
    {
        [$owner, $tenant, $device] = $this->fixture('desktop-one');
        [$other, $otherTenant] = $this->fixture('desktop-two');
        $url = $this->url($tenant, $device);

        $this->actingAs($other)->post($url, $this->payload())->assertForbidden();
        self::assertSame([], app(CodeBridgeCustomerDeviceDirectory::class)->forTenant($otherTenant, time())[0]['pending_projects']);

        DB::table('codebridge_device_credentials')
            ->where('tenant_id', $tenant)->where('device_id', $device)
            ->update(['revoked_at' => now()]);
        $this->actingAs($owner)->post($url, $this->payload())->assertNotFound();
        self::assertSame(0, DB::table('codebridge_project_assignments')->count());
    }

    public function test_invalid_repository_and_conflicting_assignment_fail_closed(): void
    {
        [$owner, $tenant, $device] = $this->fixture('desktop-one');
        $url = $this->url($tenant, $device);
        $this->actingAs($owner)->post($url, array_merge($this->payload(), [
            'repository_url' => 'file:///D:/private',
        ]))->assertSessionHasErrors('repository_url');
        $this->actingAs($owner)->post($url, array_merge($this->payload(), [
            'project_id' => '../other',
        ]))->assertSessionHasErrors('project_id');
        self::assertSame(0, DB::table('codebridge_project_assignments')->count());

        $this->actingAs($owner)->post($url, $this->payload())->assertRedirect();
        $this->actingAs($owner)->post($url, array_merge($this->payload(), [
            'repository_url' => 'https://github.com/kmjtechno/other-project',
        ]))->assertStatus(409);
        self::assertSame(1, DB::table('codebridge_project_assignments')->count());

        $this->actingAs($owner)->post($url, array_merge($this->payload(), [
            'project_id' => 'existing-project',
        ]))->assertSessionHasErrors('project_id');
        self::assertSame(1, DB::table('codebridge_project_assignments')->count());
    }

    public function test_local_project_without_repository_is_idempotent_and_does_not_grant_access(): void
    {
        [$owner, $tenant, $device] = $this->fixture('local-desktop');
        $payload = $this->payload();
        unset($payload['repository_url']);
        $url = $this->url($tenant, $device);
        $credential = DB::table('codebridge_device_credentials')->first();

        foreach ([$payload, array_merge($payload, ['repository_url' => '']), array_merge($payload, ['repository_url' => null])] as $request) {
            $this->actingAs($owner)->post($url, $request)
                ->assertRedirect()->assertSessionHasNoErrors();
        }

        $this->assertDatabaseHas('codebridge_project_assignments', [
            'tenant_id' => $tenant, 'device_id' => $device,
            'project_id' => 'kmj-calibration-studio',
            'repository_url' => '', 'status' => 'pending_local_setup',
            'requested_by' => $owner->id,
        ]);
        self::assertSame(1, DB::table('codebridge_project_assignments')->count());
        self::assertSame(1, DB::table('codebridge_device_pairings')->count());
        self::assertEquals($credential, DB::table('codebridge_device_credentials')->first());
        $devices = app(CodeBridgeCustomerDeviceDirectory::class)->forTenant($tenant, time());
        self::assertSame([['id' => 'existing-project', 'name' => 'Existing']], $devices[0]['projects']);
        self::assertSame('', $devices[0]['pending_projects'][0]['repository']);
        self::assertSame('not_verified', $devices[0]['connection_status']);

        $this->actingAs($owner)->post($url, $this->payload())->assertStatus(409);
        self::assertSame(1, DB::table('codebridge_project_assignments')->count());
    }

    public function test_local_project_still_requires_tenant_authority_and_active_device_license(): void
    {
        [$owner, $tenant, $device] = $this->fixture('local-desktop');
        [$other] = $this->fixture('other-desktop');
        $payload = $this->payload();
        unset($payload['repository_url']);
        $url = $this->url($tenant, $device);

        $this->post($url, $payload)->assertRedirect('/login');
        $this->actingAs($other)->post($url, $payload)->assertForbidden();
        DB::table('kslp_licenses')->where('customer_id', $tenant)->update(['status' => 'suspended']);
        $this->actingAs($owner)->post($url, $payload)->assertNotFound();
        DB::table('kslp_licenses')->where('customer_id', $tenant)->update(['status' => 'active']);
        DB::table('codebridge_device_credentials')->where('tenant_id', $tenant)->update(['revoked_at' => now()]);
        $this->actingAs($owner)->post($url, $payload)->assertNotFound();
        self::assertSame(0, DB::table('codebridge_project_assignments')->count());
    }

    private function url(string $tenant, string $device): string
    {
        return '/services/kmj-codebridge/organizations/'.$tenant.'/devices/'.$device.'/projects/assign';
    }

    /** @return array<string,string> */
    private function payload(): array
    {
        return [
            'project_id' => 'kmj-calibration-studio',
            'project_name' => 'KMJ Calibration Studio',
            'repository_url' => 'https://github.com/kmjtechno/kmj-calibration-pro',
        ];
    }

    /** @return array{User,string,string} */
    private function fixture(string $device): array
    {
        $user = User::factory()->create();
        $tenant = (string) Str::uuid();
        $license = (string) Str::uuid();
        $activation = (string) Str::uuid();
        $now = now();
        DB::table('organizations')->insert([
            'id' => $tenant, 'name' => 'KMJ Test Organization',
            'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('organization_memberships')->insert([
            'id' => (string) Str::uuid(), 'organization_id' => $tenant,
            'user_id' => $user->id, 'role' => 'owner',
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
            'id' => $activation, 'license_id' => $license,
            'server_identity' => 'codebridge-device:'.$device,
            'machine_identity_hash' => hash('sha256', $device),
            'idempotency_key' => 'project-assignment-test:'.$device,
            'activated_at' => $now, 'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('codebridge_device_credentials')->insert([
            'id' => (string) Str::uuid(), 'license_id' => $license,
            'activation_id' => $activation, 'tenant_id' => $tenant,
            'device_id' => $device,
            'server_identity' => 'codebridge-device:'.$device,
            'token_hash' => hash('sha256', 'test-token-'.$device),
            'lease_sequence' => 0, 'expires_at_epoch' => time() + 3600,
        ]);
        DB::table('codebridge_device_pairings')->insert([
            'id' => (string) Str::uuid(),
            'device_code_hash' => hash('sha256', 'device-code:'.$device),
            'user_code_hash' => hash('sha256', 'user-code:'.$device),
            'device_id' => $device, 'device_name' => $device,
            'platform' => 'win32', 'arch' => 'x64',
            'project_id' => 'existing-project', 'project_name' => 'Existing',
            'requested_permissions' => json_encode(['read', 'write', 'execute']),
            'code_challenge' => str_repeat('x', 43),
            'status' => 'consumed', 'tenant_id' => $tenant,
            'license_id' => $license, 'activation_id' => $activation,
            'expires_at' => $now->copy()->addMinutes(5),
            'consumed_at' => $now,
            'created_at' => $now, 'updated_at' => $now,
        ]);

        return [$user, $tenant, $device];
    }
}
