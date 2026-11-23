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

    public function test_empty_inbox_displays_only_own_real_sent_previews_without_changing_inbox_counts(): void
    {
        Mail::fake();
        Notification::fake();
        [$owner, $staff] = $this->ownerAndStaff();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/send', [
                'recipient_id' => $staff->id,
                'subject' => 'Actual private progress update',
                'body' => 'Real correspondence visible only to the authorized sender.',
                'client_key' => (string) Str::uuid(),
            ])->assertRedirect('/operator/mail?folder=sent');

        $this->actingAs($owner)->get('/operator/mail')
            ->assertOk()->assertInertia(fn (Assert $page) => $page
            ->where('folder', 'inbox')
            ->where('mailbox.total', 0)
            ->has('mailbox.items', 0)
            ->where('recentSent.total', 1)
            ->has('recentSent.items', 1)
            ->where('recentSent.items.0.subject', 'Actual private progress update'));

        $this->actingAs($owner)->get('/operator/mail?q=missing')
            ->assertOk()->assertInertia(fn (Assert $page) => $page
            ->where('mailbox.total', 0)
            ->where('recentSent', null));

        $this->actingAs($owner)->get('/operator/mail?folder=sent')
            ->assertOk()->assertInertia(fn (Assert $page) => $page
            ->where('mailbox.total', 1)
            ->where('recentSent', null));

        $this->actingAs($staff)->get('/team/mail')
            ->assertOk()->assertInertia(fn (Assert $page) => $page
            ->where('mailbox.total', 1)
            ->where('recentSent', null));
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

    public function test_private_star_archive_read_and_restore_are_not_visible_to_other_mailboxes(): void
    {
        [$owner, $staff] = $this->ownerAndStaff();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/send', [
                'recipient_id' => $staff->id,
                'subject' => 'Review request',
                'body' => 'Please review the document.',
                'client_key' => (string) Str::uuid(),
            ]);

        $inbox = DB::table('kmj_mail_messages')->where('mailbox_user_id', $staff->id)->first();
        $sent = DB::table('kmj_mail_messages')->where('mailbox_user_id', $owner->id)->first();
        $url = '/team/mail/messages/manage';
        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->post($url, ['ids' => [$sent->id], 'action' => 'star', 'folder' => 'inbox'])
            ->assertNotFound();

        foreach (['star', 'archive', 'unread'] as $action) {
            $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
                ->post($url, ['ids' => [$inbox->id], 'action' => $action, 'folder' => 'inbox'])
                ->assertRedirect('/team/mail?folder=inbox');
        }

        $this->assertDatabaseHas('kmj_mail_messages', [
            'id' => $inbox->id, 'mailbox_user_id' => $staff->id,
            'folder' => 'archive', 'is_starred' => true, 'read_at' => null,
        ]);
        $this->assertDatabaseHas('kmj_mail_messages', [
            'id' => $sent->id, 'mailbox_user_id' => $owner->id,
            'folder' => 'sent', 'is_starred' => false,
        ]);

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/team/mail?folder=archive&message='.$inbox->id)->assertOk();
        $this->assertNotNull(DB::table('kmj_mail_messages')->where('id', $inbox->id)->value('read_at'));

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/team/mail?folder=starred')->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->has('mailbox.items', 1)
                ->where('mailbox.items.0.starred', true));
        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->post($url, ['ids' => [$inbox->id], 'action' => 'trash', 'folder' => 'archive'])
            ->assertRedirect('/team/mail?folder=archive');
        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->post($url, ['ids' => [$inbox->id], 'action' => 'restore', 'folder' => 'trash'])
            ->assertRedirect('/team/mail?folder=trash');
        $this->assertDatabaseHas('kmj_mail_messages', ['id' => $inbox->id, 'folder' => 'archive']);
    }

    public function test_bulk_mail_management_is_atomic_with_owner_scope_and_rejects_invalid_actions(): void
    {
        [$owner, $staff] = $this->ownerAndStaff();
        for ($i = 1; $i <= 2; $i++) {
            $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
                ->post('/operator/mail/send', [
                    'recipient_id' => $staff->id, 'subject' => 'Update '.$i,
                    'body' => 'Note '.$i, 'client_key' => (string) Str::uuid(),
                ]);
        }
        $ids = DB::table('kmj_mail_messages')->where('mailbox_user_id', $staff->id)
            ->orderBy('id')->pluck('id')->map(static fn ($id) => (int) $id)->all();
        $foreignId = (int) DB::table('kmj_mail_messages')
            ->where('mailbox_user_id', $owner->id)->value('id');

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/team/mail/messages/manage', [
                'ids' => [$ids[0], $foreignId], 'action' => 'trash',
            ])->assertNotFound();
        $this->assertSame(2, DB::table('kmj_mail_messages')
            ->where('mailbox_user_id', $staff->id)->where('folder', 'inbox')->count());

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/team/mail/messages/manage', [
                'ids' => $ids, 'action' => 'star', 'folder' => 'inbox',
            ])->assertRedirect('/team/mail?folder=inbox');
        $this->assertSame(2, DB::table('kmj_mail_messages')
            ->where('mailbox_user_id', $staff->id)->where('is_starred', true)->count());

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/team/mail/messages/manage', [
                'ids' => [$ids[0], $ids[0]], 'action' => 'trash',
            ])->assertSessionHasErrors('ids.1');
        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/team/mail/messages/manage', [
                'ids' => $ids, 'action' => 'send',
            ])->assertSessionHasErrors('action');
    }

    public function test_mailbox_pagination_never_fetches_more_than_forty_private_messages(): void
    {
        [$owner, $staff] = $this->ownerAndStaff();
        $now = now();
        for ($i = 1; $i <= 45; $i++) {
            DB::table('kmj_mail_messages')->insert([
                'mailbox_user_id' => $staff->id,
                'sender_user_id' => $owner->id,
                'recipient_user_id' => $staff->id,
                'thread_id' => (string) Str::uuid(),
                'folder' => 'inbox',
                'subject' => 'Private note '.$i,
                'body' => 'Internal only',
                'created_at' => $now,
                'updated_at' => $now,
            ]);
        }

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/team/mail?folder=inbox')->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->has('mailbox.items', 40)
                ->where('mailbox.total', 45)
                ->where('mailbox.page', 1)
                ->where('mailbox.has_more', true));
        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/team/mail?folder=inbox&page=2')->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->has('mailbox.items', 5)
                ->where('mailbox.total', 45)
                ->where('mailbox.page', 2)
                ->where('mailbox.has_more', false));
        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/team/mail?folder=inbox&page=1001')->assertSessionHasErrors('page');
    }

    public function test_approved_dashboard_metrics_are_real_and_scoped_to_each_private_mailbox(): void
    {
        Mail::fake();
        [$owner, $staff] = $this->ownerAndStaff();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/mail/send', [
                'recipient_id' => $staff->id,
                'subject' => 'CodeBridge delivery update',
                'body' => 'Only the owner and staff copies can be read.',
                'client_key' => (string) Str::uuid(),
            ])->assertRedirect('/operator/mail?folder=sent');

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/mail?folder=sent')->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('mailMetrics.total_messages', 1)
                ->where('mailMetrics.unread', 0)
                ->where('mailMetrics.mail_text_bytes', strlen('CodeBridge delivery update') + strlen('Only the owner and staff copies can be read.')));

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/team/mail')->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('mailMetrics.total_messages', 1)
                ->where('mailMetrics.unread', 1));

        $staffMessage = (int) DB::table('kmj_mail_messages')
            ->where('mailbox_user_id', $staff->id)->value('id');

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/team/mail/messages/manage', [
                'ids' => [$staffMessage],
                'action' => 'trash',
                'folder' => 'inbox',
            ])->assertRedirect();

        $this->actingAs($staff)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/team/mail')->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('mailMetrics.total_messages', 0)
                ->where('mailMetrics.unread', 0)
                ->where('mailMetrics.mail_text_bytes', 0));

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/mail?folder=sent')->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('mailMetrics.total_messages', 1));
        Mail::assertNothingOutgoing();
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
