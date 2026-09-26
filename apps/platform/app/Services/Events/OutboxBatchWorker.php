<?php

namespace App\Services\Events;

use App\Contracts\Events\OutboxPublisher;
use App\Models\DomainOutboxMessage;
use RuntimeException;

final class OutboxBatchWorker
{
    public function __construct(
        private readonly OutboxDispatcher $dispatcher,
        private readonly OutboxPublisher $publisher,
    ) {}

    /** @return array{selected:int,published:int,failed:int} */
    public function run(int $limit = 25, int $maxAttempts = 8, int $baseDelaySeconds = 15): array
    {
        $limit = max(1, min($limit, 100));
        $maxAttempts = max(1, $maxAttempts);
        $baseDelaySeconds = max(1, $baseDelaySeconds);

        $messages = DomainOutboxMessage::query()
            ->whereNull('published_at')
            ->where('attempts', '<', $maxAttempts)
            ->where(function ($query): void {
                $query->whereNull('next_attempt_at')
                    ->orWhere('next_attempt_at', '<=', now());
            })
            ->orderBy('occurred_at')
            ->orderBy('id')
            ->limit($limit)
            ->get();

        $published = 0;
        $failed = 0;

        foreach ($messages as $message) {
            try {
                if ($this->dispatcher->publishOne((string) $message->getKey(), $this->publisher)) {
                    $published++;
                }
            } catch (RuntimeException) {
                $failed++;
                $message->refresh();
                $delay = min(3600, $baseDelaySeconds * (2 ** max(0, $message->attempts - 1)));
                $message->forceFill(['next_attempt_at' => now()->addSeconds($delay)])->save();
            }
        }

        return ['selected' => $messages->count(), 'published' => $published, 'failed' => $failed];
    }
}
