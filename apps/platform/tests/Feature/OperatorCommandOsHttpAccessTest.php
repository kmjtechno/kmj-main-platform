<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class OperatorCommandOsHttpAccessTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_guest_cannot_open_command_os_over_http(): void
    {
        $this->get('/operator')->assertRedirect(route('login'));
    }

    public function test_verified_non_owner_cannot_open_command_os_over_http(): void
    {
        $this->actingAs(User::factory()->create())
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator')
            ->assertForbidden();
    }

    public function test_owner_flag_without_passkey_does_not_grant_command_os_access(): void
    {
        $user = User::factory()->create();
        $user->forceFill([
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ])->save();

        $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator')
            ->assertForbidden();
    }

    public function test_verified_owner_with_passkey_can_open_command_os_over_http(): void
    {
        $user = User::factory()->create();
        $user->forceFill([
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ])->save();

        DB::table('passkeys')->insert([
            'user_id' => $user->getKey(),
            'name' => 'HTTP owner route test passkey',
            'credential_id' => 'http-owner-route-'.bin2hex(random_bytes(12)),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page->component('operator'));
    }

    public function test_verified_passkey_owner_must_confirm_password_before_command_os(): void
    {
        $user = User::factory()->create();
        $user->forceFill([
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ])->save();

        DB::table('passkeys')->insert([
            'user_id' => $user->getKey(),
            'name' => 'HTTP owner confirmation test',
            'credential_id' => 'http-owner-confirm-'.bin2hex(random_bytes(12)),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $this->actingAs($user)
            ->get('/operator')
            ->assertRedirect(route('password.confirm'));
    }
}
