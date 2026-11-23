<?php

declare(strict_types=1);

namespace Tests\Feature\CodeBridge;

use App\Services\CodeBridge\MonthlyHostedUsageLedger;
use Carbon\CarbonImmutable;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use InvalidArgumentException;
use Tests\TestCase;

final class MonthlyHostedUsageLedgerTest extends TestCase
{
    use RefreshDatabase;

    private const NOVEMBER = '2026-11-23T12:00:00Z';

    private function month(string $date = self::NOVEMBER): CarbonImmutable
    {
        return CarbonImmutable::parse($date);
    }

    public function test_one_completed_call_and_retry_count_exactly_once(): void
    {
        $ledger = app(MonthlyHostedUsageLedger::class);
        $organization = (string) Str::uuid();
        $execution = (string) Str::uuid();

        $first = $ledger->reserveTrusted($organization, 'account', $execution, 'community', $this->month());
        $again = $ledger->reserveTrusted($organization, 'account', $execution, 'community', $this->month());

        $this->assertSame($first, $again);
        $this->assertSame(1, $first['reserved']);
        $this->assertSame(0, $first['completed']);
        $this->assertSame(9999, $first['remaining']);
        $this->assertSame('2026-11-01', $first['period']);

        try {
            $ledger->completeTrusted($organization, 'account', $execution, false);
            $this->fail('Unverified device completion must never consume a call.');
        } catch (DomainException $e) {
            $this->assertSame('CODEBRIDGE_MONTHLY_COMPLETION_PROOF_REQUIRED', $e->getMessage());
        }

        $completed = $ledger->completeTrusted($organization, 'account', $execution, true);
        $repeat = $ledger->completeTrusted($organization, 'account', $execution, true);

        $this->assertSame($completed, $repeat);
        $this->assertSame('completed', $completed['state']);
        $this->assertSame(1, $completed['completed']);
        $this->assertSame(0, $completed['reserved']);
        $this->assertDatabaseCount('codebridge_usage_executions', 1);
        $this->assertDatabaseHas('codebridge_usage_periods', [
            'organization_id' => $organization,
            'subject_key' => 'account',
            'monthly_limit' => 10000,
            'reserved_calls' => 0,
            'completed_calls' => 1,
        ]);
    }

    public function test_last_slot_is_reserved_and_10001st_call_is_rejected(): void
    {
        $ledger = app(MonthlyHostedUsageLedger::class);
        $organization = (string) Str::uuid();
        $ledger->reserveTrusted($organization, 'account', (string) Str::uuid(), 'community', $this->month());
        // Simulate the already-settled 9,999 historical completed receipts.
        DB::table('codebridge_usage_periods')->where('organization_id', $organization)
            ->update(['reserved_calls' => 0, 'completed_calls' => 9999]);
        $last = $ledger->reserveTrusted($organization, 'account', (string) Str::uuid(), 'community', $this->month());
        $this->assertSame(0, $last['remaining']);
        $this->assertSame(1, $last['reserved']);

        try {
            $ledger->reserveTrusted($organization, 'account', (string) Str::uuid(), 'community', $this->month());
            $this->fail('The 10001st remote call must be denied.');
        } catch (DomainException $e) {
            $this->assertSame('CODEBRIDGE_MONTHLY_REMOTE_TOOL_CALL_LIMIT_REACHED', $e->getMessage());
        }
        $this->assertDatabaseHas('codebridge_usage_periods', [
            'organization_id' => $organization,
            'completed_calls' => 9999,
            'reserved_calls' => 1,
        ]);
    }

    public function test_utc_calendar_rollover_creates_independent_month_without_replaying_execution(): void
    {
        $ledger = app(MonthlyHostedUsageLedger::class);
        $organization = (string) Str::uuid();
        $previous = (string) Str::uuid();
        $ledger->reserveTrusted($organization, 'account', $previous, 'community', $this->month('2026-11-30T23:59:59Z'));
        $new = $ledger->reserveTrusted($organization, 'account', (string) Str::uuid(), 'community', $this->month('2026-12-01T00:00:00Z'));

        $this->assertSame('2026-12-01', $new['period']);
        $this->assertSame(9999, $new['remaining']);
        $this->assertDatabaseCount('codebridge_usage_periods', 2);

        try {
            $ledger->reserveTrusted($organization, 'account', $previous, 'community', $this->month('2026-12-01T00:00:00Z'));
            $this->fail('Replay must not reuse an execution ID after month-end.');
        } catch (DomainException $e) {
            $this->assertSame('CODEBRIDGE_MONTHLY_EXECUTION_REPLAY_CONFLICT', $e->getMessage());
        }
    }

    public function test_team_seats_are_isolated_and_subscription_policy_cannot_change_mid_month(): void
    {
        $ledger = app(MonthlyHostedUsageLedger::class);
        $organization = (string) Str::uuid();
        $a = $ledger->reserveTrusted($organization, 'seat:alice', (string) Str::uuid(), 'team', $this->month());
        $b = $ledger->reserveTrusted($organization, 'seat:bob', (string) Str::uuid(), 'team', $this->month());

        $this->assertSame(300000, $a['limit']);
        $this->assertSame(300000, $b['limit']);
        $this->assertDatabaseCount('codebridge_usage_periods', 2);

        try {
            $ledger->reserveTrusted($organization, 'seat:alice', (string) Str::uuid(), 'pro', $this->month());
            $this->fail('Unreviewed mid-month plan changes must fail closed.');
        } catch (DomainException $e) {
            $this->assertSame('CODEBRIDGE_MONTHLY_PLAN_SNAPSHOT_CONFLICT', $e->getMessage());
        }
    }

    public function test_replay_under_different_seat_and_unverified_plan_fail_closed(): void
    {
        $ledger = app(MonthlyHostedUsageLedger::class);
        $organization = (string) Str::uuid();
        $execution = (string) Str::uuid();
        $ledger->reserveTrusted($organization, 'seat:alice', $execution, 'team', $this->month());

        try {
            $ledger->reserveTrusted($organization, 'seat:bob', $execution, 'team', $this->month());
            $this->fail('The same remote execution cannot move between seats.');
        } catch (DomainException $e) {
            $this->assertSame('CODEBRIDGE_MONTHLY_EXECUTION_REPLAY_CONFLICT', $e->getMessage());
        }

        foreach (['business', 'trial', 'unlimited'] as $plan) {
            try {
                $ledger->reserveTrusted($organization, 'account', (string) Str::uuid(), $plan, $this->month());
                $this->fail('Unknown and Business plans require an approved contract.');
            } catch (DomainException $e) {
                $this->assertSame('CODEBRIDGE_MONTHLY_PLAN_UNAVAILABLE', $e->getMessage());
            }
        }

        $this->expectException(InvalidArgumentException::class);
        $ledger->reserveTrusted('client-controlled-org', 'account', (string) Str::uuid(), 'community', $this->month());
    }

    public function test_unknown_delivery_does_not_create_a_fabricated_completion(): void
    {
        $ledger = app(MonthlyHostedUsageLedger::class);
        $organization = (string) Str::uuid();
        $execution = (string) Str::uuid();
        $ledger->reserveTrusted($organization, 'account', $execution, 'pro', $this->month());

        $this->assertDatabaseHas('codebridge_usage_periods', [
            'organization_id' => $organization,
            'reserved_calls' => 1,
            'completed_calls' => 0,
        ]);
        $this->assertDatabaseHas('codebridge_usage_executions', [
            'organization_id' => $organization,
            'execution_id' => $execution,
            'state' => 'reserved',
        ]);
        $this->assertDatabaseCount('entitlements', 0);
        $this->assertDatabaseCount('kslp_licenses', 0);
    }
}
