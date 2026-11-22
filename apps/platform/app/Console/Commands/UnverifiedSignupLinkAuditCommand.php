<?php

declare(strict_types=1);

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Read-only owner-operator preflight. Signup creates user, customer profile
 * and an organization membership together; those records are NOT evidence
 * that deletion is authorized. This command never issues deletion approval.
 */
final class UnverifiedSignupLinkAuditCommand extends Command
{
    protected $signature = 'kmj:users:audit-signup-links {--days=7 : 0 audits all unverified ages} {--json}';

    protected $description = 'Aggregate signup-only organization shape and account linkages, without mutation or PII';

    public function handle(): int
    {
        $days = filter_var($this->option('days'), FILTER_VALIDATE_INT);
        if ($days === false || $days < 0 || $days > 3650) {
            $this->error('days must be 0..3650');

            return self::FAILURE;
        }

        foreach (['users', 'customer_profiles', 'organizations', 'organization_memberships'] as $required) {
            if (! Schema::hasTable($required)) {
                $this->error('UNVERIFIED_SIGNUP_AUDIT_SCHEMA_INCOMPLETE');

                return self::FAILURE;
            }
        }

        $unverified = DB::table('users')->whereNull('email_verified_at');
        $owners = (clone $unverified)->where(function ($query): void {
            $query->where('is_platform_owner', true)->orWhereNotNull('platform_owner_granted_at');
        })->count();
        $cohort = (clone $unverified)->where('is_platform_owner', false)
            ->whereNull('platform_owner_granted_at')
            ->where('created_at', '<=', now('UTC')->subDays($days));
        $totalCohort = (clone $cohort)->count();
        $sample = (clone $cohort)->orderBy('id')->limit(501)->get(['id']);
        $truncated = $sample->count() > 500;
        $ids = $sample->take(500)->pluck('id')->map(static fn ($id): int => (int) $id)->all();

        $profiles = DB::table('customer_profiles')->whereIn('user_id', $ids)->pluck('user_id')
            ->map(static fn ($id): int => (int) $id)->flip();
        $memberships = DB::table('organization_memberships')->whereIn('user_id', $ids)
            ->get(['user_id', 'organization_id', 'role']);
        $byUser = $memberships->groupBy('user_id');
        $orgIds = $memberships->pluck('organization_id')->unique()->values()->all();
        $memberCounts = DB::table('organization_memberships')->whereIn('organization_id', $orgIds)
            ->selectRaw('organization_id, COUNT(*) AS members')->groupBy('organization_id')
            ->pluck('members', 'organization_id');

        $signupShape = 0;
        $linkedMultiMember = 0;
        foreach ($ids as $id) {
            $ms = $byUser->get($id, collect());
            if ($ms->count() === 1 && $profiles->has($id)
                && $ms->first()->role === 'owner'
                && (int) $memberCounts->get($ms->first()->organization_id, 0) === 1) {
                $signupShape++;
            }
            foreach ($ms as $membership) {
                if ((int) $memberCounts->get($membership->organization_id, 0) > 1) {
                    $linkedMultiMember++;
                    break;
                }
            }
        }

        $organizationLinks = [];
        $userLinks = [];
        $unsafeSchema = false;
        foreach (Schema::getTables() as $entry) {
            $table = $entry['name'] ?? null;
            if (! is_string($table) || preg_match('/\A[a-z][a-z0-9_]*\z/D', $table) !== 1) {
                $unsafeSchema = true;

                continue;
            }
            if (in_array($table, ['users', 'organizations', 'organization_memberships',
                'customer_profiles', 'sessions', 'password_reset_tokens'], true)) {
                continue;
            }
            $columns = Schema::getColumnListing($table);
            $orgRefs = array_values(array_filter($columns,
                static fn (string $column): bool => $column === 'organization_id'
                    || str_ends_with($column, '_organization_id')));
            $userRefs = array_values(array_intersect($columns, [
                'user_id', 'owner_user_id', 'account_user_id', 'actor_user_id',
                'created_by', 'updated_by', 'customer_id', 'requested_by', 'notifiable_id',
            ]));
            foreach (Schema::getForeignKeys($table) as $fk) {
                if (count($fk['columns'] ?? []) !== 1) {
                    $unsafeSchema = true;

                    continue;
                }
                if (($fk['foreign_table'] ?? null) === 'organizations') {
                    $orgRefs[] = $fk['columns'][0];
                }
                if (($fk['foreign_table'] ?? null) === 'users') {
                    $userRefs[] = $fk['columns'][0];
                }
            }
            foreach (array_unique($orgRefs) as $column) {
                if (! preg_match('/\A[a-z][a-z0-9_]*\z/D', $column)) {
                    $unsafeSchema = true;

                    continue;
                }
                $count = DB::table($table)->whereIn($column, $orgIds)->count();
                if ($count > 0) {
                    $organizationLinks[$table] = ($organizationLinks[$table] ?? 0) + $count;
                }
            }
            foreach (array_unique($userRefs) as $column) {
                if (! preg_match('/\A[a-z][a-z0-9_]*\z/D', $column)) {
                    $unsafeSchema = true;

                    continue;
                }
                // Never compare a decimal users.id to a native UUID field: PostgreSQL
                // would reject the cast. Skipped or unknown cross-service identity
                // types are explicitly reported as unresolved, not proof of safety.
                $type = Schema::getColumnType($table, $column);
                if (! in_array($type, [
                    'bigint', 'integer', 'smallint', 'int2', 'int4', 'int8',
                    'string', 'varchar', 'character varying', 'character',
                    'bpchar', 'char', 'text', 'citext', 'decimal', 'numeric',
                ], true)) {
                    $unsafeSchema = true;

                    continue;
                }
                $count = DB::table($table)->whereIn($column, array_map('strval', $ids))->count();
                if ($count > 0) {
                    $userLinks[$table] = ($userLinks[$table] ?? 0) + $count;
                }
            }
        }

        $report = [
            'schema' => 'kmj.unverified-signup-link-audit.v1',
            'audit_only' => true,
            'retention_days' => $days,
            'total_users' => DB::table('users')->count(),
            'unverified_users' => (clone $unverified)->count(),
            'unverified_owner_protected' => $owners,
            'unverified_nonowner_older_than_cutoff' => $totalCohort,
            'sampled_capped_at' => 500,
            'sampled_users' => count($ids),
            'sample_truncated' => $truncated,
            'sampled_with_customer_profile' => $profiles->count(),
            'sampled_with_organization_membership' => $byUser->count(),
            'sampled_with_one_owner_membership_and_profile' => $signupShape,
            'sampled_with_multimember_organization' => $linkedMultiMember,
            'sampled_organization_business_references_by_table' => $organizationLinks,
            'sampled_user_business_references_by_table' => $userLinks,
            'unrecognized_schema_or_composite_fk' => $unsafeSchema,
            'license_identity_reconciliation_required' => Schema::hasTable('kslp_licenses'),
            'cross_service_relationships_fully_verified' => false,
            'backup_restore_verified' => false,
            'safe_to_delete_users' => false,
            'deleted_users' => 0,
            'deleted_organizations' => 0,
        ];

        if ($this->option('json')) {
            $this->line(json_encode($report, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES));
        } else {
            foreach ($report as $key => $value) {
                $this->line($key.'='.(is_array($value)
                    ? json_encode($value, JSON_THROW_ON_ERROR)
                    : (is_bool($value) ? ($value ? 'true' : 'false') : $value)));
            }
        }

        return self::SUCCESS;
    }
}
