<?php

declare(strict_types=1);

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Privacy-preserving pre-cleanup inventory. Never mutates users, credentials,
 * payment state, licenses, sessions or audit history.
 *
 * Missing tables and unknown cross-service identities are NOT proof of safety
 * for deletion. The output deliberately excludes names/emails/IDs.
 */
final class UnverifiedCustomerAuditCommand extends Command
{
    protected $signature = 'kmj:users:audit-unverified {--days=30 : Minimum unverified account age in days} {--json}';

    protected $description = 'Read-only, aggregate unverified-user inventory before a separately approved retention-safe cleanup';

    public function handle(): int
    {
        $days = filter_var($this->option('days'), FILTER_VALIDATE_INT);

        if ($days === false || $days < 1 || $days > 3650) {
            $this->error('days must be an integer between 1 and 3650');

            return self::FAILURE;
        }

        $candidateQuery = DB::table('users')
            ->whereNull('email_verified_at')
            ->where('is_platform_owner', false)
            ->whereNull('platform_owner_granted_at')
            ->where('created_at', '<=', now('UTC')->subDays($days));

        $allUnverified = DB::table('users')->whereNull('email_verified_at');

        $counts = [
            'schema' => 'kmj.unverified-account-audit.v1',
            'generated_at_utc' => now('UTC')->toIso8601String(),
            'display_timezone' => 'Asia/Kolkata',
            'retention_days' => $days,
            'total_users' => DB::table('users')->count(),
            'verified_users' => DB::table('users')->whereNotNull('email_verified_at')->count(),
            'unverified_users' => (clone $allUnverified)->count(),
            'unverified_owners_or_owner_grants' => (clone $allUnverified)
                ->where(function ($query): void {
                    $query->where('is_platform_owner', true)
                        ->orWhereNotNull('platform_owner_granted_at');
                })->count(),
            'unverified_nonowner_older_than_cutoff' => (clone $candidateQuery)->count(),
            'linked_record_counts' => [],
            'cross_service_relationships_fully_verified' => false,
            'database_backup_verified' => false,
            'safe_to_delete_users' => false,
            'deleted_users' => 0,
        ];

        foreach ([
            'passkeys' => 'user_id',
            'sessions' => 'user_id',
            'codebridge_oauth_codes' => 'user_id',
            'codebridge_oauth_refresh_tokens' => 'user_id',
            'operator_action_audits' => 'actor_user_id',
            'codebridge_project_assignments' => 'requested_by',
        ] as $table => $column) {
            if (! Schema::hasTable($table) || ! Schema::hasColumn($table, $column)) {
                $counts['linked_record_counts'][$table] = 'not_checked_table_missing';

                continue;
            }
            $counts['linked_record_counts'][$table] = DB::table($table)
                ->whereIn($column, (clone $candidateQuery)->select('id'))->count();
        }

        // customer_id in the legacy license plane is a string and may not be
        // equivalent to a user.id. Account-to-license linkage needs explicit
        // reconciliation with the issuer data model before any deletion.
        $counts['license_identity_reconciliation_required'] = Schema::hasTable('kslp_licenses');
        $counts['audit_only'] = true;

        if ((bool) $this->option('json')) {
            $this->line((string) json_encode(
                $counts, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR
            ));
        } else {
            foreach ($counts as $key => $value) {
                $this->line($key.'='.(
                    is_array($value)
                        ? json_encode($value, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR)
                        : ($value === true ? 'true' : ($value === false ? 'false' : $value))
                ));
            }
        }

        return self::SUCCESS;
    }
}
