/** ModelFabric owner page: source-only checks, no network and no provider requests. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (path) => readFileSync(resolve(root, path), 'utf8');
const page = read('resources/js/pages/operator-modelfabric.tsx');
const shell = read('resources/js/layouts/owner-module-shell.tsx');
const commandOs = read('resources/js/components/operator-command-os.tsx');
const routes = read('routes/model-fabric.php');
const controller = read('app/Http/Controllers/ModelFabricController.php');

void test('ModelFabric & AI sidebar entries open the real ModelFabric page', () => {
    assert.match(
        shell,
        /label: 'ModelFabric & AI',\s*href: '\/operator\/modelfabric'/,
    );
    assert.match(commandOs, /\['ModelFabric & AI', '\/operator\/modelfabric'/);
});

void test('page states the verified-zero rule and offers no paid switch', () => {
    assert.match(page, /NO_FREE_ROUTE_AVAILABLE/);
    assert.match(page, /Paid inference cannot be enabled from this page/);
    assert.doesNotMatch(page, /allow[_ -]?paid|enable[_ -]?paid fallback/i);
});

void test('routes are owner, password-confirmed and throttled; controller denies non owners', () => {
    assert.match(routes, /'auth', 'verified', 'password\.confirm'/);
    assert.match(routes, /throttle:20,1/);
    assert.match(controller, /\$this->access->require\(\$user\)/);
    assert.match(controller, /Evidence applies only to allowlist providers/);
    assert.match(controller, /MAX_EVIDENCE_DAYS = 30/);
});
