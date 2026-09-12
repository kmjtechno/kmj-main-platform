<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class OperatorOpsConsoleTest extends TestCase
{
    use RefreshDatabase;

    public function test_regular_user_cannot_open_ops_command_center(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);

        $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/ops')
            ->assertForbidden();
    }

    public function test_passkey_enabled_platform_owner_can_read_real_ops_snapshot(): void
    {
        $owner = $this->platformOwner();

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/ops')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('operator-ops')
                ->has('snapshot.captured_at')
                ->has('snapshot.cpu.cores')
                ->has('snapshot.memory.used_percent')
                ->has('snapshot.disk.used_percent')
                ->where('snapshot.database.status', 'healthy')
                ->has('readiness.deployment.status')
                ->has('readiness.backups.daily.status')
                ->has('readiness.autonomous_worker.status')
                ->has('readiness.free_ai_router.status')
                ->has('readiness.compliance_guard.signals')
                ->where('readiness.free_ai_router.paid_fallback', false)
                ->has('recentActions', 0));
    }

    public function test_ops_command_center_stays_available_when_audit_probe_is_unavailable(): void
    {
        $owner = $this->platformOwner();
        Schema::dropIfExists('operator_action_audits');

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/ops')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('operator-ops')
                ->has('snapshot.captured_at')
                ->has('readiness.compliance_guard.status')
                ->has('recentActions', 0));
    }

    public function test_queue_restart_is_owner_gated_and_audited(): void
    {
        $owner = $this->platformOwner();

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/ops/actions/queue-restart')
            ->assertRedirect(route('operator.ops.index'));

        $this->assertDatabaseHas('operator_action_audits', [
            'actor_user_id' => $owner->id,
            'action' => 'queue.restart',
            'outcome' => 'success',
        ]);
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
            'name' => 'Ops owner passkey',
            'credential_id' => 'ops-owner-test-credential',
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $user;
    }
}
