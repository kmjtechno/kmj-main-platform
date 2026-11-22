<?php

namespace Tests\Feature\Mail;

use App\Models\User;
use App\Notifications\WorkforceMailPreviewNotification;
use App\Services\Mail\WorkforceMailCatalog;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Notification;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use InvalidArgumentException;
use Tests\TestCase;

final class WorkforceMailCenterTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_owner_mail_is_hidden_from_guests_regular_users_and_non_passkey_owner(): void
    {
        $this->get('/operator/mail')->assertRedirect('/login');

        $user = User::factory()->create();
        $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/mail')->assertForbidden();

        $untrustedOwner = User::factory()->create(['is_platform_owner' => true]);
        $this->actingAs($untrustedOwner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/mail')->assertForbidden();
    }

    public function test_passkey_owner_sees_only_owner_templates_and_honest_connection_state(): void
    {
        $owner = $this->owner();
        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/mail')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('mail-center')
                ->where('audience', 'owner')
                ->where('workspaceMode', 'native_internal')
                ->has('mailbox.items', 0)
                ->where('testEnabled', false)
                ->has('templates', 5)
                ->where('templates.0.kind', 'owner_briefing'));
    }

    public function test_team_mail_requires_separate_owner_granted_internal_staff_access(): void
    {
        $owner = $this->owner();
        $staff = User::factory()->create(['email_verified_at' => now()]);
        $outsider = User::factory()->create(['email_verified_at' => now()]);

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/team/mail')->assertForbidden();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/staff', ['target_user_id' => $staff->id])
            ->assertRedirect('/operator/mail');

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/team/mail')->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('mail-center')
                ->where('audience', 'staff')
                ->where('workspaceMode', 'native_internal')
                ->has('mailbox.items', 0)
                ->has('templates', 5)
                ->where('templates.0.kind', 'team_welcome'));

        $this->actingAs($outsider)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/team/mail')->assertForbidden();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/staff/'.$staff->id.'/revoke')->assertRedirect('/operator/mail');

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/team/mail')->assertForbidden();
    }

    public function test_existing_customer_organization_membership_does_not_grant_internal_mail(): void
    {
        $customer = User::factory()->create(['email_verified_at' => now()]);
        app(\\KMJ\\MainPlatform\\Organizations\\Services\\OrganizationCreator::class)
            ->create('Customer organization', $customer->id);
        $this->actingAs($customer)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/team/mail')->assertForbidden();
    }

    public function test_disabled_preview_sender_rejects_without_email_or_audit(): void
    {
        Notification::fake();
        $owner = $this->owner();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/preview', ['kind' => 'owner_security'])
            ->assertSessionHasErrors('kind');

        Notification::assertNothingSent();
        $this->assertDatabaseMissing('operator_action_audits', [
            'actor_user_id' => $owner->id,
            'action' => 'workforce_mail_preview_requested',
        ]);
    }

    public function test_enabled_owner_preview_is_queued_only_to_self_not_client_selected_email(): void
    {
        Notification::fake();
        $owner = $this->owner();
        $stranger = User::factory()->create();
        $this->allowTestSending();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/preview', [
                'kind' => 'owner_security',
                'to' => $stranger->email,
                'recipient_id' => $stranger->id,
                'actionUrl' => 'https://evil.example/phishing',
                'message' => 'Do not send this content',
            ])
            ->assertRedirect('/operator/mail');

        Notification::assertSentTo($owner, WorkforceMailPreviewNotification::class);
        Notification::assertNotSentTo($stranger, WorkforceMailPreviewNotification::class);
        $this->assertDatabaseHas('operator_action_audits', [
            'actor_user_id' => $owner->id,
            'action' => 'workforce_mail_preview_requested',
            'outcome' => 'queued_not_delivered',
        ]);
    }

    public function test_team_cannot_send_owner_template_even_with_test_flag_enabled(): void
    {
        Notification::fake();
        $member = User::factory()->create();
        $owner = $this->owner();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/staff', ['target_user_id' => $member->id])
            ->assertRedirect('/operator/mail');
        $this->allowTestSending();

        $this->actingAs($member)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/team/mail/preview', ['kind' => 'owner_security'])
            ->assertSessionHasErrors('kind');
        Notification::assertNothingSent();
    }

    public function test_all_ten_mail_templates_render_html_and_text_without_external_links_or_secrets(): void
    {
        foreach (['owner', 'team'] as $audience) {
            foreach (WorkforceMailCatalog::forAudience($audience) as $template) {
                $notice = WorkforceMailCatalog::previewMessage($template['kind'], $audience, 'Asha');
                $html = view('emails.kmj-transactional', $notice->viewData)->render();
                $text = view('emails.kmj-transactional-text', $notice->viewData)->render();

                self::assertStringContainsString('kmj-email-lockup-dark.png', $html);
                self::assertStringContainsString('KMJ TECHNO', $html);
                self::assertStringContainsString('INNOVATE | BUILD | SCALE', $text);
                self::assertStringContainsString('TEST PREVIEW', $text);
                self::assertStringNotContainsString('evil.example', $html);
                self::assertStringNotContainsString('<script', $html);
                self::assertNull($notice->viewData['actionUrl']);
            }
        }

        $this->expectException(InvalidArgumentException::class);
        WorkforceMailCatalog::previewMessage('owner_security', 'team', 'Asha');
    }

    private function allowTestSending(): void
    {
        config()->set('services.kmj_workforce_mail.preview_enabled', true);
        config()->set('mail.default', 'sendmail');
        config()->set('mail.from.address', 'info@kmjtechno.com');
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
            'name' => 'Mail Center test owner passkey',
            'credential_id' => 'mail-center-owner-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $owner;
    }
}
