<?php

declare(strict_types=1);

namespace Tests\Feature\Mail;

use App\Models\User;
use App\Services\Mail\NativeInboundTextPilot;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Illuminate\Testing\TestResponse;
use Tests\TestCase;

final class NativeMailInboundPilotTest extends TestCase
{
    use RefreshDatabase;

    private const SECRET = '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef';

    private const RECIPIENT = 'mail-pilot@kmjtechno.com';

    private const SENDER = 'sender@example.net';

    private const MIME = "From: sender@example.net\r\nTo: mail-pilot@kmjtechno.com\r\nSubject: Pilot message\r\n\r\nPrivate message body.";

    public function test_default_disabled_and_invalid_signatures_never_store_mail(): void
    {
        $this->receive(self::MIME)->assertNotFound();
        $this->enablePilot();
        $this->receive(self::MIME, signature: str_repeat('0', 64))->assertUnauthorized();
        $this->receive(self::MIME, timestamp: now()->timestamp - 301)->assertUnauthorized();
        $this->receive(self::MIME, recipient: 'info@kmjtechno.com')->assertUnauthorized();
        $this->receive(str_repeat('x', 262145))->assertStatus(413);
        $this->assertDatabaseCount('kmj_mail_inbound_quarantine', 0);
        $this->assertDatabaseCount('kmj_mail_messages', 0);
    }

    public function test_signed_mail_is_encrypted_and_replays_do_not_duplicate_quarantine(): void
    {
        $owner = $this->enablePilot();
        $event = (string) Str::uuid();
        $this->receive(self::MIME, event: $event)
            ->assertCreated()->assertExactJson(['state' => 'quarantined']);
        $this->receive(self::MIME, event: $event)
            ->assertOk()->assertExactJson(['state' => 'duplicate']);
        $this->receive(self::MIME)
            ->assertOk()->assertExactJson(['state' => 'duplicate']);
        $this->receive(self::MIME.'changed', event: $event)->assertConflict();

        $this->assertDatabaseCount('kmj_mail_inbound_quarantine', 1);
        $this->assertDatabaseCount('kmj_mail_messages', 0);
        $row = DB::table('kmj_mail_inbound_quarantine')->first();
        $this->assertSame($owner->id, (int) $row->mailbox_user_id);
        $this->assertSame(self::MIME, Crypt::decryptString($row->encrypted_mime));
        $this->assertSame(self::SENDER, Crypt::decryptString($row->encrypted_envelope_sender));
        $this->assertStringNotContainsString('Private message body.', $row->encrypted_mime);
    }

    public function test_revoked_owner_cannot_receive_even_with_valid_signature(): void
    {
        $owner = $this->enablePilot();
        $owner->forceFill(['is_platform_owner' => false])->save();
        $this->receive(self::MIME)->assertForbidden();
        $this->assertDatabaseCount('kmj_mail_inbound_quarantine', 0);
    }

    public function test_text_publication_is_separate_and_preserves_real_external_sender(): void
    {
        $owner = $this->enablePilot();
        config(['kmj-mail-inbound.publish_text' => true]);
        $event = (string) Str::uuid();
        $this->receive(self::MIME, event: $event)->assertCreated();
        $this->receive(self::MIME, event: $event)->assertOk();
        $this->assertDatabaseCount('kmj_mail_inbound_quarantine', 1);
        $this->assertDatabaseCount('kmj_mail_messages', 0);
        $this->assertDatabaseCount('kmj_mail_external_inbox', 1);
        $this->assertDatabaseHas('kmj_mail_external_inbox', [
            'mailbox_user_id' => $owner->id,
            'sender_email' => self::SENDER,
            'recipient_email' => self::RECIPIENT,
            'read_at' => null,
            'body' => 'Private message body.',
        ]);
        $mail = app(NativeInboundTextPilot::class);
        $mailbox = $mail->inbox((int) $owner->id, self::SENDER, null);
        $this->assertSame(1, $mailbox['total']);
        $this->assertSame(1, $mailbox['unread']);
        $this->assertSame(self::SENDER, $mailbox['items'][0]['sender']);
        $other = User::factory()->create();
        $this->assertSame(0, $mail->inbox((int) $other->id, '', null)['total']);
        $selected = $mail->inbox((int) $owner->id, '', $mailbox['items'][0]['id']);
        $this->assertSame(0, $selected['unread']);
        $this->assertSame('Private message body.', $selected['selected']['body']);
        $this->actingAs($other)->get('/operator/mail?incoming='.$mailbox['items'][0]['id'])->assertForbidden();
    }

    public function test_unsupported_mime_and_spoofed_header_remain_quarantined(): void
    {
        $this->enablePilot();
        config(['kmj-mail-inbound.publish_text' => true]);
        $html = str_replace("Subject: Pilot message\r\n", "Subject: HTML\r\nContent-Type: text/html\r\n", self::MIME);
        $spoof = str_replace('From: sender@example.net', 'From: different@example.net', self::MIME);
        $multipart = str_replace("Subject: Pilot message\r\n", "Subject: Multipart\r\nContent-Type: multipart/mixed; boundary=abc\r\n", self::MIME);
        $attachment = str_replace("Subject: Pilot message\r\n", "Subject: Attachment\r\nContent-Disposition: attachment; filename=unsafe.txt\r\n", self::MIME);
        foreach ([$html, $spoof, $multipart, $attachment] as $raw) {
            $this->receive($raw)->assertCreated();
        }
        $this->assertDatabaseCount('kmj_mail_inbound_quarantine', 4);
        $this->assertDatabaseCount('kmj_mail_external_inbox', 0);
        $this->assertDatabaseCount('kmj_mail_messages', 0);
    }

    public function test_plain_text_pilot_decodes_bounded_transfer_encoding(): void
    {
        $this->enablePilot();
        config(['kmj-mail-inbound.publish_text' => true]);
        $raw = "From: Sender <sender@example.net>\r\nSubject: Encoded text\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n".base64_encode('Hello from outside.');
        $this->receive($raw)->assertCreated();
        $this->assertDatabaseHas('kmj_mail_external_inbox', [
            'sender_email' => self::SENDER,
            'subject' => 'Encoded text',
            'body' => 'Hello from outside.',
        ]);
    }

    private function enablePilot(): User
    {
        $owner = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        DB::table('passkeys')->insert([
            'user_id' => $owner->id,
            'name' => 'Inbound pilot test owner',
            'credential_id' => 'mail-inbound-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        config([
            'kmj-mail-inbound.enabled' => true,
            'kmj-mail-inbound.owner_id' => $owner->id,
            'kmj-mail-inbound.secret_hex' => self::SECRET,
        ]);

        return $owner;
    }

    private function receive(
        string $mime,
        ?string $event = null,
        ?int $timestamp = null,
        string $recipient = self::RECIPIENT,
        ?string $signature = null,
    ): TestResponse {
        $event ??= (string) Str::uuid();
        $timestamp ??= now()->timestamp;
        $signed = implode("\n", ['kmj-inbound-v1', $event, (string) $timestamp, $recipient, self::SENDER, hash('sha256', $mime)]);
        $signature ??= hash_hmac('sha256', $signed, hex2bin(self::SECRET));

        return $this->call('POST', '/api/kmj-mail/inbound/pilot', [], [], [], [
            'CONTENT_TYPE' => 'message/rfc822',
            'HTTP_ACCEPT' => 'application/json',
            'HTTP_X_KMJ_MAIL_EVENT' => $event,
            'HTTP_X_KMJ_MAIL_TIMESTAMP' => (string) $timestamp,
            'HTTP_X_KMJ_MAIL_RECIPIENT' => $recipient,
            'HTTP_X_KMJ_MAIL_ENVELOPE_FROM' => self::SENDER,
            'HTTP_X_KMJ_MAIL_SIGNATURE' => $signature,
        ], $mime);
    }
}
