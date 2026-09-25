<?php

namespace App\Services\Events;

use App\Models\DomainOutboxConsumption;
use App\Models\DomainOutboxMessage;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;

final class IdempotentOutboxConsumer
{
    /**
     * @param  callable(DomainOutboxMessage): void  $handler
     */
    public function consume(
        DomainOutboxMessage $message,
        string $consumer,
        callable $handler,
    ): bool {
        $consumer = trim($consumer);

        if ($consumer === '') {
            throw new InvalidArgumentException('Outbox consumer name is required.');
        }

        return DB::transaction(function () use ($message, $consumer, $handler): bool {
            $existing = DomainOutboxConsumption::query()
                ->where('message_id', $message->getKey())
                ->where('consumer', $consumer)
                ->lockForUpdate()
                ->first();

            if ($existing !== null) {
                return false;
            }

            $handler($message);

            DomainOutboxConsumption::query()->create([
                'message_id' => $message->getKey(),
                'consumer' => $consumer,
                'consumed_at' => now(),
            ]);

            return true;
        });
    }
}
