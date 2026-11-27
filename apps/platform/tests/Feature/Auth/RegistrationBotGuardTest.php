<?php

namespace Tests\Feature\Auth;

use App\Models\User;
use App\Services\Auth\RegistrationBotGuard;
use Illuminate\Foundation\Http\Middleware\PreventRequestForgery;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Inertia\Testing\AssertableInertia as Assert;
use Laravel\Fortify\Features;
use Tests\TestCase;

class RegistrationBotGuardTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        $this->skipUnlessFortifyHas(Features::registration());
        config()->set('registration.bot_guard.enabled', true);
        config()->set('registration.bot_guard.min_seconds', 0);
        $this->withoutMiddleware(PreventRequestForgery::class);
    }

    /** @return array<string, string> */
    private function payload(array $extra = []): array
    {
        return [
            'name' => 'Guard Test',
            'email' => 'guard@example.com',
            'password' => 'password',
            'password_confirmation' => 'password',
            'account_type' => 'individual',
            'phone' => '+91 98765 43210',
            'country' => 'India',
            ...$extra,
        ];
    }

    public function test_register_page_carries_a_signed_form_token(): void
    {
        $this->get(route('register'))
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('auth/register')
                ->has('formToken'));
    }

    public function test_post_without_a_token_creates_nothing(): void
    {
        $this->post(route('register.store'), $this->payload())
            ->assertSessionHasErrors('registration');

        $this->assertSame(0, User::query()->count());
    }

    public function test_filled_honeypot_creates_nothing_even_with_a_valid_token(): void
    {
        $token = app(RegistrationBotGuard::class)->issueToken();

        $this->post(route('register.store'), $this->payload([
            'kmj_form_token' => $token,
            'website_url' => 'https://spam.example',
        ]))->assertSessionHasErrors('registration');

        $this->assertSame(0, User::query()->count());
    }

    public function test_a_token_submitted_too_fast_is_rejected(): void
    {
        config()->set('registration.bot_guard.min_seconds', 3600);
        $token = app(RegistrationBotGuard::class)->issueToken();

        $this->post(route('register.store'), $this->payload(['kmj_form_token' => $token]))
            ->assertSessionHasErrors('registration');

        $this->assertSame(0, User::query()->count());
    }

    public function test_garbage_token_is_rejected(): void
    {
        $this->post(route('register.store'), $this->payload(['kmj_form_token' => 'not-a-token']))
            ->assertSessionHasErrors('registration');

        $this->assertSame(0, User::query()->count());
    }

    public function test_valid_token_registers_once_and_cannot_be_replayed(): void
    {
        $token = app(RegistrationBotGuard::class)->issueToken();

        $this->post(route('register.store'), $this->payload(['kmj_form_token' => $token]))
            ->assertRedirect(route('dashboard', absolute: false));
        $this->assertSame(1, User::query()->count());

        $this->post('/logout');
        $this->post(route('register.store'), $this->payload([
            'kmj_form_token' => $token,
            'email' => 'second@example.com',
        ]))->assertSessionHasErrors('registration');

        $this->assertSame(1, User::query()->count());
    }

    public function test_guard_only_applies_to_register_and_not_to_login(): void
    {
        User::factory()->create(['email' => 'login@example.com']);

        $this->post(route('login.store'), [
            'email' => 'login@example.com',
            'password' => 'password',
        ])->assertSessionDoesntHaveErrors('registration');
    }
}
