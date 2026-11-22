<?php

declare(strict_types=1);

namespace App\Jobs;

use App\Mail\NativeExternalMailMessage;
use App\Models\OperatorActionAudit;
use App\Models\User;
use App\Services\Mail\NativeExternalMailService;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Mail;
use Throwable;

/**
 * Submit a single, owner-authorized outbound email to local Elite Postfix.
 *
 * No automatic retry after the transport attempt begins: if PHP dies after
 * Postfix accepts but before our status update, the state remains
 * "submitting" (unknown) rather than sending a duplicate.
 */
final class SubmitNativeExternalMail implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $tries = 1;

    public int $timeout = 30;

    public function __construct(public readonly int $messageId) {}

    public function handle(NativeExternalMailService $policy): void
    {
        $message = DB::table('kmj_mail_messages')
            ->where('id', $this->messageId)
            ->where('folder', 'sent')
            ->where('delivery_state', 'queued')
            ->whereNotNull('recipient_email')
            ->first();

        if ($message === null) {
            return;
        }

        $actor = User::query()->whereKey((int) $message->sender_user_id)->first();
        if (! $actor instanceof User
            || ! is_string($message->sender_email)
            || ! $policy->senderStillAuthorized($actor, $message->sender_email)) {
            $this->transition('queued', 'blocked', 'authorization_lost');

            return;
        }

        // One worker claims this message, preventing competing queue jobs from
        // sending twice. A crash after this point needs manual reconciliation.
        $claimed = DB::table('kmj_mail_messages')
            ->where('id', $this->messageId)->where('delivery_state', 'queued')
            ->update([
                'delivery_state' => 'submitting',
                'transport_attempted_at' => now(),
                'updated_at' => now(),
            ]);
        if ($claimed !== 1) {
            return;
        }

        try {
            // Only the pinned, bounded, owner-activated local Postfix SMTP
            // transport; never fork sendmail/postdrop in a sandboxed worker.
            // This is NOT a remote provider or the transactional mailer.
            Mail::mailer('kmj_native_loopback')->to((string) $message->recipient_email)
                ->send(new NativeExternalMailMessage(
                    (string) $message->subject,
                    (string) $message->body,
                    (string) $message->sender_email,
                ));

            // This means local mail-server acceptance, NOT recipient delivery.
            DB::table('kmj_mail_messages')->where('id', $this->messageId)
                ->where('delivery_state', 'submitting')
                ->update([
                    'delivery_state' => 'mta_accepted',
                    'transport_accepted_at' => now(),
                    'updated_at' => now(),
                ]);
            $this->audit((int) $message->sender_user_id, 'kmj_mail_mta_accepted', 'accepted');
        } catch (Throwable) {
            // Do not put SMTP exception text, recipient address or message body
            // into a user-visible error, audit row or job log.
            $this->transition('submitting', 'failed', 'transport_error');
            $this->audit((int) $message->sender_user_id, 'kmj_mail_transport_failed', 'failed');
        }
    }

    private function transition(string $from, string $to, string $reason): void
    {
        DB::table('kmj_mail_messages')->where('id', $this->messageId)
            ->where('delivery_state', $from)
            ->update([
                'delivery_state' => $to,
                'delivery_error_code' => $reason,
                'updated_at' => now(),
            ]);
    }

    private function audit(int $userId, string $action, string $outcome): void
    {
        OperatorActionAudit::query()->create([
            'actor_user_id' => $userId,
            'action' => $action,
            'outcome' => $outcome,
            'metadata' => ['message_id' => $this->messageId],
        ]);
    }
}
