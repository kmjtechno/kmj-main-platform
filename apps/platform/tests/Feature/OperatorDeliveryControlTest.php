<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

final class OperatorDeliveryControlTest extends TestCase
{
    use RefreshDatabase;

    private string $path;

    protected function setUp(): void
    {
        parent::setUp();

        $this->path = storage_path('framework/testing/control-request.json');
        File::ensureDirectoryExists(dirname($this->path));
        File::delete($this->path);
        config(['kmj.ops.control_request_path' => $this->path]);
    }

    protected function tearDown(): void
    {
        File::delete($this->path);
        parent::tearDown();
    }

    public function test_regular_user_cannot_request_delivery_action(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);

        $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/ops/actions/delivery-control', [
                'action' => 'dispatch_worker',
            ])
            ->assertForbidden();

        $this->assertFileDoesNotExist($this->path);
    }

    public function test_owner_can_enqueue_allowlisted_worker_dispatch_and_it_is_audited(): void
    {
        $owner = $this->platformOwner();

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/ops/actions/delivery-control', [
                'action' => 'dispatch_worker',
            ])
            ->assertRedirect(route('operator.ops.index'));

        $request = json_decode(File::get($this->path), true, 32, JSON_THROW_ON_ERROR);
        $this->assertSame(1, $request['version']);
        $this->assertSame('dispatch_worker', $request['action']);
        $this->assertSame($owner->id, $request['actor_user_id']);
        $this->assertArrayHasKey('request_id', $request);
        $this->assertArrayHasKey('requested_at', $request);
        $this->assertArrayNotHasKey('password', $request);

        $this->assertDatabaseHas('operator_action_audits', [
            'actor_user_id' => $owner->id,
            'action' => 'delivery.dispatch_worker',
            'outcome' => 'queued',
        ]);
    }

    public function test_requeue_safe_issue_requires_positive_issue_number(): void
    {
        $owner = $this->platformOwner();

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/ops/actions/delivery-control', [
                'action' => 'requeue_safe_issue',
                'issue_number' => 142,
            ])
            ->assertRedirect(route('operator.ops.index'));

        $request = json_decode(File::get($this->path), true, 32, JSON_THROW_ON_ERROR);
        $this->assertSame('requeue_safe_issue', $request['action']);
        $this->assertSame(['issue_number' => 142], $request['parameters']);
    }

    public function test_rerun_failed_ci_requires_positive_run_id(): void
    {
        $owner = $this->platformOwner();

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/ops/actions/delivery-control', [
                'action' => 'rerun_failed_ci',
                'run_id' => 999,
            ])
            ->assertRedirect(route('operator.ops.index'));

        $request = json_decode(File::get($this->path), true, 32, JSON_THROW_ON_ERROR);
        $this->assertSame(['run_id' => 999], $request['parameters']);
    }

    public function test_unknown_or_high_risk_actions_fail_closed(): void
    {
        $owner = $this->platformOwner();

        foreach (['production_deploy', 'dns_change', 'shell', 'billing_change'] as $action) {
            File::delete($this->path);

            $this->actingAs($owner)
                ->withSession(['auth.password_confirmed_at' => time()])
                ->post('/operator/ops/actions/delivery-control', [
                    'action' => $action,
                ])
                ->assertSessionHasErrors('action');

            $this->assertFileDoesNotExist($this->path);
        }
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
            'name' => 'Ops control passkey',
            'credential_id' => 'ops-control-test-credential',
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $user;
    }
}
