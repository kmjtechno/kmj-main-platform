<?php

namespace App\Services\Events;

use App\Models\DomainOutboxMessage;

final class OutboxHealthSnapshot
{
    /**
     * @return array{
     *   status:string,
     *   max_attempts:int,
     *   pending:int,
     *   due:int,
     *   retrying:int,
     *   exhausted:int,
     *   published:int,
     *   recent_exhausted:array<int,array<string,mixed>>
     * }
     */
    public function capture(int $maxAttempts = 8): array
    {
        $maxAttempts = max(1, $maxAttempts);

        $pendingQuery = DomainOutboxMessage::query()->whereNull('published_at');
        $pending = (clone $pendingQuery)->count();
        $published = DomainOutboxMessage::query()->whereNotNull('published_at')->count();

        $exhausted = (clone $pendingQuery)
            ->where('attempts', '>=', $maxAttempts)
            ->count();

        $due = (clone $pendingQuery)
            ->where('attempts', '<', $maxAttempts)
            ->where(function ($query): void {
                $query->whereNull('next_attempt_at')
                    ->orWhere('next_attempt_at', '<=', now());
            })
            ->count();

        $retrying = (clone $pendingQuery)
            ->where('attempts', '<', $maxAttempts)
            ->whereNotNull('next_attempt_at')
            ->where('next_attempt_at', '>', now())
            ->count();

        $recentExhausted = [];

        foreach (
            DomainOutboxMessage::query()
                ->whereNull('published_at')
                ->where('attempts', '>=', $maxAttempts)
                ->latest('updated_at')
                ->limit(10)
                ->get([
                    'id',
                    'event_type',
                    'aggregate_type',
                    'aggregate_id',
                    'organization_id',
                    'attempts',
                    'last_error',
                    'occurred_at',
                    'updated_at',
                ]) as $message
        ) {
            $recentExhausted[] = [
                'id' => (string) $message->getKey(),
                'event_type' => $message->event_type,
                'aggregate_type' => $message->aggregate_type,
                'aggregate_id' => $message->aggregate_id,
                'organization_id' => $message->organization_id,
                'attempts' => $message->attempts,
                'last_error' => $message->last_error,
                'occurred_at' => $message->occurred_at?->toIso8601String(),
                'updated_at' => $message->updated_at?->toIso8601String(),
            ];
        }

        $status = $exhausted > 0
            ? 'critical'
            : ($due > 0 || $retrying > 0 ? 'degraded' : 'healthy');

        return [
            'status' => $status,
            'max_attempts' => $maxAttempts,
            'pending' => $pending,
            'due' => $due,
            'retrying' => $retrying,
            'exhausted' => $exhausted,
            'published' => $published,
            'recent_exhausted' => $recentExhausted,
        ];
    }
}
