<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class DevForgeOwnerControlTest extends TestCase
{
    use RefreshDatabase;

    public function test_guest_must_authenticate(): void
    {
        $this->get('/operator/devforge')->assertRedirect('/login');
        $this->post('/operator/devforge/actions', [
            'action' => 'install', 'confirm' => 'CONTROL_KMJ_DEVFORGE',
        ])->assertRedirect('/login');
    }

    public function test_regular_user_cannot_read_or_control_devforge(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);
        $session = ['auth.password_confirmed_at' => time()];
        $this->actingAs($user)->withSession($session)->get('/operator/devforge')->assertForbidden();
        $this->actingAs($user)->withSession($session)->post('/operator/devforge/actions', [
            'action' => 'install', 'confirm' => 'CONTROL_KMJ_DEVFORGE',
        ])->assertForbidden();
    }

    public function test_verified_passkey_owner_can_read_fail_closed_status_without_host_broker(): void
    {
        $owner = $this->owner();
        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/devforge')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('operator-devforge')
                ->has('devforge.broker_ready')
                ->has('devforge.state')
                ->has('devforge.healthy'));
    }

    public function test_unknown_and_unconfirmed_actions_are_rejected_before_host_execution(): void
    {
        $owner = $this->owner();
        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/devforge/actions', ['action' => 'shell', 'confirm' => 'CONTROL_KMJ_DEVFORGE'])
            ->assertSessionHasErrors('action');

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/devforge/actions', ['action' => 'install', 'confirm' => 'YES'])
            ->assertSessionHasErrors('confirm');
    }

    private function owner(): User
    {
        $user = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        DB::table('passkeys')->insert([
            'user_id' => $user->id,
            'name' => 'DevForge owner test passkey',
            'credential_id' => 'devforge-owner-test-credential',
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $user;
    }
}
