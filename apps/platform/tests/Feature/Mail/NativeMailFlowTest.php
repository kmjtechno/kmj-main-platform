<?php

declare(strict_types=1);

namespace Tests\Feature\Mail;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Mail;
use Illuminate\Support\Facades\Notification;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class NativeMailFlowTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_owner_can_grant_and_revoke_verified_staff_without_customer_membership(): void
    {
        $owner = $this->owner();
        $staff = User::factory()->create(['email_verified_at' => now()]);
        $unverified = User::factory()->unverified()->create();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/staff', ['target_user_id' => $unverified->id])
            ->assertNotFound();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/staff', ['target_user_id' => $staff->id])
            ->assertRedirect('/operator/mail');
        $this->assertDatabaseHas('kmj_mail_staff', [
            'user_id' => $staff->id,
            'granted_by_user_id' => $owner->id,
            'revoked_at' => null,
        ]);

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/team/mail')->assertOk();

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/staff', ['target_user_id' => $unverified->id])
            ->assertForbidden();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/staff/'.$staff->id.'/revoke')
            ->assertRedirect('/operator/mail');

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/team/mail')->assertForbidden();
    }

    public function test_internal_send_creates_private_sent_and_inbox_copies_once_without_smtp(): void
    {
        Mail::fake();
        Notification::fake();
        [$owner, $staff] = $this->ownerAndStaff();
        $token = (string) Str::uuid();
        $payload = [
            'recipient_id' => $staff->id,
            'subject' => 'Weekly service handoff',
            'body' => "Hello colleague,\nHere is the status.",
            'client_key' => $token,
        ];

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/send', $payload)
            ->assertRedirect('/operator/mail?folder=sent');
        // The same client idempotency token must not send another copy.
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/send', $payload)
            ->assertRedirect('/operator/mail?folder=sent');

        $this->assertDatabaseCount('kmj_mail_messages', 2);
        $this->assertDatabaseHas('kmj_mail_messages', [
            'mailbox_user_id' => $owner->id, 'sender_user_id' => $owner->id,
            'recipient_user_id' => $staff->id, 'folder' => 'sent',
        ]);
        $this->assertDatabaseHas('kmj_mail_messages', [
            'mailbox_user_id' => $staff->id, 'sender_user_id' => $owner->id,
            'recipient_user_id' => $staff->id, 'folder' => 'inbox', 'read_at' => null,
        ]);

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/team/mail')->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('mailbox.unread', 1)
                ->has('mailbox.items', 1)
                ->where('mailbox.items.0.subject', 'Weekly service handoff'));

        Mail::assertNothingOutgoing();
        Notification::assertNothingSent();
    }

    public function test_reading_thread_marks_only_own_mailbox_read_and_rejects_others(): void
    {
        [$owner, $staff] = $this->ownerAndStaff();
        $outsider = User::factory()->create();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/send', [
                'recipient_id' => $staff->id, 'subject' => 'Private',
                'body' => 'Workspace handoff', 'client_key' => (string) Str::uuid(),
            ]);
        $inbox = DB::table('kmj_mail_messages')->where('mailbox_user_id', $staff->id)->first();
        $sent = DB::table('kmj_mail_messages')->where('mailbox_user_id', $owner->id)->first();

        $this->actingAs($outsider)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/team/mail?message='.$inbox->id)->assertForbidden();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/mail?message='.$inbox->id)->assertNotFound();
        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/team/mail?message='.$sent->id)->assertNotFound();

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/team/mail?message='.$inbox->id)
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->has('selectedThread.items', 1)
                ->where('selectedThread.items.0.body', 'Workspace handoff')
                ->where('mailbox.unread', 0));

        $this->assertDatabaseHas('kmj_mail_messages', [
            'id' => $sent->id, 'folder' => 'sent',
        ]);
    }

    public function test_team_can_reply_within_existing_thread_but_cannot_fake_other_conversation(): void
    {
        [$owner, $staff] = $this->ownerAndStaff();
        $other = User::factory()->create();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/staff', ['target_user_id' => $other->id]);
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/send', [
                'recipient_id' => $staff->id, 'subject' => 'Work item',
                'body' => 'Please confirm.', 'client_key' => (string) Str::uuid(),
            ]);
        $inbox = DB::table('kmj_mail_messages')->where('mailbox_user_id', $staff->id)->first();
        $wrong = [
            'recipient_id' => $other->id, 'subject' => 'Re: Work item',
            'body' => 'Wrong recipient', 'client_key' => (string) Str::uuid(),
            'reply_to_id' => $inbox->id,
        ];

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/team/mail/send', $wrong)->assertForbidden();

        $wrong['recipient_id'] = $owner->id;
        $wrong['client_key'] = (string) Str::uuid();
        $wrong['body'] = 'Confirmed, thank you.';
        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/team/mail/send', $wrong)->assertRedirect('/team/mail?folder=sent');

        $this->assertSame(4, DB::table('kmj_mail_messages')->count());
        $this->assertSame(1, DB::table('kmj_mail_messages')->distinct()->count('thread_id'));
    }

    public function test_draft_save_edit_and_repeat_send_has_one_recipient_copy(): void
    {
        [$owner, $staff] = $this->ownerAndStaff();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/drafts', ['subject' => '', 'body' => ''])
            ->assertRedirect('/operator/mail?folder=drafts');

        $draft = DB::table('kmj_mail_messages')->where('mailbox_user_id', $owner->id)->first();
        $this->assertSame('drafts', $draft->folder);

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/drafts', [
                'draft_id' => $draft->id,
                'recipient_id' => $staff->id,
                'subject' => 'Approved update',
                'body' => 'Status has changed.',
            ])->assertRedirect('/operator/mail?folder=drafts');

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/drafts/'.$draft->id.'/send')->assertRedirect('/operator/mail?folder=sent');
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/drafts/'.$draft->id.'/send')->assertRedirect('/operator/mail?folder=sent');

        $this->assertDatabaseCount('kmj_mail_messages', 2);
        $this->assertDatabaseHas('kmj_mail_messages', [
            'id' => $draft->id, 'folder' => 'sent', 'subject' => 'Approved update',
        ]);
    }

    public function test_trash_and_restore_only_mutate_the_current_mailbox_copy(): void
    {
        [$owner, $staff] = $this->ownerAndStaff();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/send', [
                'recipient_id' => $staff->id, 'subject' => 'Message',
                'body' => 'Body', 'client_key' => (string) Str::uuid(),
            ]);
        $sent = DB::table('kmj_mail_messages')->where('mailbox_user_id', $owner->id)->first();
        $inbox = DB::table('kmj_mail_messages')->where('mailbox_user_id', $staff->id)->first();

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/team/mail/messages/'.$sent->id.'/trash')->assertNotFound();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/messages/'.$sent->id.'/trash')->assertRedirect('/operator/mail?folder=trash');
        $this->assertDatabaseHas('kmj_mail_messages', ['id' => $inbox->id, 'folder' => 'inbox']);
        $this->assertDatabaseHas('kmj_mail_messages', ['id' => $sent->id, 'folder' => 'trash']);

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/messages/'.$sent->id.'/restore')->assertRedirect('/operator/mail');
        $this->assertDatabaseHas('kmj_mail_messages', ['id' => $sent->id, 'folder' => 'sent']);
    }

    public function test_nonstaff_customer_cannot_send_and_user_selected_external_recipient_is_rejected(): void
    {
        [$owner, $staff] = $this->ownerAndStaff();
        $outsider = User::factory()->create();

        $this->actingAs($outsider)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/team/mail/send', [
                'recipient_id' => $owner->id, 'subject' => 'No',
                'body' => 'Do not permit.', 'client_key' => (string) Str::uuid(),
            ])->assertForbidden();

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/team/mail/send', [
                'recipient_id' => $outsider->id,
                'to' => 'outsider@example.com',
                'subject' => 'No',
                'body' => 'Cannot deliver to outsider.',
                'client_key' => (string) Str::uuid(),
            ])->assertStatus(422);
        $this->assertDatabaseCount('kmj_mail_messages', 0);
    }

    /** @return array{User, User} */
    private function ownerAndStaff(): array
    {
        $owner = $this->owner();
        $staff = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/staff', ['target_user_id' => $staff->id])
            ->assertRedirect('/operator/mail');

        return [$owner, $staff];
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
            'name' => 'Native Mail test owner passkey',
            'credential_id' => 'mail-native-owner-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $owner;
    }
}
