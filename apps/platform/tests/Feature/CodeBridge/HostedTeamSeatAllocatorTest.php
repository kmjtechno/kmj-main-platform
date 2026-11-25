<?php

declare(strict_types=1);

namespace Tests\Feature\CodeBridge;

use App\Services\CodeBridge\HostedTeamSeatAllocator;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
use Tests\TestCase;

final class HostedTeamSeatAllocatorTest extends TestCase
{
    use RefreshDatabase;

    public function test_missing_commercial_capacity_cannot_allocate_a_seat(): void
    {
        try {
            app(HostedTeamSeatAllocator::class)->allocateTrusted((string) Str::uuid(), (string) Str::uuid());
            self::fail('Unrecorded capacity must not allocate a seat.');
        } catch (DomainException $exception) {
            self::assertSame('CODEBRIDGE_SEAT_CAPACITY_REQUIRED', $exception->getMessage());
        }

        $this->assertDatabaseCount('codebridge_hosted_team_capacity', 0);
        $this->assertDatabaseCount('codebridge_hosted_seat_assignments', 0);
        $this->assertDatabaseCount('codebridge_usage_executions', 0);
    }
}
