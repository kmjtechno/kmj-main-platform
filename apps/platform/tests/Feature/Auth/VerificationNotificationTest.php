<?php

namespace Tests\Feature\Auth;

use App\Models\User;
use Illuminate\Auth\Notifications\VerifyEmail;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Notification;
use Laravel\Fortify\Features;
use Tests\TestCase;

class VerificationNotificationTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        $this->skipUnlessFortifyHas(Features::emailVerification());
    }

    public function test_production_log_mailer_rejects_resend_instead_of_claiming_delivery(): void
    {
        $originalEnvironment = app()->environment();

        try {
            app()->instance('env', 'production');
            // Laravel 13 enforces request-forgery checks when a PHPUnit test
            // simulates production. Supply a matching CSRF session/header pair
            // instead of disabling the middleware being exercised.
            $csrfToken = bin2hex(random_bytes(16));
            $this->withSession(['_token' => $csrfToken])
                ->withHeader('X-CSRF-TOKEN', $csrfToken);
            config()->set('mail.default', 'log');
            Notification::fake();

            $user = User::factory()->unverified()->create();

            $this->actingAs($user)
                ->post(route('verification.send'))
                ->assertSessionHasErrors(['email']);

            Notification::assertNothingSent();
            $this->assertFalse($user->fresh()->hasVerifiedEmail());
        } finally {
            app()->instance('env', $originalEnvironment);
        }
    }

    public function test_sends_verification_notification(): void
    {
        Notification::fake();

        $user = User::factory()->unverified()->create();

        $this->actingAs($user)
            ->post(route('verification.send'))
            ->assertRedirect(route('home'));

        Notification::assertSentTo($user, VerifyEmail::class);
    }

    public function test_does_not_send_verification_notification_if_email_is_verified(): void
    {
        Notification::fake();

        $user = User::factory()->create();

        $this->actingAs($user)
            ->post(route('verification.send'))
            ->assertRedirect(route('dashboard', absolute: false));

        Notification::assertNothingSent();
    }
}
