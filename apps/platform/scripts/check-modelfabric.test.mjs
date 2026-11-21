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

void test('gateway only walks planned routes and the refresh stays read-only', () => {
    const gateway = read('app/Services/AiProviders/ModelFabricGateway.php');
    const refresh = read('app/Console/Commands/ModelFabricRefreshCommand.php');
    const consoleRoutes = read('routes/console.php');
    assert.match(gateway, /\$this->router->plan\(/);
    assert.match(gateway, /MAX_ATTEMPTS = 3/);
    assert.doesNotMatch(gateway, /Http::|->post\(/);
    assert.match(refresh, /\$manager->test\(\$provider\)/);
    assert.doesNotMatch(refresh, /complete\(/);
    assert.match(consoleRoutes, /modelfabric:refresh'\)->everySixHours\(\)/);
    assert.match(page, /Routing activity/);
});

void test('smart routing only reorders eligible routes and never adds one', () => {
    const scorer = read('app/Services/AiProviders/RouteScorer.php');
    const gateway = read('app/Services/AiProviders/ModelFabricGateway.php');
    assert.match(scorer, /Orders ALREADY ELIGIBLE routes/);
    assert.doesNotMatch(scorer, /AiProvider\b|Http::|Cache::/);
    assert.match(gateway, /\$this->scorer->order\(\$plan\['routes'\]/);
    assert.match(gateway, /nearLimit/);
});

void test('API endpoint is bearer-hashed, throttled, non-streaming and ignores caller model choice', () => {
    const mw = read('app/Http/Middleware/AuthenticateModelFabricToken.php');
    const api = read('app/Http/Controllers/ModelFabricApiController.php');
    const apiRoutes = read('routes/model-fabric-api.php');
    const model = read('app/Models/AiModelToken.php');
    assert.match(apiRoutes, /throttle:120,1/);
    assert.match(apiRoutes, /AuthenticateModelFabricToken::class/);
    assert.match(mw, /AiModelToken::hash\(\$plain\)/);
    assert.match(mw, /RateLimiter::tooManyAttempts/);
    assert.match(model, /hash\('sha256'/);
    assert.doesNotMatch(model, /plain_token|'token'\s*=>/);
    assert.match(api, /streaming_not_supported/);
    assert.match(api, /ignored on purpose/);
    assert.match(api, /\$this->gateway->complete\(/);
    assert.doesNotMatch(api, /Http::|Log::/);
    assert.match(controller, /Flashed for exactly one page load/);
    assert.match(read('routes/model-fabric.php'), /tokens\.store/);
});
