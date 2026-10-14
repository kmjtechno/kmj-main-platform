<?php

namespace Tests\Feature\Auth;

use Illuminate\Foundation\Testing\RefreshDatabase;
use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;
use Laravel\Fortify\Features;
use Tests\TestCase;

class RegistrationTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        $this->skipUnlessFortifyHas(Features::registration());
    }

    public function test_registration_screen_can_be_rendered()
    {
        $response = $this->get(route('register'));

        $response->assertOk();
    }

    public function test_production_log_mailer_cannot_create_unverifiable_user_or_organization(): void
    {
        $originalEnvironment = app()->environment();

        try {
            app()->detectEnvironment(static fn (): string => 'production');
            config()->set('mail.default', 'log');

            $this->post(route('register.store'), [
                'name' => 'Undeliverable User',
                'email' => 'undeliverable@example.test',
                'password' => 'password',
                'password_confirmation' => 'password',
            ])->assertSessionHasErrors(['email']);

            $this->assertDatabaseMissing('users', ['email' => 'undeliverable@example.test']);
            $this->assertDatabaseMissing('organizations', [
                'name' => "Undeliverable User's Organization",
            ]);
            $this->assertGuest();
        } finally {
            app()->detectEnvironment(static fn (): string => $originalEnvironment);
        }
    }

    public function test_new_users_can_register()
    {
        $response = $this->post(route('register.store'), [
            'name' => 'Test User',
            'email' => 'test@example.com',
            'password' => 'password',
            'password_confirmation' => 'password',
        ]);

        $user = $this->app['auth']->user();

        $this->assertAuthenticated();
        $this->assertNotNull($user);
        $this->assertDatabaseHas('organizations', [
            'name' => "Test User's Organization",
        ]);

        $membership = OrganizationMembership::query()
            ->where('user_id', $user->getAuthIdentifier())
            ->where('role', 'owner')
            ->first();

        $this->assertNotNull($membership);
        $this->assertDatabaseHas('organizations', [
            'id' => $membership->organization_id,
            'name' => "Test User's Organization",
        ]);
        $response->assertRedirect(route('dashboard', absolute: false));
    }
}
