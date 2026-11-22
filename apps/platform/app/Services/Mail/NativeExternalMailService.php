<?php

declare(strict_types=1);

namespace App\Services\Mail;

use App\Jobs\SubmitNativeExternalMail;
use App\Models\OperatorActionAudit;
use App\Models\User;
use App\Services\PlatformOwnerAccess;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Illuminate\Validation\ValidationException;

final class NativeExternalMailService
{
    public function __construct(
        private readonly NativeMailService $internal,
        private readonly PlatformOwnerAccess $owner,
        private readonly RegistrationMailReadiness $readiness,
    ) {}

    /**
     * An activated outbound sender must use the owner's real verified
     * organization identity, or a distinct owner-granted staff alias.
     * Do not permit a staff member to impersonate info@/support@.
     */
    public function senderAddress(User $user): ?string
    {
        if (! $this->internal->allowed($user) || ! $this->transportEnabled()) {
            return null;
        }

        if ($this->owner->allows($user)) {
            $from = strtolower(trim((string) config('mail.from.address', '')));

            return $this->validDomainAddress($from) ? $from : null;
        }

        $alias = DB::table('kmj_mail_staff')
            ->where('user_id', (int) $user->getKey())
            ->whereNull('revoked_at')->value('sender_alias');

        $alias = is_string($alias) ? strtolower(trim($alias)) : '';

        return $this->validDomainAddress($alias) && ! $this->reservedAlias($alias)
            ? $alias : null;
    }

    public function transportEnabled(): bool
    {
        // Native outbound is independent of transactional sendmail.
        // Previous production flag alone MUST NOT activate a new transport.
        // SMTP peer, port, timeout and unauthenticated transport are pinned,
        // so an env override cannot redirect owner/staff mail elsewhere.
        return config('services.kmj_native_external_mail.enabled', false) === true
            && config('services.kmj_native_external_mail.transport') === 'loopback_smtp'
            && config('mail.mailers.kmj_native_loopback.transport') === 'smtp'
            && config('mail.mailers.kmj_native_loopback.host') === '127.0.0.1'
            && config('mail.mailers.kmj_native_loopback.port') === 25
            && config('mail.mailers.kmj_native_loopback.scheme') === null
            && config('mail.mailers.kmj_native_loopback.username') === null
            && config('mail.mailers.kmj_native_loopback.password') === null
            && config('mail.mailers.kmj_native_loopback.timeout') === 8
            && config('mail.mailers.kmj_native_loopback.local_domain') === 'kmjtechno.com'
            && $this->readiness->canAttemptDelivery();
    }

    public function queue(
        User $sender,
        string $recipientEmail,
        string $subject,
        string $body,
        string $clientKey,
        ?int $replyToId = null,
    ): int {
        $from = $this->senderAddress($sender);
        if ($from === null) {
            throw ValidationException::withMessages(['recipient_email' => 'External sending is not activated for this KMJ mailbox.']);
        }

        $email = $this->normalizeRecipient($recipientEmail);
        $subject = trim($subject);
        $this->checkContent($subject, $body);

        return DB::transaction(function () use ($sender, $email, $subject, $body, $clientKey, $replyToId, $from): int {
            $id = (int) $sender->getKey();

            // Serialize concurrent idempotency checks and per-day quota for one sender.
            User::query()->whereKey($id)->lockForUpdate()->firstOrFail();

            $existing = DB::table('kmj_mail_messages')
                ->where('mailbox_user_id', $id)->where('client_key', $clientKey)->first();
            if ($existing !== null) {
                if ($existing->recipient_email !== $email || $existing->subject !== $subject
                    || $existing->body !== $body || $existing->sender_email !== $from) {
                    throw ValidationException::withMessages(['client_key' => 'This submission key is already used for another message.']);
                }

                return (int) $existing->id;
            }

            $this->enforceDailyQuota($sender);

            $thread = (string) Str::uuid();
            if ($replyToId !== null) {
                $anchor = DB::table('kmj_mail_messages')
                    ->where('mailbox_user_id', $id)->where('id', $replyToId)->first();
                abort_if($anchor === null, 404);
                abort_unless((string) $anchor->recipient_email === $email, 403);
                $thread = (string) $anchor->thread_id;
            }

            $now = now();
            $messageId = (int) DB::table('kmj_mail_messages')->insertGetId([
                'mailbox_user_id' => $id,
                'sender_user_id' => $id,
                'recipient_user_id' => null,
                'recipient_email' => $email,
                'sender_email' => $from,
                'thread_id' => $thread,
                'folder' => 'sent',
                'subject' => $subject,
                'body' => $body,
                'client_key' => $clientKey,
                'read_at' => $now,
                // queued for a delivery *attempt*; not yet an SMTP receipt.
                'delivery_state' => 'queued',
                'created_at' => $now,
                'updated_at' => $now,
            ]);
            $this->audit($id, 'kmj_mail_external_queued', $messageId);

            SubmitNativeExternalMail::dispatch($messageId)->afterCommit();

            return $messageId;
        });
    }

    public function saveDraft(
        User $user,
        ?int $draftId,
        ?string $recipientEmail,
        string $subject,
        string $body,
    ): int {
        abort_unless($this->internal->allowed($user), 403);

        $recipientEmail = $recipientEmail === null || trim($recipientEmail) === ''
            ? null : $this->normalizeRecipient($recipientEmail);

        return DB::transaction(function () use ($user, $draftId, $recipientEmail, $subject, $body): int {
            $userId = (int) $user->getKey();
            $now = now();

            if ($draftId !== null) {
                $updated = DB::table('kmj_mail_messages')
                    ->where('id', $draftId)
                    ->where('mailbox_user_id', $userId)
                    ->where('folder', 'drafts')
                    ->update([
                        'recipient_user_id' => null,
                        'recipient_email' => $recipientEmail,
                        'subject' => $subject,
                        'body' => $body,
                        'updated_at' => $now,
                    ]);
                abort_unless($updated === 1, 404);

                return $draftId;
            }

            return (int) DB::table('kmj_mail_messages')->insertGetId([
                'mailbox_user_id' => $userId,
                'sender_user_id' => $userId,
                'recipient_user_id' => null,
                'recipient_email' => $recipientEmail,
                'thread_id' => (string) Str::uuid(),
                'folder' => 'drafts',
                'subject' => $subject,
                'body' => $body,
                'created_at' => $now,
                'updated_at' => $now,
            ]);
        });
    }

    public function isExternalDraft(User $user, int $messageId): bool
    {
        abort_unless($this->internal->allowed($user), 403);
        $row = DB::table('kmj_mail_messages')
            ->where('mailbox_user_id', (int) $user->getKey())->where('id', $messageId)
            ->first(['recipient_email', 'folder']);
        abort_if($row === null, 404);

        return $row->recipient_email !== null;
    }

    public function sendDraft(User $sender, int $messageId): int
    {
        abort_unless($this->internal->allowed($sender), 403);
        $from = $this->senderAddress($sender);
        if ($from === null) {
            throw ValidationException::withMessages(['recipient_email' => 'External sending is not activated for this KMJ mailbox.']);
        }

        return DB::transaction(function () use ($sender, $messageId, $from): int {
            $userId = (int) $sender->getKey();
            User::query()->whereKey($userId)->lockForUpdate()->firstOrFail();
            $row = DB::table('kmj_mail_messages')
                ->where('mailbox_user_id', $userId)->where('id', $messageId)
                ->lockForUpdate()->first();
            abort_if($row === null, 404);
            if ($row->folder === 'sent' && $row->recipient_email !== null) {
                return $messageId;
            }

            abort_unless($row->folder === 'drafts' && $row->recipient_email !== null, 409);
            $email = $this->normalizeRecipient((string) $row->recipient_email);
            $this->checkContent((string) $row->subject, (string) $row->body);
            $this->enforceDailyQuota($sender);

            $now = now();
            DB::table('kmj_mail_messages')->where('id', $messageId)
                ->where('mailbox_user_id', $userId)
                ->update([
                    'folder' => 'sent',
                    'sender_email' => $from,
                    'delivery_state' => 'queued',
                    'read_at' => $now,
                    'updated_at' => $now,
                ]);

            $this->audit($userId, 'kmj_mail_external_queued', $messageId);
            SubmitNativeExternalMail::dispatch($messageId)->afterCommit();

            return $messageId;
        });
    }

    /** @return array{state:string,from:?string} */
    public function capability(User $user): array
    {
        $from = $this->senderAddress($user);

        return [
            'state' => $from === null ? 'not_activated' : 'ready_to_queue',
            'from' => $from,
        ];
    }

    public function senderStillAuthorized(User $user, string $from): bool
    {
        return $this->senderAddress($user) === $from;
    }

    public function grantStaffAlias(User $owner, int $staffId, ?string $alias): void
    {
        abort_unless($this->owner->allows($owner), 403);

        $alias = $alias !== null ? strtolower(trim($alias)) : null;
        if ($alias !== null && (! $this->validDomainAddress($alias) || $this->reservedAlias($alias))) {
            throw ValidationException::withMessages(['sender_alias' => 'Use a unique KMJ domain staff address, not a reserved shared mailbox.']);
        }

        DB::transaction(function () use ($owner, $staffId, $alias): void {
            $staff = DB::table('kmj_mail_staff')
                ->where('user_id', $staffId)->whereNull('revoked_at')
                ->lockForUpdate()->first();
            abort_if($staff === null, 404);

            if ($alias !== null) {
                $taken = DB::table('kmj_mail_staff')
                    ->where('sender_alias', $alias)->where('user_id', '!=', $staffId)
                    ->exists();
                if ($taken) {
                    throw ValidationException::withMessages(['sender_alias' => 'This KMJ sender alias is already assigned.']);
                }
            }

            DB::table('kmj_mail_staff')->where('user_id', $staffId)
                ->update(['sender_alias' => $alias, 'updated_at' => now()]);
            OperatorActionAudit::query()->create([
                'actor_user_id' => (int) $owner->getKey(),
                'action' => 'kmj_mail_staff_sender_alias',
                'outcome' => 'committed',
                'metadata' => ['user_id' => $staffId, 'assigned' => $alias !== null],
            ]);
        });
    }

    private function validDomainAddress(string $email): bool
    {
        return filter_var($email, FILTER_VALIDATE_EMAIL) !== false
            && strlen($email) <= 254
            && str_ends_with($email, '@kmjtechno.com')
            && preg_match('/[\x00-\x20\x7F]/', $email) !== 1;
    }

    private function reservedAlias(string $email): bool
    {
        return in_array($email, [
            'info@kmjtechno.com', 'admin@kmjtechno.com',
            'security@kmjtechno.com', 'support@kmjtechno.com',
            'billing@kmjtechno.com', 'no-reply@kmjtechno.com',
            'postmaster@kmjtechno.com', 'abuse@kmjtechno.com',
        ], true);
    }

    public function normalizeRecipient(string $raw): string
    {
        $email = strtolower(trim($raw));
        if (strlen($email) > 254 || filter_var($email, FILTER_VALIDATE_EMAIL) === false
            || preg_match('/[\x00-\x20\x7F]/', $email) === 1) {
            throw ValidationException::withMessages(['recipient_email' => 'Enter one valid email address without display names or separators.']);
        }

        return $email;
    }

    private function checkContent(string $subject, string $body): void
    {
        if ($subject === '' || $body === '' || preg_match('/[\x00-\x1F\x7F]/', $subject) === 1) {
            throw ValidationException::withMessages(['subject' => 'A non-empty single-line subject and message are required.']);
        }
    }

    private function enforceDailyQuota(User $user): void
    {
        $limit = $this->owner->allows($user) ? 20 : 5;
        $used = DB::table('kmj_mail_messages')
            ->where('mailbox_user_id', (int) $user->getKey())
            ->whereNotNull('recipient_email')
            ->whereNotNull('delivery_state')
            ->where('created_at', '>=', now()->startOfDay())
            ->count();

        if ($used >= $limit) {
            throw ValidationException::withMessages(['recipient_email' => 'Daily external send limit reached for this mailbox.']);
        }
    }

    private function audit(int $actorId, string $action, int $messageId): void
    {
        OperatorActionAudit::query()->create([
            'actor_user_id' => $actorId,
            'action' => $action,
            'outcome' => 'queued',
            'metadata' => ['message_id' => $messageId],
        ]);
    }
}
