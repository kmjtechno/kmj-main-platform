<?php

declare(strict_types=1);

namespace App\Services\Licensing;

use App\Models\User;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use RuntimeException;

/**
 * Owner-only guarded cleanup. Email-not-verified alone is NEVER sufficient:
 * a linked business/user record blocks deletion even if an FK would cascade.
 * No bulk SQL and no caller-selected table, column, account or age threshold.
 *
 * The one exception to "a membership blocks deletion" is the empty signup organization: the account
 * is the ONLY member of an organization that no other table references at all (no license, order,
 * subscription, entitlement, outbox or audit row), and the only other row is its own signup contact
 * profile. Any reference anywhere keeps the account protected. Purge removes that empty organization.
 */
final class UnverifiedAccountCleanup
{
    private const MIN_AGE_DAYS = 7;

    private const MAX_BATCH = 100;

    private const POSSIBLE_USER_COLUMNS = [
        'user_id', 'owner_user_id', 'account_user_id', 'actor_user_id',
        'created_by', 'updated_by', 'customer_id', 'notifiable_id',
    ];

    /** @return array{unverified: int, eligible: int, protected: int, sha256: string, candidateIds: array<int>} */
    public function preview(): array
    {
        $tables = $this->relationColumns();
        $orgTables = $this->organizationRelationColumns();
        $cutoff = now()->subDays(self::MIN_AGE_DAYS);
        // Never expose passwords, passkeys or verification tokens.
        $users = User::query()
            ->whereNull('email_verified_at')
            ->where('is_platform_owner', false)
            ->whereNull('platform_owner_granted_at')
            ->where('created_at', '<', $cutoff)
            ->orderBy('id')
            ->limit(self::MAX_BATCH + 1)
            ->get(['id', 'email', 'created_at']);

        $unverified = User::query()->whereNull('email_verified_at')->count();
        if ($users->count() > self::MAX_BATCH) {
            // A bounded preview must not misrepresent a partial cohort as ALL.
            throw new RuntimeException('UNVERIFIED_CLEANUP_COHORT_EXCEEDS_SAFE_BATCH');
        }

        $eligible = [];
        foreach ($users as $user) {
            if (! $this->hasLinkedRecords((int) $user->id, $tables, (int) $cutoff->timestamp)
                && $this->ownsOnlyEmptySignupOrganizations((int) $user->id, $orgTables)) {
                $eligible[] = (int) $user->id;
            }
        }

        return [
            'unverified' => $unverified,
            'eligible' => count($eligible),
            'protected' => $unverified - count($eligible),
            'sha256' => hash('sha256', implode(',', $eligible)),
            'candidateIds' => $eligible,
        ];
    }

    /** @return int Number of accounts deleted, not business records or linked accounts. */
    public function purge(int $expected, string $sha256): int
    {
        if ($expected < 0 || $expected > self::MAX_BATCH ||
            preg_match('/\A[a-f0-9]{64}\z/D', $sha256) !== 1) {
            throw new RuntimeException('UNVERIFIED_CLEANUP_INVALID_CONFIRMATION');
        }

        return DB::transaction(function () use ($expected, $sha256): int {
            // Serialize eligibility against email verification and concurrent
            // account edits. Never delete a user outside this exact snapshot.
            User::query()->whereNull('email_verified_at')
                ->where('is_platform_owner', false)
                ->whereNull('platform_owner_granted_at')
                ->where('created_at', '<', now()->subDays(self::MIN_AGE_DAYS))
                ->lockForUpdate()->get(['id']);

            $proof = $this->preview();
            if ($proof['eligible'] !== $expected ||
                ! hash_equals($proof['sha256'], $sha256)) {
                throw new RuntimeException('UNVERIFIED_CLEANUP_STALE_PREVIEW');
            }

            $deleted = 0;
            foreach ($proof['candidateIds'] as $id) {
                // Run again under locks to reject new memberships, grants
                // and any other discovered relations before deleting.
                $current = $this->preview();
                if (! in_array($id, $current['candidateIds'], true)) {
                    throw new RuntimeException('UNVERIFIED_CLEANUP_CHANGED_ACCOUNT');
                }
                $account = User::query()->whereKey($id)
                    ->whereNull('email_verified_at')
                    ->where('is_platform_owner', false)
                    ->whereNull('platform_owner_granted_at')
                    ->lockForUpdate()->first();
                if (! $account instanceof User) {
                    throw new RuntimeException('UNVERIFIED_CLEANUP_CHANGED_ACCOUNT');
                }

                // Stale sessions and expired email-reset tokens are not
                // durable purchases/organizations. Fresh sessions block above.
                if (Schema::hasTable('sessions')) {
                    DB::table('sessions')->where('user_id', $id)->delete();
                }
                if (Schema::hasTable('password_reset_tokens')) {
                    DB::table('password_reset_tokens')->where('email', $account->email)->delete();
                }
                // Eligibility above proved these organizations have this account as their only member
                // and no reference anywhere. A restrictive foreign key would abort the whole transaction.
                $orgIds = DB::table('organization_memberships')->where('user_id', $id)->pluck('organization_id')->all();
                DB::table('organization_memberships')->where('user_id', $id)->delete();
                if ($orgIds !== []) {
                    DB::table('organizations')->whereIn('id', $orgIds)->delete();
                }
                $account->delete();
                $deleted++;
            }

            return $deleted;
        }, 1);
    }

    /** @return array<string, list<string>> */
    private function relationColumns(): array
    {
        $relations = [];
        $tables = Schema::getTables();
        foreach ($tables as $entry) {
            $table = $entry['name'] ?? null;
            if (! is_string($table) || preg_match('/\A[a-z][a-z0-9_]*\z/D', $table) !== 1) {
                throw new RuntimeException('UNVERIFIED_CLEANUP_UNRECOGNIZED_TABLE');
            }
            // organization_memberships is judged by ownsOnlyEmptySignupOrganizations(); customer_profiles
            // is the account's own signup contact data and is removed with the account (cascade).
            if (in_array($table, ['users', 'password_reset_tokens', 'sessions', 'organization_memberships', 'customer_profiles'], true)) {
                continue;
            }

            $columns = Schema::getColumnListing($table);
            $refs = array_values(array_intersect($columns, self::POSSIBLE_USER_COLUMNS));
            foreach (Schema::getForeignKeys($table) as $fk) {
                if (($fk['foreign_table'] ?? '') !== 'users') {
                    continue;
                }
                $fkColumns = $fk['columns'] ?? [];
                if (count($fkColumns) !== 1) {
                    throw new RuntimeException('UNVERIFIED_CLEANUP_COMPOSITE_FOREIGN_KEY');
                }
                $refs[] = $fkColumns[0];
            }
            if ($refs !== []) {
                $relations[$table] = array_values(array_unique($refs));
            }
        }

        return $relations;
    }

    /**
     * Tables and columns that can hold an organization id. Unknown column types fail closed.
     *
     * @return array<string, list<string>>
     */
    private function organizationRelationColumns(): array
    {
        $relations = [];
        foreach (Schema::getTables() as $entry) {
            $table = $entry['name'] ?? null;
            if (! is_string($table) || preg_match('/\A[a-z][a-z0-9_]*\z/D', $table) !== 1) {
                throw new RuntimeException('UNVERIFIED_CLEANUP_UNRECOGNIZED_TABLE');
            }
            if (in_array($table, ['organizations', 'organization_memberships'], true)) {
                continue;
            }
            $refs = [];
            foreach (Schema::getColumns($table) as $column) {
                $name = (string) ($column['name'] ?? '');
                if (preg_match('/organization|org_id|tenant|customer_id|issuer/i', $name) !== 1) {
                    continue;
                }
                $type = strtolower((string) ($column['type_name'] ?? ''));
                // JSON/JSONB can contain nested organization UUID strings. Never treat
                // a potential organization reference in either type as proven empty.
                if (in_array($type, ['bigint', 'integer', 'smallint', 'int2', 'int4', 'int8', 'bool', 'boolean', 'timestamp', 'timestamptz', 'date', 'float4', 'float8', 'numeric'], true)) {
                    continue; // cannot hold a UUID organization id
                }
                if (! in_array($type, ['uuid', 'varchar', 'text', 'bpchar', 'char', 'citext'], true)) {
                    throw new RuntimeException('UNVERIFIED_CLEANUP_ORG_REFERENCE_TYPE_UNKNOWN');
                }
                $refs[] = $name;
            }
            foreach (Schema::getForeignKeys($table) as $fk) {
                if (($fk['foreign_table'] ?? '') !== 'organizations') {
                    continue;
                }
                $fkColumns = $fk['columns'] ?? [];
                if (count($fkColumns) !== 1) {
                    throw new RuntimeException('UNVERIFIED_CLEANUP_COMPOSITE_FOREIGN_KEY');
                }
                $refs[] = $fkColumns[0];
            }
            if ($refs !== []) {
                $relations[$table] = array_values(array_unique($refs));
            }
        }

        return $relations;
    }

    /**
     * True when every organization this account belongs to has this account as its only member
     * and is referenced by no other table. No membership at all is also true.
     *
     * @param  array<string, list<string>>  $orgRelations
     */
    private function ownsOnlyEmptySignupOrganizations(int $id, array $orgRelations): bool
    {
        $orgIds = DB::table('organization_memberships')->where('user_id', $id)
            ->pluck('organization_id')->map(fn ($org): string => (string) $org)->all();
        if ($orgIds === []) {
            return true;
        }

        $others = DB::table('organization_memberships')->whereIn('organization_id', $orgIds)
            ->where('user_id', '!=', $id)->exists();
        if ($others) {
            return false;
        }

        foreach ($orgRelations as $table => $columns) {
            foreach ($columns as $column) {
                if (preg_match('/\A[a-z][a-z0-9_]*\z/D', $column) !== 1) {
                    throw new RuntimeException('UNVERIFIED_CLEANUP_UNSAFE_REFERENCE_COLUMN');
                }
                if (DB::table($table)->whereIn($column, $orgIds)->exists()) {
                    return false;
                }
            }
        }

        return true;
    }

    /** @param array<string, list<string>> $relations */
    private function hasLinkedRecords(int $id, array $relations, int $cutoff): bool
    {
        if (Schema::hasTable('sessions') && DB::table('sessions')
            ->where('user_id', $id)->where('last_activity', '>=', $cutoff)->exists()) {
            return true;
        }

        foreach ($relations as $table => $columns) {
            foreach ($columns as $column) {
                // A customer_id may be UUID while users.id is bigint. Always
                // compare text to text; never cast a user ID into a UUID or
                // silently skip that potentially related record.
                if (preg_match('/\\A[a-z][a-z0-9_]*\\z/D', $column) !== 1) {
                    throw new RuntimeException('UNVERIFIED_CLEANUP_UNSAFE_REFERENCE_COLUMN');
                }
                $type = Schema::getColumnType($table, $column);
                if ($type === 'uuid') {
                    // Decimal users.id cannot be represented by a native UUID.
                    continue;
                }
                if (! in_array($type, ['bigint', 'integer', 'smallint', 'int2', 'int4', 'int8', 'string', 'varchar', 'character varying', 'character', 'bpchar', 'char', 'text', 'citext', 'decimal', 'numeric'], true)) {
                    // Unknown foreign-reference type requires a fresh reviewed
                    // schema contract, never optimistic eligibility.
                    throw new RuntimeException('UNVERIFIED_CLEANUP_REFERENCE_TYPE_UNKNOWN');
                }
                if (DB::table($table)->where($column, (string) $id)->exists()) {
                    return true;
                }
            }
        }

        return false;
    }
}
