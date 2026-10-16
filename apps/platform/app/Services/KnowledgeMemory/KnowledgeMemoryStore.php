<?php

declare(strict_types=1);

namespace App\Services\KnowledgeMemory;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use InvalidArgumentException;

/**
 * Internal memory store; NOT an authentication or HTTP boundary.
 *
 * The caller must resolve a real organization entitlement and project grant
 * before passing the identifiers. No automatic sync, capture, inference or
 * tool execution is provided here. Operational CI/task state is authoritative
 * in CodeBridge, never in these untrusted knowledge observations.
 */
final class KnowledgeMemoryStore
{
    private const TYPES = ['decision', 'bugfix', 'architecture', 'discovery', 'pattern', 'policy', 'summary'];

    /**
     * @param  array<string, mixed>  $input
     * @return array{observation_id: string, revision: int, replayed: bool}
     */
    public function save(string $organizationId, string $projectKey, array $input): array
    {
        $this->assertScope($organizationId, $projectKey);
        $fields = ['operation_id', 'topic_key', 'type', 'title', 'content', 'expected_revision'];
        if (count($input) !== count($fields) || array_diff(array_keys($input), $fields) !== [] || array_diff($fields, array_keys($input)) !== []) {
            throw new InvalidArgumentException('KNOWLEDGE_INVALID_PAYLOAD');
        }

        $operationId = $this->checkedString($input['operation_id'], '/^[A-Za-z0-9][A-Za-z0-9._:-]{7,95}$/D', 96);
        $topicKey = $this->checkedString($input['topic_key'], '/^[a-z][a-z0-9-]{0,23}\/[a-z0-9][a-z0-9._-]{0,63}$/D', 96);
        $type = $this->checkedString($input['type'], '/^[a-z]{1,24}$/D', 24);
        $title = $this->checkedString($input['title'], '/^[^\x00-\x1F\x7F]{1,160}$/uD', 160);
        $content = $this->checkedString($input['content'], '/^[\s\S]+$/uD', 4096);

        if (! in_array($type, self::TYPES, true)
            || ! is_int($input['expected_revision']) || $input['expected_revision'] < 0
            || $input['expected_revision'] > 1000000
            || preg_match('/-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:gh[pousr]_|sk-(?:proj-)?)[A-Za-z0-9_-]{16,}|(?:password|api[_-]?key|access[_-]?token|secret)\s*[:=]\s*\S+/i', $title."\n".$content)
        ) {
            throw new InvalidArgumentException('KNOWLEDGE_INVALID_OR_SENSITIVE_INPUT');
        }

        $expectedRevision = $input['expected_revision'];
        $contentSha = hash('sha256', $content);
        $requestSha = hash('sha256', json_encode([
            $organizationId, $projectKey, $operationId, $topicKey,
            $type, $title, $contentSha, $expectedRevision,
        ], JSON_THROW_ON_ERROR));

        return DB::transaction(function () use (
            $organizationId, $projectKey, $operationId, $topicKey,
            $type, $title, $content, $contentSha, $expectedRevision, $requestSha
        ): array {
            $now = now();

            // Reserve the retry identity BEFORE touching the observation. In
            // PostgreSQL a concurrent ON CONFLICT waits for the first writer;
            // only an atomically committed receipt may be replayed.
            DB::table('knowledge_write_receipts')->insertOrIgnore([
                'organization_id' => $organizationId,
                'project_key' => $projectKey,
                'operation_id' => $operationId,
                'request_sha256' => $requestSha,
                'observation_id' => null,
                'revision' => null,
                'created_at' => $now,
                'updated_at' => $now,
            ]);

            $receipt = DB::table('knowledge_write_receipts')
                ->where('organization_id', $organizationId)
                ->where('project_key', $projectKey)
                ->where('operation_id', $operationId)
                ->lockForUpdate()
                ->first();

            if ($receipt === null || ! hash_equals($receipt->request_sha256, $requestSha)) {
                throw new DomainException('KNOWLEDGE_OPERATION_CONFLICT');
            }

            if ($receipt->revision !== null) {
                return [
                    'observation_id' => $receipt->observation_id,
                    'revision' => (int) $receipt->revision,
                    'replayed' => true,
                ];
            }

            $query = DB::table('knowledge_observations')
                ->where('organization_id', $organizationId)
                ->where('project_key', $projectKey)
                ->where('topic_key', $topicKey);

            if ($expectedRevision === 0) {
                $observationId = (string) Str::uuid();
                $created = DB::table('knowledge_observations')->insertOrIgnore([
                    'id' => $observationId,
                    'organization_id' => $organizationId,
                    'project_key' => $projectKey,
                    'topic_key' => $topicKey,
                    'type' => $type,
                    'title' => $title,
                    'content' => $content,
                    'content_sha256' => $contentSha,
                    'revision' => 1,
                    'created_at' => $now,
                    'updated_at' => $now,
                ]);
                if ($created !== 1) {
                    throw new DomainException('KNOWLEDGE_REVISION_CONFLICT');
                }
                $revision = 1;
            } else {
                $current = $query->lockForUpdate()->first(['id', 'revision']);
                if ($current === null || (int) $current->revision !== $expectedRevision) {
                    throw new DomainException('KNOWLEDGE_REVISION_CONFLICT');
                }
                $revision = $expectedRevision + 1;
                $observationId = $current->id;
                $query->update([
                    'type' => $type,
                    'title' => $title,
                    'content' => $content,
                    'content_sha256' => $contentSha,
                    'revision' => $revision,
                    'updated_at' => $now,
                ]);
            }

            DB::table('knowledge_write_receipts')
                ->where('organization_id', $organizationId)
                ->where('project_key', $projectKey)
                ->where('operation_id', $operationId)
                ->update([
                    'observation_id' => $observationId,
                    'revision' => $revision,
                    'updated_at' => $now,
                ]);

            return [
                'observation_id' => $observationId,
                'revision' => $revision,
                'replayed' => false,
            ];
        }, 3);
    }

    /** @return array<string, mixed>|null */
    public function get(string $organizationId, string $projectKey, string $observationId): ?array
    {
        $this->assertScope($organizationId, $projectKey);
        if (! Str::isUuid($observationId)) {
            throw new InvalidArgumentException('KNOWLEDGE_INVALID_ID');
        }

        $row = DB::table('knowledge_observations')
            ->where('organization_id', $organizationId)
            ->where('project_key', $projectKey)
            ->where('id', $observationId)
            ->first(['id', 'organization_id', 'project_key', 'topic_key', 'type', 'title', 'content', 'revision', 'updated_at']);

        return $row === null ? null : [
            'observation_id' => $row->id,
            'organization_id' => $row->organization_id,
            'project_key' => $row->project_key,
            'topic_key' => $row->topic_key,
            'type' => $row->type,
            'title' => $row->title,
            'content' => $row->content,
            'revision' => (int) $row->revision,
            'updated_at' => $row->updated_at,
        ];
    }

    /**
     * Intentionally compact progressive-disclosure previews; use get() for
     * the full authorized observation. No all-project or global search.
     *
     * @return list<array<string, mixed>>
     */
    public function search(string $organizationId, string $projectKey, string $query, int $limit = 10): array
    {
        $this->assertScope($organizationId, $projectKey);
        $query = trim($query);
        if (! preg_match('/^[a-zA-Z0-9][a-zA-Z0-9 .:-]{0,79}$/D', $query) || $limit < 1 || $limit > 20) {
            throw new InvalidArgumentException('KNOWLEDGE_INVALID_SEARCH');
        }

        $builder = DB::table('knowledge_observations')
            ->where('organization_id', $organizationId)
            ->where('project_key', $projectKey);

        if (DB::getDriverName() === 'pgsql') {
            $builder->whereRaw(
                "to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, '')) @@ plainto_tsquery('simple', ?)",
                [$query]
            );
        } else {
            // CI-only fallback for phpunit.xml's in-memory SQLite database.
            $builder->where(function ($nested) use ($query): void {
                $nested->where('title', 'like', '%'.$query.'%')
                    ->orWhere('content', 'like', '%'.$query.'%');
            });
        }

        return $builder->orderByDesc('updated_at')
            ->orderBy('id')
            ->limit($limit)
            ->get(['id', 'organization_id', 'project_key', 'topic_key', 'type', 'title', 'content', 'revision', 'updated_at'])
            ->map(fn ($row): array => [
                'observation_id' => $row->id,
                'organization_id' => $row->organization_id,
                'project_key' => $row->project_key,
                'topic_key' => $row->topic_key,
                'type' => $row->type,
                'title' => $row->title,
                'revision' => (int) $row->revision,
                // CodeBridge's compact brief is single-line and rejects control
                // characters. Sanitize only the preview; the authorized
                // detail endpoint retains the exact original text.
                'preview' => Str::limit(preg_replace('/[\\x00-\\x1F\\x7F]+/u', ' ', $row->content) ?? '', 240),
                'updated_at' => $row->updated_at,
            ])
            ->all();
    }

    private function assertScope(string $organizationId, string $projectKey): void
    {
        if (! Str::isUuid($organizationId)
            || ! preg_match('/^[a-z0-9][a-z0-9._-]{0,63}$/D', $projectKey)
        ) {
            throw new InvalidArgumentException('KNOWLEDGE_INVALID_SCOPE');
        }
    }

    private function checkedString(mixed $value, string $pattern, int $maxBytes): string
    {
        if (! is_string($value) || strlen($value) < 1 || strlen($value) > $maxBytes
            || trim($value) !== $value || ! preg_match($pattern, $value)
        ) {
            throw new InvalidArgumentException('KNOWLEDGE_INVALID_PAYLOAD');
        }

        return $value;
    }
}
