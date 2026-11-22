<?php

declare(strict_types=1);

namespace App\Services\Mail;

use App\Models\OperatorActionAudit;
use App\Models\User;
use App\Services\PlatformOwnerAccess;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Illuminate\Validation\ValidationException;

final class NativeMailService
{
    public function __construct(private readonly PlatformOwnerAccess $ownerAccess) {}

    public function staffAllowed(User $user): bool
    {
        return $user->hasVerifiedEmail()
            && DB::table('kmj_mail_staff')
                ->where('user_id', (int) $user->getKey())
                ->whereNull('revoked_at')->exists();
    }

    public function allowed(User $user): bool
    {
        return $this->ownerAccess->allows($user) || $this->staffAllowed($user);
    }

    /**
     * Only verified, currently authorized KMJ owner/staff accounts can exchange
     * local workspace mail. No external email addresses are accepted.
     *
     * @return list<array{id:int,name:string,role:string}>
     */
    public function directory(): array
    {
        $users = User::query()->whereNotNull('email_verified_at')
            ->where(function ($query): void {
                $query->whereHas('passkeys', static fn ($sub) => $sub->whereNotNull('id'))
                    ->where('is_platform_owner', true)
                    ->orWhereIn('id', DB::table('kmj_mail_staff')
                        ->select('user_id')->whereNull('revoked_at'));
            })
            ->orderBy('name')->limit(100)->get(['id', 'name', 'email_verified_at', 'is_platform_owner']);

        return array_values($users->filter(fn (User $user): bool => $this->allowed($user))
            ->map(fn (User $user): array => [
                'id' => (int) $user->getKey(),
                'name' => (string) $user->name,
                'role' => $this->ownerAccess->allows($user) ? 'owner' : 'staff',
            ])->values()->all());
    }

    /** @return array{items:array<int,array<string,mixed>>,unread:int} */
    public function mailbox(User $user, string $folder, string $search = ''): array
    {
        $this->requireAllowed($user);
        if (! in_array($folder, ['inbox', 'sent', 'drafts', 'trash'], true)) {
            throw ValidationException::withMessages(['folder' => 'Unknown mailbox folder.']);
        }

        $query = DB::table('kmj_mail_messages')
            ->where('mailbox_user_id', (int) $user->getKey())
            ->where('folder', $folder);

        if ($search !== '') {
            $query->where(function ($builder) use ($search): void {
                $escaped = addcslashes($search, '%_\\');
                $builder->where('subject', 'like', '%'.$escaped.'%')
                    ->orWhere('body', 'like', '%'.$escaped.'%');
            });
        }

        $page = $query->orderByDesc('id')->limit(40)
            ->get(['id', 'thread_id', 'folder', 'subject', 'body', 'sender_user_id',
                'recipient_user_id', 'read_at', 'sent_at', 'created_at']);

        $items = $page->map(static fn (object $row): array => [
            'id' => (int) $row->id,
            'thread_id' => (string) $row->thread_id,
            'folder' => (string) $row->folder,
            'subject' => (string) $row->subject,
            'snippet' => mb_strimwidth((string) $row->body, 0, 160, '…'),
            'sender_user_id' => (int) $row->sender_user_id,
            'recipient_user_id' => $row->recipient_user_id === null ? null : (int) $row->recipient_user_id,
            'unread' => $row->read_at === null && $row->folder === 'inbox',
            'at' => (string) ($row->sent_at ?? $row->created_at),
        ])->all();

        $unread = DB::table('kmj_mail_messages')
            ->where('mailbox_user_id', (int) $user->getKey())
            ->where('folder', 'inbox')->whereNull('read_at')->count();

        return ['items' => array_values($items), 'unread' => $unread];
    }

    /** @return array{items:list<array<string,mixed>>,thread_id:string} */
    public function thread(User $user, int $messageId): array
    {
        $this->requireAllowed($user);
        $anchor = DB::table('kmj_mail_messages')
            ->where('mailbox_user_id', (int) $user->getKey())->where('id', $messageId)->first();
        abort_if($anchor === null, 404);

        $rows = DB::table('kmj_mail_messages')
            ->where('mailbox_user_id', (int) $user->getKey())
            ->where('thread_id', (string) $anchor->thread_id)
            ->orderBy('id')->limit(100)
            ->get(['id', 'sender_user_id', 'recipient_user_id', 'folder',
                'subject', 'body', 'sent_at', 'created_at']);

        DB::table('kmj_mail_messages')
            ->where('mailbox_user_id', (int) $user->getKey())
            ->where('thread_id', (string) $anchor->thread_id)
            ->where('folder', 'inbox')->whereNull('read_at')
            ->update(['read_at' => now(), 'updated_at' => now()]);

        return [
            'thread_id' => (string) $anchor->thread_id,
            'items' => array_values($rows->map(static fn (object $row): array => [
                'id' => (int) $row->id,
                'from_id' => (int) $row->sender_user_id,
                'to_id' => $row->recipient_user_id === null ? null : (int) $row->recipient_user_id,
                'folder' => (string) $row->folder,
                'subject' => (string) $row->subject,
                'body' => (string) $row->body,
                'at' => (string) ($row->sent_at ?? $row->created_at),
            ])->values()->all()),
        ];
    }

    public function saveDraft(User $user, ?int $draftId, ?int $recipientId, string $subject, string $body): int
    {
        $this->requireAllowed($user);
        if ($recipientId !== null) {
            $this->validRecipient($recipientId);
        }

        return DB::transaction(function () use ($user, $draftId, $recipientId, $subject, $body): int {
            $now = now();
            if ($draftId !== null) {
                $updated = DB::table('kmj_mail_messages')
                    ->where('id', $draftId)->where('mailbox_user_id', (int) $user->getKey())
                    ->where('folder', 'drafts')
                    ->update(['recipient_user_id' => $recipientId,
                        'subject' => $subject, 'body' => $body, 'updated_at' => $now]);
                abort_unless($updated === 1, 404);

                return $draftId;
            }

            return (int) DB::table('kmj_mail_messages')->insertGetId([
                'mailbox_user_id' => (int) $user->getKey(),
                'sender_user_id' => (int) $user->getKey(),
                'recipient_user_id' => $recipientId,
                'thread_id' => (string) Str::uuid(),
                'folder' => 'drafts',
                'subject' => $subject,
                'body' => $body,
                'client_key' => null,
                'created_at' => $now,
                'updated_at' => $now,
            ]);
        });
    }

    public function send(User $sender, int $recipientId, string $subject, string $body, string $clientKey, ?int $replyToId = null): int
    {
        $this->requireAllowed($sender);
        $this->validRecipient($recipientId);

        return DB::transaction(function () use ($sender, $recipientId, $subject, $body, $clientKey, $replyToId): int {
            $senderId = (int) $sender->getKey();
            $existing = DB::table('kmj_mail_messages')
                ->where('mailbox_user_id', $senderId)->where('client_key', $clientKey)->first(['id']);
            if ($existing !== null) {
                return (int) $existing->id;
            }

            $thread = (string) Str::uuid();
            if ($replyToId !== null) {
                $anchor = DB::table('kmj_mail_messages')
                    ->where('mailbox_user_id', $senderId)->where('id', $replyToId)->first();
                abort_if($anchor === null, 404);
                abort_unless(
                    (int) $anchor->sender_user_id === $recipientId
                    || (int) $anchor->recipient_user_id === $recipientId,
                    403,
                );
                $thread = (string) $anchor->thread_id;
            }

            $now = now();
            $data = [
                'sender_user_id' => $senderId,
                'recipient_user_id' => $recipientId,
                'thread_id' => $thread,
                'subject' => $subject,
                'body' => $body,
                'sent_at' => $now,
                'created_at' => $now,
                'updated_at' => $now,
            ];

            $sentId = (int) DB::table('kmj_mail_messages')->insertGetId($data + [
                'mailbox_user_id' => $senderId,
                'folder' => 'sent',
                'read_at' => $now,
                'client_key' => $clientKey,
            ]);

            DB::table('kmj_mail_messages')->insert($data + [
                'mailbox_user_id' => $recipientId,
                'folder' => 'inbox',
                'client_key' => null,
                'read_at' => null,
            ]);

            $this->audit($senderId, 'kmj_mail_internal_sent', ['message_id' => $sentId]);

            return $sentId;
        });
    }

    public function sendDraft(User $sender, int $draftId): int
    {
        $this->requireAllowed($sender);

        return DB::transaction(function () use ($sender, $draftId): int {
            $senderId = (int) $sender->getKey();
            $draft = DB::table('kmj_mail_messages')
                ->where('mailbox_user_id', $senderId)
                ->where('id', $draftId)->lockForUpdate()->first();
            abort_if($draft === null, 404);
            if ($draft->folder === 'sent') {
                return $draftId; // Idempotent retry: never duplicate inbox delivery.
            }
            abort_unless($draft->folder === 'drafts', 409);
            abort_if($draft->recipient_user_id === null, 422);
            $recipientId = (int) $draft->recipient_user_id;
            $this->validRecipient($recipientId);
            abort_if(trim((string) $draft->subject) === '' || trim((string) $draft->body) === '', 422);

            $now = now();
            DB::table('kmj_mail_messages')->where('id', $draftId)
                ->where('mailbox_user_id', $senderId)
                ->update(['folder' => 'sent', 'read_at' => $now,
                    'sent_at' => $now, 'updated_at' => $now]);

            DB::table('kmj_mail_messages')->insert([
                'mailbox_user_id' => $recipientId,
                'sender_user_id' => $senderId,
                'recipient_user_id' => $recipientId,
                'thread_id' => $draft->thread_id,
                'folder' => 'inbox',
                'subject' => $draft->subject,
                'body' => $draft->body,
                'created_at' => $now,
                'updated_at' => $now,
                'sent_at' => $now,
            ]);
            $this->audit($senderId, 'kmj_mail_internal_sent', ['message_id' => $draftId]);

            return $draftId;
        });
    }

    public function moveToTrash(User $user, int $messageId, bool $restore = false): void
    {
        $this->requireAllowed($user);
        DB::transaction(function () use ($user, $messageId, $restore): void {
            $record = DB::table('kmj_mail_messages')
                ->where('mailbox_user_id', (int) $user->getKey())
                ->where('id', $messageId)->lockForUpdate()->first();
            abort_if($record === null, 404);

            if ($restore) {
                abort_unless($record->folder === 'trash', 409);
                $folder = in_array($record->previous_folder, ['inbox', 'sent', 'drafts'], true)
                    ? $record->previous_folder : 'inbox';
                DB::table('kmj_mail_messages')->where('id', $messageId)
                    ->update(['folder' => $folder, 'previous_folder' => null, 'updated_at' => now()]);
            } elseif ($record->folder !== 'trash') {
                DB::table('kmj_mail_messages')->where('id', $messageId)
                    ->update(['folder' => 'trash', 'previous_folder' => $record->folder,
                        'updated_at' => now()]);
            }
        });
    }

    public function grantStaff(User $owner, int $targetId): void
    {
        abort_unless($this->ownerAccess->allows($owner), 403);
        $target = User::query()->whereKey($targetId)->whereNotNull('email_verified_at')->firstOrFail();
        abort_if((int) $target->getKey() === (int) $owner->getKey()
            || (bool) $target->getAttribute('is_platform_owner'), 422);

        DB::transaction(function () use ($owner, $targetId): void {
            DB::table('kmj_mail_staff')->updateOrInsert(['user_id' => $targetId], [
                'granted_by_user_id' => (int) $owner->getKey(),
                'revoked_at' => null, 'updated_at' => now(), 'created_at' => now(),
            ]);
            $this->audit((int) $owner->getKey(), 'kmj_mail_staff_granted', ['user_id' => $targetId]);
        });
    }

    public function revokeStaff(User $owner, int $targetId): void
    {
        abort_unless($this->ownerAccess->allows($owner), 403);
        DB::transaction(function () use ($owner, $targetId): void {
            $count = DB::table('kmj_mail_staff')->where('user_id', $targetId)
                ->whereNull('revoked_at')->update(['revoked_at' => now(), 'updated_at' => now()]);
            abort_unless($count === 1, 404);
            $this->audit((int) $owner->getKey(), 'kmj_mail_staff_revoked', ['user_id' => $targetId]);
        });
    }

    /** @return list<array{user_id:int,name:string,email:string}> */
    public function activeStaff(): array
    {
        return array_values(DB::table('kmj_mail_staff')->join('users', 'users.id', '=', 'kmj_mail_staff.user_id')
            ->whereNull('kmj_mail_staff.revoked_at')->whereNotNull('users.email_verified_at')
            ->orderBy('users.name')->limit(100)
            ->get(['users.id', 'users.name', 'users.email'])
            ->map(static fn (object $row): array => [
                'user_id' => (int) $row->id,
                'name' => (string) $row->name,
                'email' => (string) $row->email,
            ])->all());
    }

    private function validRecipient(int $userId): User
    {
        $user = User::query()->whereKey($userId)->whereNotNull('email_verified_at')->firstOrFail();
        abort_unless($this->allowed($user), 422, 'The recipient does not have a current KMJ workspace mailbox.');

        return $user;
    }

    private function requireAllowed(User $user): void
    {
        abort_unless($this->allowed($user), 403);
    }

    /** @param array<string, int> $metadata */
    private function audit(int $actorId, string $action, array $metadata): void
    {
        OperatorActionAudit::query()->create([
            'actor_user_id' => $actorId,
            'action' => $action,
            'outcome' => 'committed',
            'metadata' => $metadata,
        ]);
    }
}
