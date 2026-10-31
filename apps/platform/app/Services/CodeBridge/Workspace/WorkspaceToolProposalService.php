<?php

declare(strict_types=1);

namespace App\Services\CodeBridge\Workspace;

use Illuminate\Database\UniqueConstraintViolationException;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use InvalidArgumentException;
use JsonException;
use RuntimeException;

/**
 * Chat-to-device consent bridge. An assistant reply may carry ONE fenced proposal block naming an
 * allowlisted tool from {@see WorkspaceToolCatalog}. The block is parsed and validated against that closed
 * catalog and stored as a `pending` proposal bound to the conversation's tenant/user/device/project.
 * Nothing reaches a device until the SAME user confirms; confirmation goes through
 * {@see WorkspaceJobService::enqueue()}, which re-checks the live paired-project grant, applies the
 * per-project active cap and is idempotent per proposal. Free text is never executed.
 */
final class WorkspaceToolProposalService
{
    public const TTL_SECONDS = 900;

    private const BLOCK = '/```kmj-tool-proposal[ \t]*\r?\n(.{1,600}?)\r?\n```[ \t\r\n]*\z/s';

    public function __construct(private readonly WorkspaceJobService $jobs) {}

    /** Instruction appended to the system prompt ONLY while device jobs are enabled on this server. */
    public static function promptAddendum(): string
    {
        $tools = [];
        foreach (WorkspaceToolCatalog::all() as $tool) {
            $tools[] = $tool['name'].($tool['name'] === 'quality_gate' ? ' (arguments: {"gate":"<configured gate id>"})' : ' (no arguments)');
        }

        return ' You may suggest ONE device tool by ending your reply with a fenced block exactly like '
            .'```kmj-tool-proposal'."\n".'{"tool":"git_status","arguments":{}}'."\n".'```'
            .'. Allowed tools: '.implode(', ', $tools).'. A suggestion runs nothing: the user must press Confirm, '
            .'and the device may still refuse. Never claim a tool already ran.';
    }

    /**
     * @return array{tool: string, arguments: array<string, string>}|null null when the reply holds no valid proposal
     */
    public static function parse(string $content): ?array
    {
        // Only ONE explicit proposal at the END of a completed assistant reply is actionable.
        // Quoted examples, multiple proposals, and trailing prose must not become executable suggestions.
        if (substr_count($content, '```kmj-tool-proposal') !== 1 || preg_match(self::BLOCK, $content, $match) !== 1) {
            return null;
        }
        try {
            $decoded = json_decode($match[1], true, 4, JSON_THROW_ON_ERROR);
        } catch (JsonException) {
            return null;
        }
        if (! is_array($decoded) || array_diff(array_keys($decoded), ['tool', 'arguments']) !== [] || ! is_string($decoded['tool'] ?? null)) {
            return null;
        }
        $arguments = $decoded['arguments'] ?? [];
        if (! is_array($arguments)) {
            return null;
        }
        try {
            return ['tool' => $decoded['tool'], 'arguments' => WorkspaceToolCatalog::validate($decoded['tool'], $arguments)];
        } catch (InvalidArgumentException) {
            return null;
        }
    }

    /** Stores a pending proposal for a COMPLETED assistant message. Returns its id, or null when none applies. */
    public function capture(WorkspaceConversation $conversation, string $messageId, string $content): ?string
    {
        if (! WorkspaceJobService::enabled()) {
            return null;
        }
        $proposal = self::parse($content);
        if ($proposal === null) {
            return null;
        }
        $id = (string) Str::ulid();
        try {
            DB::table('codebridge_workspace_tool_proposals')->insert([
                'id' => $id, 'conversation_id' => $conversation->id, 'message_id' => $messageId,
                'tenant_id' => $conversation->tenantId, 'user_id' => $conversation->userId,
                'device_id' => $conversation->deviceId, 'project_id' => $conversation->projectId,
                'tool' => $proposal['tool'], 'arguments' => json_encode($proposal['arguments'], JSON_THROW_ON_ERROR),
                'status' => 'pending', 'created_at' => now(), 'updated_at' => now(),
            ]);
        } catch (UniqueConstraintViolationException) {
            return null; // one proposal per assistant message
        }

        return $id;
    }

    /** @return list<array<string, mixed>> proposals of one conversation with the REAL status of any job they created */
    public function forConversation(WorkspaceConversation $conversation): array
    {
        $this->expireStale((string) $conversation->id);

        return array_values(DB::table('codebridge_workspace_tool_proposals as p')
            ->leftJoin('codebridge_workspace_jobs as j', function ($join): void {
                $join->on('j.id', '=', 'p.job_id')->on('j.tenant_id', '=', 'p.tenant_id');
            })
            ->where('p.conversation_id', $conversation->id)
            ->where('p.tenant_id', $conversation->tenantId)->where('p.user_id', $conversation->userId)
            ->orderByDesc('p.id')->limit(50)
            ->get(['p.id', 'p.message_id', 'p.tool', 'p.arguments', 'p.status', 'p.job_id', 'p.decided_at', 'p.created_at', 'j.status as job_status', 'j.progress as job_progress', 'j.summary as job_summary', 'j.error_code as job_error_code', 'j.finished_at as job_finished_at'])
            ->reverse()->values()
            ->map(function (object $record): array {
                $row = (array) $record;
                $arguments = json_decode((string) $row['arguments'], true);

                return [
                    'id' => (string) $row['id'], 'message_id' => (string) $row['message_id'], 'tool' => (string) $row['tool'],
                    'arguments' => is_array($arguments) ? $arguments : [], 'status' => (string) $row['status'],
                    'job_id' => $row['job_id'] === null ? null : (string) $row['job_id'],
                    'job_status' => $row['job_status'] === null ? null : (string) $row['job_status'],
                    // The device's own bounded report, shown as a result in the chat. Plain text only, never rendered as markup.
                    'job_progress' => $row['job_progress'] === null ? null : (int) $row['job_progress'],
                    'job_summary' => $row['job_summary'] === null ? null : mb_substr((string) $row['job_summary'], 0, 600),
                    'job_error_code' => $row['job_error_code'] === null ? null : (string) $row['job_error_code'],
                    'job_finished_at' => $row['job_finished_at'] === null ? null : Carbon::parse((string) $row['job_finished_at'])->toIso8601String(),
                    'expires_in_seconds' => $row['status'] === 'pending'
                        ? max(0, self::TTL_SECONDS - (int) Carbon::parse((string) $row['created_at'])->diffInSeconds(now(), true)) : null,
                ];
            })->all());
    }

    /**
     * @return array{job_id: string, created: bool, conversation_id: string}
     *
     * @throws RuntimeException proposal_rejected | proposal_expired | jobs_disabled | too_many_active_jobs
     */
    public function confirm(string $tenantId, int $userId, string $proposalId): array
    {
        abort_unless(Str::isUlid($proposalId), 404);

        $result = DB::transaction(function () use ($tenantId, $userId, $proposalId): array {
            $row = $this->locked($tenantId, $userId, $proposalId);
            $conversation = (string) $row['conversation_id'];
            if ($row['status'] === 'confirmed') {
                return ['job_id' => (string) $row['job_id'], 'created' => false, 'conversation_id' => $conversation];
            }
            if ($row['status'] === 'rejected') {
                return ['error' => 'proposal_rejected'];
            }
            if ($row['status'] === 'expired' || $this->isStale($row)) {
                $this->mark($proposalId, 'expired'); // committed: an expired proposal stays expired

                return ['error' => 'proposal_expired'];
            }
            $arguments = json_decode((string) $row['arguments'], true);
            // Idempotency key is derived from the proposal id: a double click can never create a second job.
            // Any exception here (403/404 grant, jobs_disabled, too_many_active_jobs) rolls everything back
            // and leaves the proposal pending.
            $queued = $this->jobs->enqueue(
                $tenantId, $userId, (string) $row['device_id'], (string) $row['project_id'], (string) $row['tool'],
                is_array($arguments) ? $arguments : [], 'prop-'.$proposalId,
            );
            DB::table('codebridge_workspace_tool_proposals')->where('id', $proposalId)->update([
                'status' => 'confirmed', 'job_id' => $queued['id'], 'decided_at' => now(), 'updated_at' => now(),
            ]);

            return ['job_id' => $queued['id'], 'created' => $queued['created'], 'conversation_id' => $conversation];
        });
        if (isset($result['error'])) {
            throw new RuntimeException($result['error']);
        }

        return $result;
    }

    /** @return array{conversation_id: string} */
    public function reject(string $tenantId, int $userId, string $proposalId): array
    {
        abort_unless(Str::isUlid($proposalId), 404);

        return DB::transaction(function () use ($tenantId, $userId, $proposalId): array {
            $row = $this->locked($tenantId, $userId, $proposalId);
            if ($row['status'] === 'confirmed') {
                throw new RuntimeException('proposal_already_confirmed');
            }
            if ($row['status'] === 'pending') {
                $this->mark($proposalId, 'rejected');
            }

            return ['conversation_id' => (string) $row['conversation_id']];
        });
    }

    /**
     * Tenant AND user scoped, row-locked; anything else is a 404 that never confirms existence.
     *
     * @return array<string, mixed>
     */
    private function locked(string $tenantId, int $userId, string $proposalId): array
    {
        $found = DB::table('codebridge_workspace_tool_proposals')
            ->where('id', $proposalId)->where('tenant_id', $tenantId)->where('user_id', $userId)->lockForUpdate()->first();
        abort_if($found === null, 404);

        return (array) $found;
    }

    /** @param array<string, mixed> $row */
    private function isStale(array $row): bool
    {
        return Carbon::parse((string) $row['created_at'])->diffInSeconds(now(), true) > self::TTL_SECONDS;
    }

    private function mark(string $proposalId, string $status): void
    {
        DB::table('codebridge_workspace_tool_proposals')->where('id', $proposalId)->where('status', 'pending')
            ->update(['status' => $status, 'decided_at' => now(), 'updated_at' => now()]);
    }

    private function expireStale(string $conversationId): void
    {
        DB::table('codebridge_workspace_tool_proposals')->where('conversation_id', $conversationId)->where('status', 'pending')
            ->where('created_at', '<', now()->subSeconds(self::TTL_SECONDS))
            ->update(['status' => 'expired', 'decided_at' => now(), 'updated_at' => now()]);
    }
}
