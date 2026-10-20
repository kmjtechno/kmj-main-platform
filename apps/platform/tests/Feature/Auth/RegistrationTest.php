<?php

namespace Tests\Feature\Auth;

use Illuminate\Foundation\Http\Middleware\PreventRequestForgery;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Inertia\Testing\AssertableInertia as Assert;
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

    public function test_public_registration_cta_respects_production_mail_readiness(): void
    {
        $this->withoutVite();

        // Development/testing can still exercise isolated registration.
        $this->get('/')->assertOk()->assertInertia(fn (Assert $page) => $page
            ->where('publicSite.registration_available', true)
            ->etc());

        $originalEnvironment = app()->environment();

        try {
            app()->instance('env', 'production');
            config()->set('mail.default', 'log');

            // The public header must not offer a working signup CTA while
            // the production registration endpoint fails closed.
            $this->get('/')->assertOk()->assertInertia(fn (Assert $page) => $page
                ->where('publicSite.registration_available', false)
                ->etc());
        } finally {
            app()->instance('env', $originalEnvironment);
        }
    }

    public function test_production_log_mailer_cannot_create_unverifiable_user_or_organization(): void
    {
        $originalEnvironment = app()->environment();

        try {
            // Tests run under PHPUnit CLI, which may force --env=testing
            // and override EnvironmentDetector callback resolution.
            // Override the actual app env binding used by isProduction().
            app()->instance('env', 'production');
            // Laravel 13 re-enables request-forgery checks when tests simulate
            // production; bypass only this middleware in this isolated test.
            $this->withoutMiddleware(PreventRequestForgery::class);
            self::assertTrue(app()->isProduction());
            config()->set('mail.default', 'log');

            $this->post(route('register.store'), [
                'name' => 'Undeliverable User',
                'email' => 'undeliverable@example.test',
                // Exercise mail-readiness rather than production password policy.
                // Production requires mixed case, digits, symbols and >=12 chars.
                'password' => 'Kmj!9vX#2026sQ7rL8',
                'password_confirmation' => 'Kmj!9vX#2026sQ7rL8',
                'account_type' => 'individual',
                'phone' => '+91 98765 43210',
                'country' => 'India',
            ])->assertSessionHasErrors(['email']);

            $this->assertDatabaseMissing('users', ['email' => 'undeliverable@example.test']);
            $this->assertDatabaseMissing('organizations', [
                'name' => "Undeliverable User's Organization",
            ]);
            $this->assertGuest();
        } finally {
            app()->instance('env', $originalEnvironment);
        }
    }

    public function test_public_registration_is_rate_limited_before_account_creation(): void
    {
        $this->withServerVariables(['REMOTE_ADDR' => '198.51.100.241']);

        for ($attempt = 0; $attempt < 6; $attempt++) {
            $this->post(route('register.store'), [
                'name' => '',
                'email' => 'invalid',
                'password' => '',
                'password_confirmation' => '',
            ])->assertSessionHasErrors();
        }

        $this->post(route('register.store'), [
            'name' => '',
            'email' => 'invalid',
            'password' => '',
            'password_confirmation' => '',
        ])->assertStatus(429);

        $this->assertDatabaseCount('users', 0);
    }

    public function test_signup_throttle_does_not_block_registration_view_or_login(): void
    {
        $this->withServerVariables(['REMOTE_ADDR' => '198.51.100.242']);

        for ($attempt = 0; $attempt < 7; $attempt++) {
            $response = $this->post(route('register.store'), [
                'name' => '',
                'email' => 'invalid',
                'password' => '',
                'password_confirmation' => '',
            ]);

            if ($attempt === 6) {
                $response->assertStatus(429);
            }
        }

        $this->get(route('register'))->assertOk();
        $this->post('/login', [
            'email' => 'nonexistent@example.test',
            'password' => 'invalid-password',
        ])->assertStatus(302);
        $this->assertDatabaseCount('users', 0);
    }

    public function test_signup_hourly_quota_cannot_be_bypassed_by_waiting_one_minute(): void
    {
        $this->withServerVariables(['REMOTE_ADDR' => '198.51.100.243']);

        for ($attempt = 0; $attempt < 30; $attempt++) {
            if ($attempt > 0 && $attempt % 6 === 0) {
                $this->travel(61)->seconds();
            }

            $this->post(route('register.store'), [
                'name' => '',
                'email' => 'invalid',
                'password' => '',
                'password_confirmation' => '',
            ])->assertSessionHasErrors();
        }

        $this->post(route('register.store'), [
            'name' => '',
            'email' => 'invalid',
            'password' => '',
            'password_confirmation' => '',
        ])->assertStatus(429);

        $this->assertDatabaseCount('users', 0);
    }

    public function test_new_users_can_register()
    {
        $response = $this->post(route('register.store'), [
            'name' => 'Test User',
            'email' => 'test@example.com',
            'password' => 'password',
            'password_confirmation' => 'password',
            'account_type' => 'individual',
            'phone' => '+91 98765 43210',
            'country' => 'India',
            'service_interest' => 'software',
        ]);

        $user = $this->app['auth']->user();

        $this->assertAuthenticated();
        $this->assertNotNull($user);
        $this->assertDatabaseHas('organizations', [
            'name' => "Test User's Organization",
        ]);
        $this->assertDatabaseHas('customer_profiles', [
            'user_id' => $user->getKey(),
            'account_type' => 'individual',
            'phone' => '+91 98765 43210',
            'country' => 'India',
            'company_name' => null,
            'service_interest' => 'software',
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
    public function test_business_registration_requires_company_name_before_any_write(): void
    {
        $this->withServerVariables(['REMOTE_ADDR' => '198.51.100.244']);

        $this->post(route('register.store'), [
            'name' => 'Business Owner',
            'email' => 'company-required@example.test',
            'password' => 'password',
            'password_confirmation' => 'password',
            'account_type' => 'business',
            'phone' => '+44 20 7946 0123',
            'country' => 'United Kingdom',
        ])->assertSessionHasErrors(['company_name']);

        $this->assertDatabaseMissing('users', [
            'email' => 'company-required@example.test',
        ]);
        $this->assertDatabaseCount('customer_profiles', 0);
    }

    public function test_business_registration_persists_contact_and_creates_owned_business_organization(): void
    {
        $this->withServerVariables(['REMOTE_ADDR' => '198.51.100.245']);

        $this->post(route('register.store'), [
            'name' => 'Business Owner',
            'email' => 'business-owner@example.test',
            'password' => 'password',
            'password_confirmation' => 'password',
            'account_type' => 'business',
            'company_name' => 'World Cinema Systems',
            'phone' => '+44 20 7946 0123',
            'country' => 'United Kingdom',
            'service_interest' => 'cinema',
        ])->assertRedirect(route('dashboard', absolute: false));

        $user = $this->app['auth']->user();
        $this->assertNotNull($user);

        $this->assertDatabaseHas('customer_profiles', [
            'user_id' => $user->getKey(),
            'account_type' => 'business',
            'company_name' => 'World Cinema Systems',
            'country' => 'United Kingdom',
            'service_interest' => 'cinema',
        ]);
        $this->assertDatabaseHas('organizations', ['name' => 'World Cinema Systems']);
        $this->assertDatabaseHas('organization_memberships', [
            'user_id' => $user->getKey(),
            'role' => 'owner',
        ]);
        $this->assertDatabaseCount('entitlements', 0);
    }

    public function test_registration_does_not_accept_unrecognized_product_interests(): void
    {
        $this->withServerVariables(['REMOTE_ADDR' => '198.51.100.246']);

        $this->post(route('register.store'), [
            'name' => 'Potential Customer',
            'email' => 'bad-interest@example.test',
            'password' => 'password',
            'password_confirmation' => 'password',
            'account_type' => 'individual',
            'phone' => '+1 415 555 0134',
            'country' => 'United States',
            'service_interest' => 'grant_superadmin_license',
        ])->assertSessionHasErrors(['service_interest']);

        $this->assertDatabaseMissing('users', [
            'email' => 'bad-interest@example.test',
        ]);
    }
}
