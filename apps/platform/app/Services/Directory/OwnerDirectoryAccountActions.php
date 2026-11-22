<?php

declare(strict_types=1);

namespace App\Services\Directory;

use App\Models\User;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use RuntimeException;

/**
 * Owner-only account maintenance, invoked behind auth+verified+passkey
 * PlatformOwnerAccess and a fresh password.confirm step-up. Account deletion
 * is restricted to standalone users; organization/billing/security links
 * always block instead of cascading into commercial records.
 */
final class OwnerDirectoryAccountActions
{
    private const POSSIBLE_REFERENCES = [
        'user_id', 'owner_user_id', 'account_user_id', 'actor_user_id',
        'requested_by', 'created_by', 'updated_by', 'customer_id', 'notifiable_id',
    ];

    /** @param array<string, string|null> $values */
    public function updateContact(int $id, int $actorId, array $values): void
    {
        DB::transaction(function () use ($id, $actorId, $values): void {
            $user = User::query()->whereKey($id)->lockForUpdate()->first();
            if (! $user instanceof User || (bool) $user->is_platform_owner ||
                $user->platform_owner_granted_at !== null) {
                throw new RuntimeException('DIRECTORY_ACCOUNT_PROTECTED');
            }

            $user->forceFill(['name' => trim($values['name'])])->save();
            $profile = $user->customerProfile()->first();
            if ($profile !== null) {
                $contact = [];
                foreach (['phone', 'country'] as $key) {
                    if (isset($values[$key]) && trim((string) $values[$key]) !== '') {
                        $contact[$key] = trim((string) $values[$key]);
                    }
                }
                foreach (['company_name', 'service_interest'] as $key) {
                    if (array_key_exists($key, $values)) {
                        $contact[$key] = $values[$key] === null
                            ? null : trim((string) $values[$key]);
                    }
                }
                if ($contact !== []) {
                    $profile->update($contact);
                }
            }
            $this->recordAudit($actorId, 'directory_user_contact_updated', $id);
        });
    }

    /**
     * Explicitly selected page-only customer accounts: all delete or none.
     * This is NOT the paused unverified-account cleanup or a background sweep.
     *
     * @param  array<int, int>  $ids
     */
    public function deleteSelectedCustomers(array $ids, int $actorId): void
    {
        if (count($ids) < 2 || count($ids) > 15 ||
            count(array_unique($ids)) !== count($ids)) {
            throw new RuntimeException('DIRECTORY_INVALID_SELECTION');
        }
        if (in_array($actorId, $ids, true)) {
            throw new RuntimeException('DIRECTORY_ACCOUNT_PROTECTED');
        }

        sort($ids, SORT_NUMERIC);

        DB::transaction(function () use ($ids, $actorId): void {
            // Lock all selected account rows in canonical ID order before
            // touching any data. Missing/owner accounts fail the entire batch.
            $locked = User::query()->whereKey($ids)->orderBy('id')
                ->lockForUpdate()->get(['id', 'is_platform_owner', 'platform_owner_granted_at']);

            if ($locked->count() !== count($ids)) {
                throw new RuntimeException('DIRECTORY_ACCOUNT_PROTECTED');
            }
            foreach ($locked as $candidate) {
                if ((bool) $candidate->is_platform_owner ||
                    $candidate->platform_owner_granted_at !== null ||
                    (int) $candidate->id === $actorId) {
                    throw new RuntimeException('DIRECTORY_ACCOUNT_PROTECTED');
                }
            }

            foreach ($ids as $id) {
                // Nested DB transactions use savepoints; any exception
                // rolls back EVERY customer and their private signup graph.
                $this->deleteCustomerAndSignupData($id, $actorId);
            }
        }, 1);
    }

    /**
     * Delete one customer's private signup graph, not merely their users row.
     *
     * The linked organization may be deleted only if this customer is its
     * sole owner/member and no business/identity table references it.
     * Unknown relations fail closed. Nothing outside this transaction is
     * mutated and external files are NOT claimed as erased.
     */
    public function deleteCustomerAndSignupData(int $id, int $actorId): void
    {
        DB::transaction(function () use ($id, $actorId): void {
            $user = User::query()->whereKey($id)->lockForUpdate()->first();
            if (! $user instanceof User || $id === $actorId ||
                (bool) $user->is_platform_owner ||
                $user->platform_owner_granted_at !== null) {
                throw new RuntimeException('DIRECTORY_ACCOUNT_PROTECTED');
            }

            if (! Schema::hasTable('organization_memberships') ||
                ! Schema::hasTable('organizations') ||
                ! Schema::hasTable('customer_profiles') ||
                ! Schema::hasTable('operator_action_audits')) {
                throw new RuntimeException('DIRECTORY_REQUIRED_SCHEMA_MISSING');
            }

            // Lock every personal organization before checking dependents.
            // Shared, non-owner, and commercially-used organizations must not
            // be deleted or cause an implicit transfer of other people's data.
            $memberships = DB::table('organization_memberships')
                ->where('user_id', $id)->orderBy('organization_id')
                ->lockForUpdate()->get(['organization_id', 'role']);
            $orgIds = $memberships->pluck('organization_id')
                ->map(static fn ($org): string => (string) $org)->unique()->values()->all();

            if ($memberships->contains(static fn ($membership): bool => $membership->role !== 'owner')) {
                throw new RuntimeException('DIRECTORY_SHARED_ORGANIZATION');
            }
            if ($orgIds !== []) {
                $lockedOrganizations = DB::table('organizations')
                    ->whereIn('id', $orgIds)->orderBy('id')->lockForUpdate()->get(['id']);
                if ($lockedOrganizations->count() !== count($orgIds) ||
                    DB::table('organization_memberships')
                        ->whereIn('organization_id', $orgIds)
                        ->where('user_id', '!=', $id)->exists()) {
                    throw new RuntimeException('DIRECTORY_SHARED_ORGANIZATION');
                }
            }

            // Refuse every discovered business/identity FK or potential
            // untyped cross-service link. Do not trust FK cascades as proof
            // that a purchase, license, audit or linked identity can be lost.
            $this->assertNoLinkedBusinessRecords($id, $orgIds);

            if (Schema::hasTable('sessions')) {
                DB::table('sessions')->where('user_id', $id)->delete();
            }
            if (Schema::hasTable('password_reset_tokens')) {
                DB::table('password_reset_tokens')->where('email', $user->email)->delete();
            }
            // Delete *only* signup-owned records. Profile and membership
            // also cascade, but explicit deletion makes the intent testable.
            DB::table('customer_profiles')->where('user_id', $id)->delete();
            DB::table('organization_memberships')->where('user_id', $id)->delete();
            if ($orgIds !== []) {
                DB::table('organizations')->whereIn('id', $orgIds)->delete();
            }
            $user->delete();

            // Retain a minimal owner operation receipt, without a customer's
            // email/name/contact, so the destructive action is auditable.
            $this->recordAudit($actorId, 'directory_customer_signup_graph_deleted', $id);
        }, 1);
    }

    /**
     * @param  array<int, string>  $orgIds
     */
    private function assertNoLinkedBusinessRecords(int $id, array $orgIds): void
    {
        foreach (Schema::getTables() as $entry) {
            $table = $entry['name'] ?? null;
            if (! is_string($table) ||
                preg_match('/\A[a-z][a-z0-9_]*\z/D', $table) !== 1) {
                throw new RuntimeException('DIRECTORY_SCHEMA_UNRECOGNIZED');
            }

            if (in_array($table, [
                'users', 'organizations', 'organization_memberships',
                'customer_profiles', 'sessions', 'password_reset_tokens',
            ], true)) {
                continue;
            }

            $columns = Schema::getColumnListing($table);
            $userRefs = array_values(array_intersect($columns, self::POSSIBLE_REFERENCES));
            $orgRefs = [];
            foreach (Schema::getColumns($table) as $column) {
                $name = (string) ($column['name'] ?? '');
                if (preg_match('/\A[a-z][a-z0-9_]*\z/D', $name) !== 1) {
                    throw new RuntimeException('DIRECTORY_UNSAFE_COLUMN_NAME');
                }
                if (preg_match('/organization|org_id|tenant|customer_id|issuer/i', $name) !== 1) {
                    continue;
                }
                $type = strtolower((string) ($column['type_name'] ?? ''));
                if (in_array($type, [
                    'bigint', 'integer', 'smallint', 'int2', 'int4', 'int8',
                    'bool', 'boolean', 'timestamp', 'timestamptz', 'date',
                    'float4', 'float8', 'numeric',
                ], true)) {
                    continue;
                }
                if (! in_array($type, [
                    'uuid', 'varchar', 'text', 'bpchar', 'char', 'citext',
                    'character varying', 'string',
                ], true)) {
                    throw new RuntimeException('DIRECTORY_UNREVIEWED_ORGANIZATION_REFERENCE');
                }
                $orgRefs[] = $name;
            }
            foreach (Schema::getForeignKeys($table) as $fk) {
                if (count($fk['columns'] ?? []) !== 1) {
                    if (in_array(($fk['foreign_table'] ?? ''), ['users', 'organizations'], true)) {
                        throw new RuntimeException('DIRECTORY_COMPOSITE_REFERENCE');
                    }

                    continue;
                }
                if (($fk['foreign_table'] ?? '') === 'users') {
                    $userRefs[] = $fk['columns'][0];
                }
                if (($fk['foreign_table'] ?? '') === 'organizations') {
                    $orgRefs[] = $fk['columns'][0];
                }
            }

            foreach (array_unique($userRefs) as $column) {
                if (! is_string($column) ||
                    preg_match('/\A[a-z][a-z0-9_]*\z/D', $column) !== 1) {
                    throw new RuntimeException('DIRECTORY_UNSAFE_REFERENCE');
                }
                $type = Schema::getColumnType($table, $column);
                if ($type === 'uuid') {
                    // A bigint users.id is not representable as a native UUID.
                    continue;
                }
                if (! in_array($type, [
                    'bigint', 'integer', 'smallint', 'int2', 'int4', 'int8',
                    'string', 'varchar', 'character varying', 'character',
                    'bpchar', 'char', 'text', 'citext', 'decimal', 'numeric',
                ], true)) {
                    throw new RuntimeException('DIRECTORY_UNKNOWN_USER_REFERENCE_TYPE');
                }
                if (DB::table($table)->where($column, (string) $id)->exists()) {
                    throw new RuntimeException('DIRECTORY_ACCOUNT_LINKED');
                }
            }

            foreach (array_unique($orgRefs) as $column) {
                if ($orgIds !== [] && DB::table($table)->whereIn($column, $orgIds)->exists()) {
                    throw new RuntimeException('DIRECTORY_ORGANIZATION_LINKED');
                }
            }
        }
    }

    private function recordAudit(int $actorId, string $action, int $targetId): void
    {
        DB::table('operator_action_audits')->insert([
            'actor_user_id' => $actorId,
            'action' => $action,
            'outcome' => 'success',
            'metadata' => json_encode([
                'target_user_id' => $targetId,
                'credentials_or_email_logged' => false,
            ], JSON_THROW_ON_ERROR),
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }
}
