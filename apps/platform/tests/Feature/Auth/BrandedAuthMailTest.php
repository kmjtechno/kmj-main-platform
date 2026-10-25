<?php

namespace Tests\Feature\Auth;

use App\Models\User;
use Illuminate\Auth\Notifications\ResetPassword;
use Illuminate\Auth\Notifications\VerifyEmail;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\URL;
use Tests\TestCase;

class BrandedAuthMailTest extends TestCase
{
    use RefreshDatabase;

    public function test_verification_notification_keeps_signed_laravel_link_and_official_brand(): void
    {
        $user = User::factory()->unverified()->create();

        $message = (new VerifyEmail)->toMail($user);

        $this->assertSame('Verify your email address | KMJ TECHNO', $message->subject);
        $this->assertSame([
            'html' => 'emails.kmj-auth-transactional',
            'text' => 'emails.kmj-auth-transactional-text',
        ], $message->view);

        $url = $message->viewData['actionUrl'];
        $this->assertStringContainsString('/email/verify/', $url);
        $this->assertStringContainsString('signature=', $url);
        $this->assertTrue(URL::hasValidSignature(Request::create($url)));

        $html = view('emails.kmj-auth-transactional', $message->viewData)->render();
        $text = view('emails.kmj-auth-transactional-text', $message->viewData)->render();
        $this->assertStringContainsString('/assets/brand/kmj-email-lockup-dark.png', $html);
        $this->assertStringContainsString('INNOVATE | BUILD | SCALE', $html);
        $this->assertStringContainsString('INNOVATE | BUILD | SCALE', $text);
        $this->assertStringContainsString('Verify email address', $html);
        $this->assertStringContainsString('Verify email address', $text);
        $this->assertStringContainsString($url, $text);
        $this->assertStringNotContainsString('Unsubscribe', $html);
        $this->assertStringNotContainsString('<script', $html);
    }

    public function test_password_reset_notification_preserves_token_and_mailbox_and_plain_text_link(): void
    {
        $user = User::factory()->create(['email' => 'owner+test@kmjtechno.com']);
        $token = 'safe-test-reset-token';

        $message = (new ResetPassword($token))->toMail($user);

        $this->assertSame('Reset your password | KMJ TECHNO', $message->subject);
        $url = $message->viewData['actionUrl'];
        $this->assertStringContainsString('/reset-password/'.$token, $url);
        $this->assertStringContainsString('owner%2Btest%40kmjtechno.com', $url);
        $this->assertSame('Reset my password', $message->viewData['actionText']);

        $html = view('emails.kmj-auth-transactional', $message->viewData)->render();
        $text = view('emails.kmj-auth-transactional-text', $message->viewData)->render();
        $this->assertStringContainsString('Reset your password', $html);
        $this->assertStringContainsString('Reset my password', $html);
        $this->assertStringContainsString($url, $text);
        $this->assertStringNotContainsString('&amp;', $text);
        $this->assertStringContainsString('expires in', $text);
    }

    public function test_dynamic_content_is_html_escaped(): void
    {
        $user = User::factory()->unverified()->create();
        $message = (new VerifyEmail)->toMail($user);
        $data = $message->viewData;
        $data['intro'] = '<script>alert("xss")</script>';
        $html = view('emails.kmj-auth-transactional', $data)->render();
        $this->assertStringNotContainsString('<script>', $html);
        $this->assertStringContainsString('&lt;script&gt;', $html);
    }

    public function test_login_and_mail_transport_config_remain_untouched(): void
    {
        $this->assertSame('smtp-relay.brevo.com', config('mail.mailers.kmj_brevo.host'));
        $this->assertSame('smtps', config('mail.mailers.kmj_brevo.scheme'));
        $this->assertSame(465, config('mail.mailers.kmj_brevo.port'));
    }
}
