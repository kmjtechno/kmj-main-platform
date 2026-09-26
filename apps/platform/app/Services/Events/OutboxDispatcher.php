<?php

namespace App\Services\Events;

use App\Contracts\Events\OutboxPublisher;
use App\Models\DomainOutboxMessage;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

final class OutboxDispatcher
{
    public function publishOne(string $messageId, OutboxPublisher $publisher): bool
    {
        $failure = null;

        $published = DB::transaction(function () use ($messageId, $publisher, &$failure): bool {
            $message = DomainOutboxMessage::query()
                ->lockForUpdate()
                ->findOrFail($messageId);

            if ($message->published_at !== null) {
                return false;
            }

            try {
                $publisher->publish($message);
            } catch (Throwable $exception) {
                $message->forceFill([
                    'attempts' => $message->attempts + 1,
                    'last_error' => mb_substr($exception->getMessage(), 0, 2000),
                ])->save();
                $failure = $exception;

                return false;
            }

            $message->forceFill([
                'published_at' => now(),
                'attempts' => $message->attempts + 1,
                'last_error' => null,
            ])->save();

            return true;
        });

        if ($failure instanceof Throwable) {
            throw new RuntimeException('Outbox publication failed.', previous: $failure);
        }

        return $published;
    }
}
