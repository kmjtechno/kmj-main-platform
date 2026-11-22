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

    public function deleteStandalone(int $id, int $actorId): void
    {
        DB::transaction(function () use ($id, $actorId): void {
            $user = User::query()->whereKey($id)->lockForUpdate()->first();
            if (! $user instanceof User || $id === $actorId ||
                (bool) $user->is_platform_owner ||
                $user->platform_owner_granted_at !== null) {
                throw new RuntimeException('DIRECTORY_ACCOUNT_PROTECTED');
            }

            // A user's organization, passkey, license, invoice, entitlement,
            // access grant or audit history must NEVER be deleted by cascade.
            foreach (Schema::getTables() as $entry) {
                $table = $entry['name'] ?? null;
                if (! is_string($table) ||
                    preg_match('/\A[a-z][a-z0-9_]*\z/D', $table) !== 1) {
                    throw new RuntimeException('DIRECTORY_SCHEMA_UNRECOGNIZED');
                }
                if (in_array($table, [
                    'users', 'customer_profiles', 'sessions', 'password_reset_tokens',
                ], true)) {
                    continue;
                }

                $columns = Schema::getColumnListing($table);
                $refs = array_values(array_intersect($columns, self::POSSIBLE_REFERENCES));
                foreach (Schema::getForeignKeys($table) as $fk) {
                    if (($fk['foreign_table'] ?? null) !== 'users') {
                        continue;
                    }
                    if (count($fk['columns'] ?? []) !== 1) {
                        throw new RuntimeException('DIRECTORY_SCHEMA_UNRECOGNIZED');
                    }
                    $refs[] = $fk['columns'][0];
                }
                foreach (array_unique($refs) as $column) {
                    if (! is_string($column) ||
                        preg_match('/\A[a-z][a-z0-9_]*\z/D', $column) !== 1) {
                        throw new RuntimeException('DIRECTORY_SCHEMA_UNRECOGNIZED');
                    }
                    $type = Schema::getColumnType($table, $column);
                    if ($type === 'uuid') {
                        // UUID foreign identities do not equal a bigint user ID.
                        // The organization membership is separately protected.
                        continue;
                    }
                    if (! in_array($type, [
                        'integer', 'bigint', 'smallint', 'int2', 'int4', 'int8',
                        'string', 'varchar', 'character varying', 'text',
                        'char', 'character', 'bpchar', 'citext', 'decimal', 'numeric',
                    ], true)) {
                        throw new RuntimeException('DIRECTORY_UNKNOWN_REFERENCE_TYPE');
                    }
                    if (DB::table($table)->where($column, (string) $id)->exists()) {
                        throw new RuntimeException('DIRECTORY_ACCOUNT_LINKED');
                    }
                }
            }

            // Stale sessions and reset tokens are credentials, not commercial
            // records; remove them only inside the exact account transaction.
            if (Schema::hasTable('sessions')) {
                DB::table('sessions')->where('user_id', $id)->delete();
            }
            if (Schema::hasTable('password_reset_tokens')) {
                DB::table('password_reset_tokens')->where('email', $user->email)->delete();
            }
            $user->delete();
            $this->recordAudit($actorId, 'directory_standalone_user_deleted', $id);
        });
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
