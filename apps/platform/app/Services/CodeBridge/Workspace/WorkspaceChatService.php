<?php

declare(strict_types=1);

namespace App\Services\CodeBridge\Workspace;

use App\Models\AiProvider;
use App\Services\AiProviders\ProviderManager;
use App\Services\Licensing\CodeBridge\CodeBridgeCustomerDeviceDirectory;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use RuntimeException;
use Throwable;

/**
 * Persistent, tenant/user/project-scoped conversations backed by zero-spend admitted models.
 *
 * Truthfulness rules: a message is `running` only while a provider request is really in
 * flight; a cancel that lands first wins and the late provider output is discarded; every
 * lifecycle step is a durable event with a real timestamp. This service cannot run shell
 * commands, read project files or start device jobs; that stays on the paired device.
 */
final class WorkspaceChatService
{
    public const STALE_AFTER_SECONDS = 90;

    private const HISTORY_MESSAGES = 20;

    private const HISTORY_CHARS = 24000;

    private const SYSTEM_PROMPT = 'You are the KMJ CodeBridge workspace assistant. You can only converse. '
        .'You cannot run commands, read files or start jobs from this chat; say so if asked.';

    public function __construct(
        private readonly ProviderManager $providers,
        private readonly CodeBridgeCustomerDeviceDirectory $devices,
    ) {}

    public function projectAuthorized(string $tenantId, string $deviceId, string $projectId): bool
    {
        foreach ($this->devices->forTenant($tenantId, time()) as $device) {
            if ($device['id'] !== $deviceId) {
                continue;
            }
            foreach ($device['projects'] as $project) {
                if ($project['id'] === $projectId) {
                    return true;
                }
            }
        }

        return false;
    }

    public function createConversation(string $tenantId, int $userId, string $deviceId, string $projectId, string $title): string
    {
        abort_unless($this->projectAuthorized($tenantId, $deviceId, $projectId), 404);
        $id = (string) Str::uuid();
        DB::table('codebridge_workspace_conversations')->insert([
            'id' => $id, 'tenant_id' => $tenantId, 'device_id' => $deviceId, 'project_id' => $projectId,
            'user_id' => $userId, 'title' => mb_substr(trim($title) !== '' ? trim($title) : 'New chat', 0, 120),
            'created_at' => now(), 'updated_at' => now(),
        ]);

        return $id;
    }

    /** Tenant + user scoped lookup; anything else is a 404, never a 403 that confirms existence. */
    public function conversation(string $tenantId, int $userId, string $id): WorkspaceConversation
    {
        $found = DB::table('codebridge_workspace_conversations')
            ->where('id', $id)->where('tenant_id', $tenantId)->where('user_id', $userId)->first();
        abort_if($found === null, 404);
        $row = (array) $found;
        $conversation = new WorkspaceConversation(
            (string) $row['id'], (string) $row['tenant_id'], (string) $row['device_id'],
            (string) $row['project_id'], (int) $row['user_id'], (string) $row['title'],
        );
        abort_unless($this->projectAuthorized($tenantId, $conversation->deviceId, $conversation->projectId), 404);

        return $conversation;
    }

    /** @return list<array<string, mixed>> */
    public function conversations(string $tenantId, int $userId, string $deviceId, string $projectId): array
    {
        return DB::table('codebridge_workspace_conversations')
            ->where('tenant_id', $tenantId)->where('user_id', $userId)
            ->where('device_id', $deviceId)->where('project_id', $projectId)
            ->orderByDesc('updated_at')->limit(50)
            ->get(['id', 'title', 'updated_at'])
            ->map(fn (object $row): array => (array) $row)->all();
    }

    /** @return array{messages: list<array<string, mixed>>, events: list<array<string, mixed>>} */
    public function transcript(WorkspaceConversation $conversation): array
    {
        $this->expireStale((string) $conversation->id);
        $iso = static fn (mixed $value): ?string => $value === null ? null : Carbon::parse((string) $value)->toIso8601String();

        return [
            'messages' => DB::table('codebridge_workspace_messages')
                ->where('conversation_id', $conversation->id)->orderBy('id')->limit(200)
                ->get(['id', 'role', 'content', 'status', 'provider_id', 'model', 'error_code', 'retry_of', 'started_at', 'finished_at', 'created_at'])
                ->map(function (object $record) use ($iso): array {
                    $row = (array) $record;
                    // Elapsed time comes only from real timestamps; a running request is measured up to now.
                    $elapsed = $row['started_at'] === null ? null
                        : max(0, Carbon::parse((string) $row['started_at'])->diffInSeconds($row['finished_at'] === null ? now() : Carbon::parse((string) $row['finished_at']), true));

                    return [
                        'id' => $row['id'], 'role' => $row['role'], 'content' => $row['content'], 'status' => $row['status'],
                        'provider_id' => $row['provider_id'], 'model' => $row['model'], 'error_code' => $row['error_code'],
                        'retry_of' => $row['retry_of'], 'created_at' => $iso($row['created_at']),
                        'started_at' => $iso($row['started_at']), 'finished_at' => $iso($row['finished_at']),
                        'elapsed_seconds' => $elapsed === null ? null : (int) floor($elapsed),
                    ];
                })->values()->all(),
            'events' => DB::table('codebridge_workspace_events')
                ->where('conversation_id', $conversation->id)->orderByDesc('id')->limit(100)
                ->get(['id', 'message_id', 'kind', 'status', 'detail', 'created_at'])
                ->reverse()->values()
                ->map(function (object $record) use ($iso): array {
                    $row = (array) $record;

                    return [
                        'id' => $row['id'], 'message_id' => $row['message_id'], 'kind' => $row['kind'],
                        'status' => $row['status'], 'detail' => $row['detail'], 'at' => $iso($row['created_at']),
                    ];
                })->values()->all(),
        ];
    }

    public function send(WorkspaceConversation $conversation, string $content, string $providerId, string $model): void
    {
        $this->assertIdle($conversation);
        $provider = $this->provider($conversation, $providerId);
        DB::table('codebridge_workspace_messages')->insert([
            'id' => (string) Str::ulid(), 'conversation_id' => $conversation->id, 'role' => 'user',
            'content' => $content, 'status' => 'complete', 'created_at' => now(), 'updated_at' => now(),
        ]);
        $this->run($conversation, $provider, $model, null);
    }

    public function retry(WorkspaceConversation $conversation, string $messageId, string $providerId, string $model): void
    {
        $this->assertIdle($conversation);
        $provider = $this->provider($conversation, $providerId);
        $last = DB::table('codebridge_workspace_messages')
            ->where('conversation_id', $conversation->id)->orderByDesc('id')->first();
        $last = $last === null ? null : (array) $last;
        // Only the newest attempt, and only if it did not complete, can be retried.
        if (! ($last !== null && $last['id'] === $messageId && $last['role'] === 'assistant'
            && in_array($last['status'], ['failed', 'cancelled'], true))) {
            throw new RuntimeException('retry_not_allowed');
        }
        $this->run($conversation, $provider, $model, $messageId);
    }

    public function cancel(WorkspaceConversation $conversation, string $messageId): void
    {
        $changed = DB::table('codebridge_workspace_messages')
            ->where('id', $messageId)->where('conversation_id', $conversation->id)
            ->where('role', 'assistant')->where('status', 'running')
            ->update(['status' => 'cancelled', 'error_code' => 'cancelled_by_user', 'finished_at' => now(), 'updated_at' => now()]);
        if ($changed === 0) {
            throw new RuntimeException('not_running');
        }
        $this->event($conversation->id, $messageId, 'cancelled', 'cancelled', 'cancelled_by_user');
    }

    private function provider(WorkspaceConversation $conversation, string $providerId): AiProvider
    {
        // Same tenant only: another organization's provider id is indistinguishable from a missing one.
        return AiProvider::query()->where('organization_id', $conversation->tenantId)->find($providerId)
            ?? throw new RuntimeException('provider_not_found');
    }

    private function run(WorkspaceConversation $conversation, AiProvider $provider, string $model, ?string $retryOf): void
    {
        $messageId = (string) Str::ulid();
        DB::table('codebridge_workspace_messages')->insert([
            'id' => $messageId, 'conversation_id' => $conversation->id, 'role' => 'assistant', 'content' => '',
            'status' => 'running', 'provider_id' => $provider->id, 'model' => $model, 'retry_of' => $retryOf,
            'started_at' => now(), 'created_at' => now(), 'updated_at' => now(),
        ]);
        $this->event($conversation->id, $messageId, 'inference_started', 'running', $model);

        try {
            $result = $this->providers->complete($provider, $model, $this->history($conversation->id, $messageId));
        } catch (Throwable) {
            $result = ['ok' => false, 'content' => null, 'error_code' => 'internal_error'];
        }

        // Conditional write: a cancel (or stale expiry) that landed first wins; output is discarded.
        $changed = DB::table('codebridge_workspace_messages')->where('id', $messageId)->where('status', 'running')
            ->update($result['ok']
                ? ['content' => (string) $result['content'], 'status' => 'complete', 'finished_at' => now(), 'updated_at' => now()]
                : ['status' => 'failed', 'error_code' => (string) $result['error_code'], 'finished_at' => now(), 'updated_at' => now()]);
        if ($changed === 1) {
            $this->event($conversation->id, $messageId, $result['ok'] ? 'inference_completed' : 'inference_failed',
                $result['ok'] ? 'complete' : 'failed', $result['ok'] ? $model : (string) $result['error_code']);
        }
        DB::table('codebridge_workspace_conversations')->where('id', $conversation->id)->update(['updated_at' => now()]);
    }

    /** @return list<array{role: string, content: string}> */
    private function history(string $conversationId, string $excludeMessageId): array
    {
        $rows = DB::table('codebridge_workspace_messages')
            ->where('conversation_id', $conversationId)->where('status', 'complete')->where('id', '!=', $excludeMessageId)
            ->orderByDesc('id')->limit(self::HISTORY_MESSAGES)->get(['role', 'content']);
        $messages = [];
        $chars = 0;
        foreach ($rows as $record) { // newest first, so the size cap drops the oldest
            $row = (array) $record;
            $chars += mb_strlen((string) $row['content']);
            if ($chars > self::HISTORY_CHARS) {
                break;
            }
            array_unshift($messages, ['role' => (string) $row['role'], 'content' => (string) $row['content']]);
        }

        return [['role' => 'system', 'content' => self::SYSTEM_PROMPT], ...$messages];
    }

    private function assertIdle(WorkspaceConversation $conversation): void
    {
        $this->expireStale((string) $conversation->id);
        $busy = DB::table('codebridge_workspace_messages')
            ->where('conversation_id', $conversation->id)->where('status', 'running')->exists();
        if ($busy) {
            throw new RuntimeException('conversation_busy');
        }
    }

    /** A request that outlived the provider timeout is not still running; say so honestly. */
    private function expireStale(string $conversationId): void
    {
        $stale = DB::table('codebridge_workspace_messages')
            ->where('conversation_id', $conversationId)->where('status', 'running')
            ->where('started_at', '<', now()->subSeconds(self::STALE_AFTER_SECONDS))->pluck('id');
        foreach ($stale as $id) {
            $changed = DB::table('codebridge_workspace_messages')->where('id', $id)->where('status', 'running')
                ->update(['status' => 'failed', 'error_code' => 'abandoned', 'finished_at' => now(), 'updated_at' => now()]);
            if ($changed === 1) {
                $this->event($conversationId, (string) $id, 'inference_failed', 'failed', 'abandoned');
            }
        }
    }

    private function event(string $conversationId, ?string $messageId, string $kind, string $status, ?string $detail): void
    {
        DB::table('codebridge_workspace_events')->insert([
            'conversation_id' => $conversationId, 'message_id' => $messageId, 'kind' => $kind,
            'status' => $status, 'detail' => $detail === null ? null : mb_substr($detail, 0, 200), 'created_at' => now(),
        ]);
    }
}
