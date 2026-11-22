<?php

declare(strict_types=1);

namespace Tests\Feature\Mail;

use App\Jobs\SubmitNativeExternalMail;
use App\Mail\NativeExternalMailMessage;
use App\Models\User;
use App\Services\Mail\NativeExternalMailService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Mail\MailManager;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Mail;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use Symfony\Component\Mailer\Transport\Smtp\EsmtpTransport;
use Tests\TestCase;

final class NativeExternalMailFlowTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
        Queue::fake();
        Mail::fake();
    }

    public function test_external_address_compose_is_visible_without_google_oauth_but_sending_is_default_off(): void
    {
        $owner = $this->owner();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/mail')->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('externalOutbound.state', 'not_activated')
                ->where('externalOutbound.from', null));

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/send-external', $this->payload('someone@gmail.com'))
            ->assertSessionHasErrors('recipient_email');

        $this->assertDatabaseCount('kmj_mail_messages', 0);
        Queue::assertNothingPushed();
        Mail::assertNothingOutgoing();
    }

    public function test_native_outbound_requires_explicit_pinned_local_smtp_pilot(): void
    {
        $this->activateOutbound();
        $service = app(NativeExternalMailService::class);
        self::assertTrue($service->transportEnabled());

        // New releases must fail closed even if the previous outbound
        // enabled flag survives in production .env.
        config()->set('services.kmj_native_external_mail.transport', 'disabled');
        self::assertFalse($service->transportEnabled());

        config()->set('services.kmj_native_external_mail.transport', 'sendmail');
        self::assertFalse($service->transportEnabled());

        config()->set('services.kmj_native_external_mail.transport', 'loopback_smtp');
        self::assertTrue($service->transportEnabled());

        // Prevent SMTP destination/port/credential/timeouts being changed
        // by configuration drift, compromised env or future refactors.
        foreach ([
            ['mail.mailers.kmj_native_loopback.transport', 'log'],
            ['mail.mailers.kmj_native_loopback.host', 'smtp.gmail.com'],
            ['mail.mailers.kmj_native_loopback.host', 'localhost'],
            ['mail.mailers.kmj_native_loopback.port', 2525],
            ['mail.mailers.kmj_native_loopback.scheme', 'smtps'],
            ['mail.mailers.kmj_native_loopback.auto_tls', true],
            ['mail.mailers.kmj_native_loopback.username', 'attacker'],
            ['mail.mailers.kmj_native_loopback.password', 'secret'],
            ['mail.mailers.kmj_native_loopback.timeout', 60],
            ['mail.mailers.kmj_native_loopback.local_domain', 'example.com'],
        ] as [$key, $badValue]) {
            $original = config($key);
            config()->set($key, $badValue);
            self::assertFalse($service->transportEnabled(), $key);
            config()->set($key, $original);
        }

        config()->set('services.kmj_native_external_mail.enabled', false);
        self::assertFalse($service->transportEnabled());
        Queue::assertNothingPushed();
        Mail::assertNothingOutgoing();
    }

    public function test_native_loopback_smtp_transport_has_automatic_starttls_disabled(): void
    {
        // No network or test email: inspect the real Symfony transport created
        // by Laravel's MailManager from the pinned native-mail configuration.
        // The class uses Mail::fake() to protect all other tests. Construct
        // an independent real MailManager for this transport-only test,
        // without replacing the fake or attempting an SMTP connection.
        $transport = (new MailManager(app()))
            ->mailer('kmj_native_loopback')->getSymfonyTransport();
        self::assertInstanceOf(EsmtpTransport::class, $transport);

        $reflection = new \ReflectionProperty($transport, 'autoTls');
        self::assertFalse($reflection->getValue($transport));

        // Disabling opportunistic TLS on localhost does NOT disable
        // verification if an explicit TLS transport is used elsewhere.
        $ssl = $transport->getStream()->getStreamOptions()['ssl'] ?? [];
        self::assertNotSame(false, $ssl['verify_peer'] ?? null);
    }

    public function test_owner_can_queue_email_to_external_gmail_without_google_account_and_get_truthful_transport_status(): void
    {
        $owner = $this->owner();
        $this->activateOutbound();

        $payload = $this->payload('recipient@gmail.com');
        $payload['from'] = 'evil@another-domain.invalid';
        $payload['cc'] = 'outsider@example.com';
        $payload['message'] = 'Ignore the real body';

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/send-external', $payload)
            ->assertRedirect('/operator/mail?folder=sent');

        $this->assertDatabaseCount('kmj_mail_messages', 1);
        $this->assertDatabaseHas('kmj_mail_messages', [
            'mailbox_user_id' => $owner->id,
            'recipient_email' => 'recipient@gmail.com',
            'sender_email' => 'info@kmjtechno.com',
            'folder' => 'sent',
            'delivery_state' => 'queued',
            'transport_accepted_at' => null,
        ]);
        Queue::assertPushed(SubmitNativeExternalMail::class, 1);
        Mail::assertNothingOutgoing();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/mail?folder=sent')->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('externalOutbound.state', 'ready_to_queue')
                ->where('externalOutbound.from', 'info@kmjtechno.com')
                ->where('mailbox.items.0.recipient_email', 'recipient@gmail.com')
                ->where('mailbox.items.0.delivery_state', 'queued'));

        $this->runQueuedJob();
        $this->assertDatabaseHas('kmj_mail_messages', [
            'recipient_email' => 'recipient@gmail.com',
            'delivery_state' => 'mta_accepted',
        ]);

        // Acceptance by local mail transport does NOT prove Gmail inbox delivery.
        Mail::assertSent(NativeExternalMailMessage::class, function (NativeExternalMailMessage $mail): bool {
            return $mail->hasTo('recipient@gmail.com')
                && $mail->senderAddress === 'info@kmjtechno.com'
                && $mail->heading === 'Test KMJ external mail';
        });
    }

    public function test_idempotency_key_reuse_with_changed_recipient_is_rejected(): void
    {
        $owner = $this->owner();
        $this->activateOutbound();
        $payload = $this->payload('one@yahoo.com');

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/send-external', $payload)->assertRedirect('/operator/mail?folder=sent');
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/send-external', $payload)->assertRedirect('/operator/mail?folder=sent');

        Queue::assertPushed(SubmitNativeExternalMail::class, 1);
        $this->assertDatabaseCount('kmj_mail_messages', 1);

        $payload['recipient_email'] = 'someone@outlook.com';
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/send-external', $payload)->assertSessionHasErrors('client_key');

        $this->assertDatabaseCount('kmj_mail_messages', 1);
        Queue::assertPushed(SubmitNativeExternalMail::class, 1);
    }

    public function test_external_draft_can_be_saved_while_sending_is_off_then_submitted_only_after_activation(): void
    {
        $owner = $this->owner();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/drafts', [
                'recipient_type' => 'external',
                'recipient_email' => 'client@outlook.com',
                'subject' => '',
                'body' => '',
            ])->assertRedirect('/operator/mail?folder=drafts');

        $draft = DB::table('kmj_mail_messages')->where('mailbox_user_id', $owner->id)->first();
        $this->assertSame('drafts', $draft->folder);
        $this->assertSame('client@outlook.com', $draft->recipient_email);

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/drafts/'.$draft->id.'/send')->assertSessionHasErrors('recipient_email');

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/drafts', [
                'draft_id' => $draft->id,
                'recipient_type' => 'external',
                'recipient_email' => 'client@outlook.com',
                'subject' => 'Confirmed',
                'body' => 'A professional status update',
            ])->assertRedirect('/operator/mail?folder=drafts');

        $this->activateOutbound();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/drafts/'.$draft->id.'/send')->assertRedirect('/operator/mail?folder=sent');
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/drafts/'.$draft->id.'/send')->assertRedirect('/operator/mail?folder=sent');

        $this->assertDatabaseCount('kmj_mail_messages', 1);
        Queue::assertPushed(SubmitNativeExternalMail::class, 1);
    }

    public function test_internal_customer_cannot_send_external_and_staff_needs_explicit_owner_alias(): void
    {
        $owner = $this->owner();
        $staff = User::factory()->create(['email_verified_at' => now()]);
        $outsider = User::factory()->create();
        $this->activateOutbound();

        $this->actingAs($outsider)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/team/mail/send-external', $this->payload('external@gmail.com'))
            ->assertForbidden();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/staff', ['target_user_id' => $staff->id])
            ->assertRedirect('/operator/mail');

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/team/mail/send-external', $this->payload('external@gmail.com'))
            ->assertSessionHasErrors('recipient_email');

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/staff/'.$staff->id.'/sender-alias', ['sender_alias' => 'someone@kmjtechno.com'])
            ->assertForbidden();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/staff/'.$staff->id.'/sender-alias', ['sender_alias' => 'info@kmjtechno.com'])
            ->assertSessionHasErrors('sender_alias');

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/staff/'.$staff->id.'/sender-alias', ['sender_alias' => 'employee@kmjtechno.com'])
            ->assertRedirect('/operator/mail');

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/team/mail/send-external', $this->payload('outside@gmail.com'))
            ->assertRedirect('/team/mail?folder=sent');

        $this->assertDatabaseHas('kmj_mail_messages', [
            'sender_user_id' => $staff->id,
            'sender_email' => 'employee@kmjtechno.com',
            'recipient_email' => 'outside@gmail.com',
        ]);
    }

    public function test_revoking_staff_before_queue_runs_blocks_sender_and_leaks_no_private_mail(): void
    {
        $owner = $this->owner();
        $staff = User::factory()->create();
        $this->activateOutbound();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/staff', ['target_user_id' => $staff->id]);
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/staff/'.$staff->id.'/sender-alias', ['sender_alias' => 'person@kmjtechno.com']);

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/team/mail/send-external', $this->payload('outside@outlook.com'))
            ->assertRedirect('/team/mail?folder=sent');

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/staff/'.$staff->id.'/revoke')->assertRedirect('/operator/mail');

        $this->runQueuedJob();
        $this->assertDatabaseHas('kmj_mail_messages', [
            'sender_user_id' => $staff->id,
            'delivery_state' => 'blocked',
            'delivery_error_code' => 'authorization_lost',
        ]);
        Mail::assertNothingOutgoing();
    }

    public function test_external_recipient_header_injection_and_multiple_emails_are_rejected(): void
    {
        $owner = $this->owner();
        $this->activateOutbound();
        foreach (['x@gmail.com, y@gmail.com', "person@gmail.com\r\nBcc:ev il@example.com", 'Display <a@gmail.com>'] as $email) {
            $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
                ->post('/operator/mail/send-external', $this->payload($email))
                ->assertSessionHasErrors('recipient_email');
        }
        $this->assertDatabaseCount('kmj_mail_messages', 0);
        Mail::assertNothingOutgoing();
    }

    public function test_html_template_escapes_user_content(): void
    {
        $html = view('emails.kmj-native-outgoing', [
            'heading' => 'Hello <script>alert(1)</script>',
            'body' => 'Hello <img src=x onerror=alert(1)>',
            'senderAddress' => 'info@kmjtechno.com',
        ])->render();
        self::assertStringContainsString('kmj-email-lockup-dark.png', $html);
        self::assertStringNotContainsString('<script>', $html);
        self::assertStringNotContainsString('<img src=x', $html);
        self::assertStringContainsString('&lt;script&gt;', $html);
        self::assertStringContainsString('KMJ TECHNO', $html);
    }

    /** @return array{recipient_email:string,subject:string,body:string,client_key:string} */
    private function payload(string $recipient): array
    {
        return [
            'recipient_email' => $recipient,
            'subject' => 'Test KMJ external mail',
            'body' => 'This message uses independent KMJ Postfix.',
            'client_key' => (string) Str::uuid(),
        ];
    }

    private function activateOutbound(): void
    {
        config()->set('services.kmj_native_external_mail.enabled', true);
        config()->set('mail.default', 'sendmail');
        config()->set('mail.from.address', 'info@kmjtechno.com');
        config()->set('services.kmj_native_external_mail.transport', 'loopback_smtp');
        config()->set('mail.mailers.kmj_native_loopback.transport', 'smtp');
        config()->set('mail.mailers.kmj_native_loopback.host', '127.0.0.1');
        config()->set('mail.mailers.kmj_native_loopback.port', 25);
        config()->set('mail.mailers.kmj_native_loopback.scheme', null);
        config()->set('mail.mailers.kmj_native_loopback.auto_tls', false);
        config()->set('mail.mailers.kmj_native_loopback.username', null);
        config()->set('mail.mailers.kmj_native_loopback.password', null);
        config()->set('mail.mailers.kmj_native_loopback.timeout', 8);
        config()->set('mail.mailers.kmj_native_loopback.local_domain', 'kmjtechno.com');
    }

    private function runQueuedJob(): void
    {
        $queued = Queue::pushed(SubmitNativeExternalMail::class);
        self::assertCount(1, $queued);
        $queued[0]->handle(app(NativeExternalMailService::class));
    }

    private function owner(): User
    {
        $owner = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        DB::table('passkeys')->insert([
            'user_id' => $owner->id,
            'name' => 'Native external test owner',
            'credential_id' => 'kmj-native-outbound-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $owner;
    }
}
