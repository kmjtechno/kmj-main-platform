<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class PlatformOwnerConsoleTest extends TestCase
{
    use RefreshDatabase;

    public function test_regular_user_cannot_open_operator_console(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);

        $response = $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator');

        $response->assertForbidden();
    }

    public function test_platform_owner_without_passkey_is_rejected(): void
    {
        $user = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);

        $response = $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator');

        $response->assertForbidden();
    }

    public function test_passkey_enabled_platform_owner_can_open_operator_console(): void
    {
        $user = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);

        DB::table('passkeys')->insert([
            'user_id' => $user->id,
            'name' => 'Owner passkey',
            'credential_id' => 'owner-console-test-credential',
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $response = $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator');

        $response->assertOk();
        $response->assertInertia(fn (Assert $page) => $page
            ->component('operator')
            ->where('metrics.users', 1)
            ->where('metrics.organizations', 0)
            ->where('metrics.entitlements', 0)
            ->where('metrics.orders', 0)
            ->where('metrics.confirmed_orders', 0)
            ->has('recentOrders', 0));
    }
}
