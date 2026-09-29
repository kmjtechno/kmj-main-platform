<?php

namespace Tests\Feature;

use App\Models\DomainOutboxMessage;
use App\Services\Events\OutboxHealthSnapshot;
use App\Services\Events\TransactionalOutbox;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class OutboxHealthSnapshotTest extends TestCase
{
    use RefreshDatabase;

    public function test_snapshot_classifies_due_retrying_exhausted_and_published_messages(): void
    {
        $due = $this->message('due');

        $retrying = $this->message('retrying');
        $retrying->forceFill([
            'attempts' => 2,
            'next_attempt_at' => now()->addMinutes(5),
            'last_error' => 'temporary failure',
        ])->save();

        $exhausted = $this->message('exhausted');
        $exhausted->forceFill([
            'attempts' => 8,
            'last_error' => 'permanent failure',
            'next_attempt_at' => now()->subMinute(),
        ])->save();

        $published = $this->message('published');
        $published->forceFill([
            'attempts' => 1,
            'published_at' => now(),
        ])->save();

        $snapshot = app(OutboxHealthSnapshot::class)->capture(8);

        self::assertSame('critical', $snapshot['status']);
        self::assertSame(3, $snapshot['pending']);
        self::assertSame(1, $snapshot['due']);
        self::assertSame(1, $snapshot['retrying']);
        self::assertSame(1, $snapshot['exhausted']);
        self::assertSame(1, $snapshot['published']);
        self::assertSame('test.exhausted', $snapshot['recent_exhausted'][0]['event_type']);
        self::assertSame('permanent failure', $snapshot['recent_exhausted'][0]['last_error']);

        self::assertNull($due->refresh()->published_at);
    }

    public function test_snapshot_is_healthy_when_no_unpublished_messages_exist(): void
    {
        $message = $this->message('done');
        $message->forceFill([
            'attempts' => 1,
            'published_at' => now(),
        ])->save();

        $snapshot = app(OutboxHealthSnapshot::class)->capture();

        self::assertSame('healthy', $snapshot['status']);
        self::assertSame(0, $snapshot['pending']);
        self::assertSame(0, $snapshot['exhausted']);
        self::assertSame([], $snapshot['recent_exhausted']);
    }

    public function test_status_command_fails_closed_when_exhausted_messages_exist(): void
    {
        $message = $this->message('command');
        $message->forceFill([
            'attempts' => 8,
            'last_error' => 'dead letter',
        ])->save();

        $this->artisan('outbox:status', ['--max-attempts' => 8, '--json' => true])
            ->expectsOutputToContain('"status":"critical"')
            ->assertFailed();
    }

    private function message(string $key): DomainOutboxMessage
    {
        return app(TransactionalOutbox::class)->record(
            eventType: 'test.'.$key,
            aggregateType: 'test',
            aggregateId: $key,
            payload: ['key' => $key],
            idempotencyKey: 'health-'.$key,
        );
    }
}
