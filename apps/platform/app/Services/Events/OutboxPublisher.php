<?php

namespace App\Services\Events;

use App\Models\DomainOutboxMessage;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use InvalidArgumentException;
use Throwable;

final class OutboxPublisher
{
    /**
     * @param  callable(DomainOutboxMessage): void  $publisher
     * @return array{published: int, failed: int, skipped: int}
     */
    public function publishPending(callable $publisher, int $limit = 100): array
    {
        if ($limit < 1 || $limit > 1000) {
            throw new InvalidArgumentException('Outbox publish limit must be between 1 and 1000.');
        }

        $messageIds = DomainOutboxMessage::query()
            ->whereNull('published_at')
            ->orderBy('occurred_at')
            ->orderBy('id')
            ->limit($limit)
            ->pluck('id');
        $result = ['published' => 0, 'failed' => 0, 'skipped' => 0];

        foreach ($messageIds as $messageId) {
            $status = $this->publishOne((string) $messageId, $publisher);
            $result[$status]++;
        }

        return $result;
    }

    /**
     * @param  callable(DomainOutboxMessage): void  $publisher
     * @return 'published'|'failed'|'skipped'
     */
    private function publishOne(string $messageId, callable $publisher): string
    {
        return DB::transaction(function () use ($messageId, $publisher): string {
            $message = DomainOutboxMessage::query()
                ->lockForUpdate()
                ->findOrFail($messageId);

            if ($message->getAttribute('published_at') !== null) {
                return 'skipped';
            }

            $message->setAttribute('attempts', ((int) $message->getAttribute('attempts')) + 1);

            try {
                $publisher($message);
                $message->setAttribute('published_at', now());
                $message->setAttribute('last_error', null);
                $message->save();

                return 'published';
            } catch (Throwable $exception) {
                $message->setAttribute(
                    'last_error',
                    Str::limit($exception->getMessage(), 60000, ''),
                );
                $message->save();

                return 'failed';
            }
        });
    }
}
