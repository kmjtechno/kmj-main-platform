import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) =>
    readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

void test('release center shows a read-only pending-migration status', () => {
    const svc = read('app/Services/Operations/MigrationStatusSnapshot.php');
    assert.match(svc, /getRan\(\)/);
    assert.doesNotMatch(svc, /->run\(|Artisan::call|->up\(|DB::statement/);
    assert.match(
        read('routes/operator-ops.php'),
        /'migrations' => \$migrations->capture\(\)/,
    );
    const page = read('resources/js/pages/operator-release-center.tsx');
    assert.match(page, /release-migration-status/);
    assert.match(page, /Post-activation has not been applied/);
});
