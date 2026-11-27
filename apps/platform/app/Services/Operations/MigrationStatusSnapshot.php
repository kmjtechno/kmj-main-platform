<?php

declare(strict_types=1);

namespace App\Services\Operations;

use Illuminate\Database\Migrations\Migrator;
use Illuminate\Support\Facades\Schema;
use Throwable;

/**
 * Read-only: compares the migration files shipped in this release with the migrations table.
 * It runs nothing and writes nothing, so the owner can see whether post-activation was applied.
 */
final class MigrationStatusSnapshot
{
    /** @return array{status: string, pending_count: int, pending: list<string>, applied_count: int} */
    public function capture(): array
    {
        try {
            if (! Schema::hasTable((string) config('database.migrations.table', 'migrations'))) {
                return $this->unavailable();
            }

            // The shared migrator also knows the package migration paths registered by providers.
            /** @var Migrator $migrator */
            $migrator = app('migrator');
            $files = array_keys($migrator->getMigrationFiles(array_merge([database_path('migrations')], $migrator->paths())));
            $ran = $migrator->getRepository()->getRan();
            $pending = array_values(array_diff($files, $ran));
            sort($pending);

            return [
                'status' => $pending === [] ? 'ok' : 'pending',
                'pending_count' => count($pending),
                'pending' => array_slice($pending, 0, 10),
                'applied_count' => count(array_intersect($files, $ran)),
            ];
        } catch (Throwable $exception) {
            report($exception);

            return $this->unavailable();
        }
    }

    /** @return array{status: string, pending_count: int, pending: list<string>, applied_count: int} */
    private function unavailable(): array
    {
        return ['status' => 'unavailable', 'pending_count' => 0, 'pending' => [], 'applied_count' => 0];
    }
}
