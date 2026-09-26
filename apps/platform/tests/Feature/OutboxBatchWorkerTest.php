<?php

namespace Tests\Feature;

use App\Contracts\Events\OutboxPublisher;
use App\Events\DomainOutboxPublished;
use App\Models\DomainOutboxMessage;
use App\Services\Events\OutboxBatchWorker;
use App\Services\Events\TransactionalOutbox;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Event;
use RuntimeException;
use Tests\TestCase;

final class OutboxBatchWorkerTest extends TestCase
{
    use RefreshDatabase;

    public function test_worker_publishes_only_due_pending_messages_within_limit(): void
    {
        $due = $this->message('due');
        $future = $this->message('future');
        $future->forceFill(['next_attempt_at' => now()->addHour()])->save();

        $publisher = new class implements OutboxPublisher
        {
            public array $ids = [];

            public function publish(DomainOutboxMessage $message): void
            {
                $this->ids[] = (string) $message->getKey();
            }
        };

        $this->app->instance(OutboxPublisher::class, $publisher);
        $worker = app(OutboxBatchWorker::class);
        $result = $worker->run(limit: 1, maxAttempts: 8, baseDelaySeconds: 15);

        self::assertSame(['selected' => 1, 'published' => 1, 'failed' => 0], $result);
        self::assertSame([(string) $due->getKey()], $publisher->ids);
        self::assertNotNull($due->refresh()->published_at);
        self::assertNull($future->refresh()->published_at);
    }

    public function test_failure_schedules_exponential_retry_and_max_attempts_are_skipped(): void
    {
        $message = $this->message('retry');
        $publisher = new class implements OutboxPublisher
        {
            public function publish(DomainOutboxMessage $message): void
            {
                throw new RuntimeException('transport down');
            }
        };
        $this->app->instance(OutboxPublisher::class, $publisher);

        $before = now();
        $result = app(OutboxBatchWorker::class)->run(limit: 25, maxAttempts: 2, baseDelaySeconds: 20);

        self::assertSame(['selected' => 1, 'published' => 0, 'failed' => 1], $result);
        $message->refresh();
        self::assertSame(1, $message->attempts);
        self::assertSame('transport down', $message->last_error);
        self::assertTrue($message->next_attempt_at->greaterThanOrEqualTo($before->addSeconds(19)));

        $message->forceFill(['attempts' => 2, 'next_attempt_at' => now()->subSecond()])->save();
        self::assertSame(['selected' => 0, 'published' => 0, 'failed' => 0], app(OutboxBatchWorker::class)->run(maxAttempts: 2));
    }

    public function test_artisan_worker_uses_bound_laravel_event_publisher(): void
    {
        Event::fake([DomainOutboxPublished::class]);
        $message = $this->message('artisan');

        $this->artisan('outbox:work', ['--limit' => 5])
            ->expectsOutput('selected=1 published=1 failed=0')
            ->assertSuccessful();

        Event::assertDispatched(DomainOutboxPublished::class);
        self::assertNotNull($message->refresh()->published_at);
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
