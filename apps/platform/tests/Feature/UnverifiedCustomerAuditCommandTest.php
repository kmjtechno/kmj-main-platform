<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class UnverifiedCustomerAuditCommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_audit_only_reports_aggregate_candidates_and_preserves_data(): void
    {
        $unverifiedOld = User::factory()->unverified()->create([
            'created_at' => now('UTC')->subDays(45),
            'email' => 'candidate@example.test',
        ]);
        User::factory()->unverified()->create([
            'created_at' => now('UTC')->subDays(2),
        ]);
        User::factory()->create(['created_at' => now('UTC')->subDays(90)]);
        User::factory()->unverified()->create([
            'created_at' => now('UTC')->subDays(90),
            'is_platform_owner' => true,
        ]);

        DB::table('sessions')->insert([
            'id' => 'audit-only-session',
            'user_id' => $unverifiedOld->id,
            'payload' => '',
            'last_activity' => time(),
        ]);

        $before = DB::table('users')->count();
        self::assertSame(0, Artisan::call('kmj:users:audit-unverified', [
            '--days' => '30', '--json' => true,
        ]));
        $output = trim(Artisan::output());
        $report = json_decode($output, true, 512, JSON_THROW_ON_ERROR);

        self::assertSame('kmj.unverified-account-audit.v1', $report['schema']);
        self::assertSame(4, $report['total_users']);
        self::assertSame(1, $report['verified_users']);
        self::assertSame(3, $report['unverified_users']);
        self::assertSame(1, $report['unverified_owners_or_owner_grants']);
        self::assertSame(1, $report['unverified_nonowner_older_than_cutoff']);
        self::assertSame(1, $report['linked_record_counts']['sessions']);
        self::assertFalse($report['safe_to_delete_users']);
        self::assertTrue($report['audit_only']);
        self::assertSame(0, $report['deleted_users']);
        self::assertSame($before, DB::table('users')->count());
        self::assertSame(1, DB::table('sessions')->count());
        self::assertStringNotContainsString('candidate@example.test', $output);
        self::assertStringNotContainsString('audit-only-session', $output);
    }

    public function test_invalid_retention_bound_fails_without_modifying_users(): void
    {
        User::factory()->unverified()->create();
        self::assertSame(1, Artisan::call('kmj:users:audit-unverified', [
            '--days' => '0', '--json' => true,
        ]));
        self::assertSame(1, DB::table('users')->count());
    }
}
