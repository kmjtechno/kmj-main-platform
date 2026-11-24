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

    /**
     * Owner-only mailbox metrics; never return aggregate data from other
     * employees' private mailbox copies or global mail transport tables.
     *
     * @return array{total_messages:int,unread:int,mail_text_bytes:int}
     */
    public function summary(User $user): array
    {
        $this->requireAllowed($user);
        $query = DB::table('kmj_mail_messages')
            ->where('mailbox_user_id', (int) $user->getKey());

        $contentSize = (clone $query)
            ->where('folder', '!=', 'trash')
            ->selectRaw('COALESCE(SUM(LENGTH(body) + LENGTH(subject)), 0) AS bytes')
            ->first();

        return [
            'total_messages' => (int) (clone $query)->where('folder', '!=', 'trash')->count(),
            'unread' => (int) (clone $query)->where('folder', 'inbox')->whereNull('read_at')->count(),
            // Only approximate message text, never server storage or a quota.
            'mail_text_bytes' => (int) ($contentSize->bytes ?? 0),
        ];
    }

    /** @return array{items:array<int,array<string,mixed>>,unread:int,total:int,page:int,page_size:int,has_more:bool} */
    public function mailbox(User $user, string $folder, string $search = '', int $page = 1): array
    {
        $this->requireAllowed($user);
        if (! in_array($folder, ['inbox', 'sent', 'drafts', 'archive', 'starred', 'trash'], true)) {
            throw ValidationException::withMessages(['folder' => 'Unknown mailbox folder.']);
        }

        abort_unless($page >= 1 && $page <= 1000, 422);
        $query = DB::table('kmj_mail_messages')
            ->where('mailbox_user_id', (int) $user->getKey());

        if ($folder === 'starred') {
            $query->where('is_starred', true)->whereNotIn('folder', ['trash', 'drafts']);
        } else {
            $query->where('folder', $folder);
        }

        if ($search !== '') {
            $query->where(function ($builder) use ($search): void {
                $escaped = addcslashes($search, '%_\\');
                $builder->where('subject', 'like', '%'.$escaped.'%')
                    ->orWhere('body', 'like', '%'.$escaped.'%')
                    ->orWhere('recipient_email', 'like', '%'.$escaped.'%')
                    ->orWhere('sender_email', 'like', '%'.$escaped.'%');
            });
        }

        $total = (clone $query)->count();
        $limit = 40;
        $rows = $query->orderByDesc('id')->offset(($page - 1) * $limit)->limit($limit + 1)
            ->get(['id', 'thread_id', 'folder', 'subject', 'body', 'sender_user_id',
                'recipient_user_id', 'recipient_email', 'sender_email', 'delivery_state',
                'is_starred', 'read_at', 'sent_at', 'created_at']);
        $hasMore = $rows->count() > $limit;

        $items = $rows->take($limit)->map(static fn (object $row): array => [
            'id' => (int) $row->id,
            'thread_id' => (string) $row->thread_id,
            'folder' => (string) $row->folder,
            'subject' => (string) $row->subject,
            'snippet' => mb_strimwidth((string) $row->body, 0, 160, '…'),
            'sender_user_id' => $row->sender_user_id === null ? null : (int) $row->sender_user_id,
            'recipient_user_id' => $row->recipient_user_id === null ? null : (int) $row->recipient_user_id,
            'recipient_email' => $row->recipient_email,
            'sender_email' => $row->sender_email,
            'delivery_state' => $row->delivery_state,
            'unread' => $row->read_at === null && in_array($row->folder, ['inbox', 'archive'], true),
            'starred' => (bool) $row->is_starred,
            'at' => (string) ($row->sent_at ?? $row->created_at),
        ])->all();

        $unread = DB::table('kmj_mail_messages')
            ->where('mailbox_user_id', (int) $user->getKey())
            ->where('folder', 'inbox')->whereNull('read_at')->count();

        return ['items' => array_values($items), 'unread' => $unread,
            'total' => (int) $total, 'page' => $page, 'page_size' => $limit, 'has_more' => $hasMore];
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
                'subject', 'body', 'recipient_email', 'sender_email', 'delivery_state', 'is_starred',
                'sent_at', 'created_at']);

        DB::table('kmj_mail_messages')
            ->where('mailbox_user_id', (int) $user->getKey())
            ->where('thread_id', (string) $anchor->thread_id)
            ->whereIn('folder', ['inbox', 'archive'])->whereNull('read_at')
            ->update(['read_at' => now(), 'updated_at' => now()]);

        return [
            'thread_id' => (string) $anchor->thread_id,
            'items' => array_values($rows->map(static fn (object $row): array => [
                'id' => (int) $row->id,
                'from_id' => $row->sender_user_id === null ? null : (int) $row->sender_user_id,
                'to_id' => $row->recipient_user_id === null ? null : (int) $row->recipient_user_id,
                'recipient_email' => $row->recipient_email,
                'sender_email' => $row->sender_email,
                'delivery_state' => $row->delivery_state,
                'starred' => (bool) $row->is_starred,
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
                        'recipient_email' => null, 'sender_email' => null,
                        'delivery_state' => null,
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
                ->where('mailbox_user_id', $senderId)->where('client_key', $clientKey)->first();
            if ($existing !== null) {
                if ($existing->recipient_email !== null
                    || (int) $existing->recipient_user_id !== $recipientId
                    || $existing->subject !== $subject || $existing->body !== $body) {
                    throw ValidationException::withMessages(['client_key' => 'This submission key was already used for a different message.']);
                }

                return (int) $existing->id;
            }

            $thread = (string) Str::uuid();
            if ($replyToId !== null) {
                $anchor = DB::table('kmj_mail_messages')
                    ->where('mailbox_user_id', $senderId)->where('id', $replyToId)->first();
                abort_if($anchor === null, 404);
                abort_unless($anchor->sender_user_id !== null, 403);
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
            abort_if($draft->recipient_email !== null || $draft->recipient_user_id === null, 422);
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
                $folder = in_array($record->previous_folder, ['inbox', 'sent', 'drafts', 'archive'], true)
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

    /**
     * Atomic, mailbox-scoped organization actions. Never mutates a recipient's
     * independent copy, triggers email delivery, or permanently deletes records.
     *
     * @param  list<int>  $ids
     */
    public function manage(User $user, array $ids, string $action): int
    {
        $this->requireAllowed($user);
        abort_unless(in_array($action, [
            'star', 'unstar', 'read', 'unread', 'archive', 'unarchive', 'trash', 'restore',
        ], true), 422);

        $ids = array_values(array_unique(array_map('intval', $ids)));
        abort_unless(count($ids) >= 1 && count($ids) <= 40 && min($ids) > 0, 422);
        $ownerId = (int) $user->getKey();

        return DB::transaction(function () use ($ownerId, $ids, $action): int {
            $records = DB::table('kmj_mail_messages')
                ->where('mailbox_user_id', $ownerId)
                ->whereIn('id', $ids)
                ->orderBy('id')
                ->lockForUpdate()->get(['id', 'folder', 'previous_folder']);
            abort_unless($records->count() === count($ids), 404);

            // Fail the entire bulk action when even one selected item is
            // ineligible; never partially mutate a mixed-folder selection.
            foreach ($records as $record) {
                $folder = (string) $record->folder;
                $ok = match ($action) {
                    'star', 'unstar' => in_array($folder, ['inbox', 'sent', 'archive'], true),
                    'read', 'unread' => in_array($folder, ['inbox', 'archive'], true),
                    'archive' => $folder === 'inbox',
                    'unarchive' => $folder === 'archive',
                    'trash' => $folder !== 'trash',
                    'restore' => $folder === 'trash',
                };
                abort_unless($ok, 409);
            }

            $now = now();
            foreach ($records as $record) {
                $updates = match ($action) {
                    'star' => ['is_starred' => true],
                    'unstar' => ['is_starred' => false],
                    'read' => ['read_at' => $now],
                    'unread' => ['read_at' => null],
                    'archive' => ['folder' => 'archive', 'previous_folder' => null],
                    'unarchive' => ['folder' => 'inbox', 'previous_folder' => null],
                    'trash' => ['folder' => 'trash', 'previous_folder' => $record->folder],
                    'restore' => [
                        'folder' => in_array($record->previous_folder, ['inbox', 'sent', 'drafts', 'archive'], true)
                            ? $record->previous_folder : 'inbox',
                        'previous_folder' => null,
                    ],
                };
                DB::table('kmj_mail_messages')
                    ->where('mailbox_user_id', $ownerId)
                    ->where('id', (int) $record->id)
                    ->update($updates + ['updated_at' => $now]);
            }

            $this->audit($ownerId, 'kmj_mail_messages_organized', ['count' => count($ids)]);

            return count($ids);
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
                ->whereNull('revoked_at')->update(['revoked_at' => now(), 'sender_alias' => null, 'updated_at' => now()]);
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
            ->get(['users.id', 'users.name', 'users.email', 'kmj_mail_staff.sender_alias'])
            ->map(static fn (object $row): array => [
                'user_id' => (int) $row->id,
                'name' => (string) $row->name,
                'email' => (string) $row->email,
                'sender_alias' => $row->sender_alias === null ? null : (string) $row->sender_alias,
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
