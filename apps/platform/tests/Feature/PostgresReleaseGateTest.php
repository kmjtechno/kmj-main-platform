<?php

declare(strict_types=1);

namespace Tests\Feature;

use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Tests\TestCase;

final class PostgresReleaseGateTest extends TestCase
{
    public function test_release_qa_uses_the_private_postgresql_socket_and_migrated_schema(): void
    {
        if (getenv('KMJ_PG_STAGING_VERIFY') !== '1') {
            $this->markTestSkipped('Only the explicit isolated PostgreSQL release verifier runs this test.');
        }

        $socket = getenv('KMJ_PG_VERIFY_SOCKET');
        self::assertIsString($socket);
        self::assertNotSame('', $socket);
        self::assertSame('pgsql', DB::connection()->getDriverName());
        self::assertSame('kmj_release_qa', DB::connection()->getDatabaseName());
        self::assertSame($socket, config('database.connections.pgsql.host'));
        self::assertTrue(Schema::hasTable('payment_gateway_settings'));
        self::assertTrue(Schema::hasTable('kslp_license_keys'));
    }
}
