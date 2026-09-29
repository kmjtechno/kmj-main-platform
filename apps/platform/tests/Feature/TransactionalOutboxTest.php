<?php

namespace Tests\Feature;

use App\Models\DomainOutboxConsumption;
use App\Models\DomainOutboxMessage;
use App\Services\Events\IdempotentOutboxConsumer;
use App\Services\Events\TransactionalOutbox;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use RuntimeException;
use Tests\TestCase;

final class TransactionalOutboxTest extends TestCase
{
    use RefreshDatabase;

    public function test_record_is_idempotent_for_the_same_event(): void
    {
        $outbox = app(TransactionalOutbox::class);

        $first = $outbox->record(
            eventType: 'sandbox_license.revoked',
            aggregateType: 'sandbox_license',
            aggregateId: 'jti-123',
            payload: ['reason' => 'owner request'],
            idempotencyKey: 'sandbox-license-revoked:jti-123',
        );
        $second = $outbox->record(
            eventType: 'sandbox_license.revoked',
            aggregateType: 'sandbox_license',
            aggregateId: 'jti-123',
            payload: ['reason' => 'owner request'],
            idempotencyKey: 'sandbox-license-revoked:jti-123',
        );

        self::assertSame($first->getKey(), $second->getKey());
        self::assertSame(1, DomainOutboxMessage::query()->count());
    }

    public function test_reusing_an_idempotency_key_for_different_event_fails_closed(): void
    {
        $outbox = app(TransactionalOutbox::class);

        $outbox->record(
            eventType: 'sandbox_license.issued',
            aggregateType: 'sandbox_license',
            aggregateId: 'jti-123',
            payload: ['status' => 'success'],
            idempotencyKey: 'same-key',
        );

        $this->expectException(DomainException::class);

        $outbox->record(
            eventType: 'sandbox_license.revoked',
            aggregateType: 'sandbox_license',
            aggregateId: 'jti-123',
            payload: ['status' => 'revoked'],
            idempotencyKey: 'same-key',
        );
    }

    public function test_consumer_processes_each_message_once(): void
    {
        $message = app(TransactionalOutbox::class)->record(
            eventType: 'sandbox_license.revoked',
            aggregateType: 'sandbox_license',
            aggregateId: 'jti-123',
            payload: ['status' => 'revoked'],
            idempotencyKey: 'consume-once',
        );
        $consumer = app(IdempotentOutboxConsumer::class);
        $calls = 0;

        $first = $consumer->consume($message, 'test.consumer', function () use (&$calls): void {
            $calls++;
        });
        $second = $consumer->consume($message, 'test.consumer', function () use (&$calls): void {
            $calls++;
        });

        self::assertTrue($first);
        self::assertFalse($second);
        self::assertSame(1, $calls);
        self::assertSame(1, DomainOutboxConsumption::query()->count());
    }

    public function test_failed_consumer_does_not_commit_receipt(): void
    {
        $message = app(TransactionalOutbox::class)->record(
            eventType: 'sandbox_license.revoked',
            aggregateType: 'sandbox_license',
            aggregateId: 'jti-123',
            payload: ['status' => 'revoked'],
            idempotencyKey: 'retry-after-failure',
        );
        $consumer = app(IdempotentOutboxConsumer::class);

        try {
            $consumer->consume($message, 'test.consumer', function (): void {
                throw new RuntimeException('simulated failure');
            });
            self::fail('Expected consumer failure.');
        } catch (RuntimeException $exception) {
            self::assertSame('simulated failure', $exception->getMessage());
        }

        self::assertSame(0, DomainOutboxConsumption::query()->count());

        self::assertTrue($consumer->consume($message, 'test.consumer', static function (): void {}));
        self::assertSame(1, DomainOutboxConsumption::query()->count());
    }
}
