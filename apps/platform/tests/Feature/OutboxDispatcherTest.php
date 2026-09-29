<?php

namespace Tests\Feature;

use App\Contracts\Events\OutboxPublisher;
use App\Models\DomainOutboxMessage;
use App\Services\Events\OutboxDispatcher;
use App\Services\Events\TransactionalOutbox;
use Illuminate\Foundation\Testing\RefreshDatabase;
use RuntimeException;
use Tests\TestCase;

final class OutboxDispatcherTest extends TestCase
{
    use RefreshDatabase;

    public function test_successful_publication_marks_message_once(): void
    {
        $message = $this->message('dispatch-success');
        $publisher = new class implements OutboxPublisher
        {
            public int $calls = 0;

            public function publish(DomainOutboxMessage $message): void
            {
                $this->calls++;
            }
        };
        $dispatcher = app(OutboxDispatcher::class);

        self::assertTrue($dispatcher->publishOne((string) $message->getKey(), $publisher));
        self::assertFalse($dispatcher->publishOne((string) $message->getKey(), $publisher));

        $message->refresh();
        self::assertSame(1, $publisher->calls);
        self::assertSame(1, $message->attempts);
        self::assertNotNull($message->published_at);
        self::assertNull($message->last_error);
    }

    public function test_failed_publication_records_retry_evidence_and_remains_pending(): void
    {
        $message = $this->message('dispatch-failure');
        $publisher = new class implements OutboxPublisher
        {
            public function publish(DomainOutboxMessage $message): void
            {
                throw new RuntimeException('simulated transport failure');
            }
        };

        try {
            app(OutboxDispatcher::class)->publishOne((string) $message->getKey(), $publisher);
            self::fail('Expected publication failure.');
        } catch (RuntimeException $exception) {
            self::assertSame('Outbox publication failed.', $exception->getMessage());
            self::assertSame('simulated transport failure', $exception->getPrevious()?->getMessage());
        }

        $message->refresh();
        self::assertSame(1, $message->attempts);
        self::assertNull($message->published_at);
        self::assertSame('simulated transport failure', $message->last_error);
    }

    private function message(string $key): DomainOutboxMessage
    {
        return app(TransactionalOutbox::class)->record(
            eventType: 'test.event',
            aggregateType: 'test',
            aggregateId: $key,
            payload: ['key' => $key],
            idempotencyKey: $key,
        );
    }
}
