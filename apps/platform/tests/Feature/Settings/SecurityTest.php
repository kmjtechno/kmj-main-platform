<?php

namespace Tests\Feature\Settings;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;
use Inertia\Testing\AssertableInertia as Assert;
use Laravel\Fortify\Features;
use Tests\TestCase;

class SecurityTest extends TestCase
{
    use RefreshDatabase;

    public function test_security_page_is_displayed()
    {
        $this->skipUnlessFortifyHas(Features::twoFactorAuthentication());

        Features::twoFactorAuthentication([
            'confirm' => true,
            'confirmPassword' => true,
        ]);
        /* @chisel-passkeys */
        Features::passkeys([
            'confirmPassword' => true,
        ]);
        /* @end-chisel-passkeys */

        $user = User::factory()->create();

        $this->actingAs($user)
            /* @chisel-password-confirmation */
            ->withSession(['auth.password_confirmed_at' => time()])
            /* @end-chisel-password-confirmation */
            ->get(route('security.edit'))
            ->assertInertia(fn (Assert $page) => $page
                ->component('settings/security')
                /* @chisel-passkeys */
                ->where('canManagePasskeys', true)
                ->where('passkeys', [])
                /* @end-chisel-passkeys */
                ->where('canManageTwoFactor', true)
                ->where('twoFactorEnabled', false),
            );
    }

    /* @chisel-password-confirmation */
    public function test_security_page_requires_password_confirmation_when_enabled()
    {
        $this->skipUnlessFortifyHas(Features::twoFactorAuthentication());

        $user = User::factory()->create();

        Features::twoFactorAuthentication([
            'confirm' => true,
            'confirmPassword' => true,
        ]);

        $response = $this->actingAs($user)
            ->get(route('security.edit'));

        $response->assertRedirect(route('password.confirm'));
    }
    /* @end-chisel-password-confirmation */

    public function test_security_page_renders_without_two_factor_when_feature_is_disabled()
    {
        $this->skipUnlessFortifyHas(Features::twoFactorAuthentication());

        config(['fortify.features' => []]);

        $user = User::factory()->create();

        $this->actingAs($user)
            /* @chisel-password-confirmation */
            ->withSession(['auth.password_confirmed_at' => time()])
            /* @end-chisel-password-confirmation */
            ->get(route('security.edit'))
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('settings/security')
                /* @chisel-passkeys */
                ->where('canManagePasskeys', false)
                ->where('passkeys', [])
                /* @end-chisel-passkeys */
                ->where('canManageTwoFactor', false)
                ->missing('twoFactorEnabled')
                ->missing('requiresConfirmation'),
            );
    }

    public function test_other_database_sessions_can_be_signed_out_without_touching_another_user()
    {
        config(['session.driver' => 'database']);

        $user = User::factory()->create();
        $otherUser = User::factory()->create();

        DB::table('sessions')->insert([
            ['id' => 'other-session', 'user_id' => $user->id, 'ip_address' => '127.0.0.2', 'user_agent' => 'other', 'payload' => '', 'last_activity' => time()],
            ['id' => 'different-user-session', 'user_id' => $otherUser->id, 'ip_address' => '127.0.0.3', 'user_agent' => 'different-user', 'payload' => '', 'last_activity' => time()],
        ]);

        $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->delete(route('security.sessions.destroy-other'))
            ->assertRedirect();

        $this->assertDatabaseMissing('sessions', ['id' => 'other-session', 'user_id' => $user->id]);
        $this->assertDatabaseHas('sessions', ['id' => 'different-user-session', 'user_id' => $otherUser->id]);
        $this->assertAuthenticatedAs($user);
    }

    public function test_signing_out_other_sessions_requires_password_confirmation()
    {
        $user = User::factory()->create();

        $this->actingAs($user)
            ->delete(route('security.sessions.destroy-other'))
            ->assertRedirect(route('password.confirm'));
    }

    public function test_password_can_be_updated()
    {
        $user = User::factory()->create();

        $response = $this
            ->actingAs($user)
            ->from(route('security.edit'))
            ->put(route('user-password.update'), [
                'current_password' => 'password',
                'password' => 'new-password',
                'password_confirmation' => 'new-password',
            ]);

        $response
            ->assertSessionHasNoErrors()
            ->assertRedirect(route('security.edit'));

        $this->assertTrue(Hash::check('new-password', $user->refresh()->password));
    }

    public function test_correct_password_must_be_provided_to_update_password()
    {
        $user = User::factory()->create();

        $response = $this
            ->actingAs($user)
            ->from(route('security.edit'))
            ->put(route('user-password.update'), [
                'current_password' => 'wrong-password',
                'password' => 'new-password',
                'password_confirmation' => 'new-password',
            ]);

        $response
            ->assertSessionHasErrors('current_password')
            ->assertRedirect(route('security.edit'));
    }
}
