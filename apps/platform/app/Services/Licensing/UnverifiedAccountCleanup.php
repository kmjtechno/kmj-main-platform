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
            if (! $this->hasLinkedRecords((int) $user->id, $tables, $cutoff->timestamp)) {
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
            if (in_array($table, ['users', 'password_reset_tokens', 'sessions'], true)) {
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

    /** @param array<string, list<string>> $relations */
    private function hasLinkedRecords(int $id, array $relations, int $cutoff): bool
    {
        if (Schema::hasTable('sessions') && DB::table('sessions')
            ->where('user_id', $id)->where('last_activity', '>=', $cutoff)->exists()) {
            return true;
        }

        foreach ($relations as $table => $columns) {
            foreach ($columns as $column) {
                if (DB::table($table)->where($column, (string) $id)->exists()) {
                    return true;
                }
            }
        }

        return false;
    }
}
