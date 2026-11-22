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

void test('API endpoint is bearer-hashed, throttled, replays streams after routing and ignores caller model choice', () => {
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
    assert.doesNotMatch(api, /streaming_not_supported/);
    assert.match(api, /text\/event-stream/);
    assert.match(api, /data: \[DONE\]/);
    assert.match(api, /ignored on purpose/);
    assert.match(api, /\$this->gateway->complete\(/);
    assert.doesNotMatch(api, /Http::|Log::/);
    assert.match(controller, /Flashed for exactly one page load/);
    assert.match(read('routes/model-fabric.php'), /tokens\.store/);
});

void test('owner daily caps and priority are enforced before provider limits and stay owner-only', () => {
    const gateway = read('app/Services/AiProviders/ModelFabricGateway.php');
    const scorer = read('app/Services/AiProviders/RouteScorer.php');
    assert.match(gateway, /daily_cap_reached/);
    assert.match(gateway, /nearDailyCap/);
    assert.match(scorer, /never overrides task fit/);
    assert.match(controller, /provider_limits_saved/);
    assert.match(read('routes/model-fabric.php'), /providers\.update/);
    assert.match(page, /Save limits/);
});

void test('Hugging Face one-click OAuth is secretless PKCE, inference-api only and needs a free-account attestation', () => {
    const service = read('app/Services/AiProviders/HuggingFaceConnect.php');
    const hf = read('app/Http/Controllers/HuggingFaceConnectController.php');
    const aiRoutes = read('routes/ai-providers.php');
    const web = read('routes/web.php');
    const hub = read('resources/js/components/ai-provider-connect-hub.tsx');
    assert.match(service, /SCOPE = 'inference-api'/);
    assert.match(service, /'token_endpoint_auth_method' => 'none'/);
    assert.match(service, /code_challenge_method' => 'S256'/);
    assert.doesNotMatch(service, /client_secret/);
    assert.match(hf, /'free_account_confirmed' => \['accepted'\]/);
    assert.match(hf, /hash_equals\(\$expectedState, \$returnedState\)/);
    assert.match(hf, /pull\('ai_provider_hf_oauth'\)/);
    assert.match(aiRoutes, /connect\/huggingface/);
    assert.match(web, /oauth\/clients\/huggingface\.json/);
    assert.match(hub, /Free account with no\s+payment method/);
});

void test('bulk evidence needs one explicit attestation, is capped and renewal never revives revoked evidence', () => {
    const controller = read('app/Http/Controllers/ModelFabricController.php');
    const routes = read('routes/model-fabric.php');
    const page = read('resources/js/pages/operator-modelfabric.tsx');
    assert.match(controller, /MAX_BULK_MODELS = 50/);
    assert.match(controller, /'attest_pricing' => \['accepted'\]/);
    assert.match(controller, /Revoked evidence cannot be renewed/);
    assert.match(controller, /DB::transaction/);
    assert.match(routes, /evidence\/bulk/);
    assert.match(routes, /evidence\/\{evidence\}\/renew/);
    assert.match(page, /Approve \{bulkModels\.length\} selected/);
    assert.match(page, /Renew 30 days/);
});

void test('ModelFabric connects OpenRouter and Hugging Face itself and returns to the ModelFabric page', () => {
    const page = read('resources/js/pages/operator-modelfabric.tsx');
    const hf = read('app/Http/Controllers/HuggingFaceConnectController.php');
    const or = read('app/Http/Controllers/AiProviderController.php');
    const service = read('app/Services/AiProviders/HuggingFaceConnect.php');
    assert.match(page, /return_to: 'modelfabric'/);
    assert.match(page, /connectOAuth\('huggingface'\)/);
    assert.match(hf, /operator\.modelfabric\.index/);
    assert.match(or, /operator\.modelfabric\.index/);
    assert.match(service, /oauth_exchange_failed \(http/);
    assert.doesNotMatch(service, /oauth_exchange_failed \(.*body/);
});

void test('Hugging Face exchange accepts long opaque tokens and only reports a coarse failure shape', () => {
    const service = read('app/Services/AiProviders/HuggingFaceConnect.php');
    assert.match(service, /\{16,4096\}/);
    assert.match(service, /no_access_token/);
    assert.match(service, /bad_token_shape_len_/);
    assert.doesNotMatch(service, /\{16,512\}/);
});

void test('Auto-approve rules stay narrow, expiring, chat-only and revocable', () => {
    const applier = read('app/Services/AiProviders/ModelFabricRuleApplier.php');
    const controller = read('app/Http/Controllers/ModelFabricController.php');
    const routes = read('routes/model-fabric.php');
    const refresh = read('app/Console/Commands/ModelFabricRefreshCommand.php');
    const page = read('resources/js/pages/operator-modelfabric.tsx');
    assert.match(applier, /MAX_MATCHES = 50/);
    assert.match(applier, /MIN_LITERAL_PREFIX = 10/);
    assert.match(applier, /'tts'.*'image'.*'embedding'/);
    assert.match(applier, /revoked_at !== null/);
    assert.match(applier, /'allowlist'/);
    assert.match(applier, /paid_inference_enabled' => false/);
    assert.match(controller, /A revoked rule cannot be renewed/);
    assert.match(controller, /'attest_pricing' => \['accepted'\]/);
    assert.match(routes, /rules\/\{rule\}\/renew/);
    assert.match(refresh, /ModelFabricRuleApplier/);
    assert.match(page, /Save auto-approve rule/);
});

void test('GitHub Models is an allowlist-only preset with its own read-only catalog URL', () => {
    const config = read('config/ai_providers.php');
    const adapter = read(
        'app/Services/AiProviders/OpenAiCompatibleAdapter.php',
    );
    assert.match(
        config,
        /'github' => \['label' => 'GitHub Models', 'base_url' => 'https:\/\/models\.github\.ai\/inference', 'free_tier' => 'allowlist'\]/,
    );
    assert.match(adapter, /https:\/\/models\.github\.ai\/catalog\/models/);
});

void test('credit-limited approvals (ADR-004 rev 2) are capped, attested and enforced', () => {
    const migration = read(
        'database/migrations/2026_11_22_000200_add_cost_class_to_ai_model_evidence.php',
    );
    const gateway = read('app/Services/AiProviders/ModelFabricGateway.php');
    // No raw DDL in the migration (migration review policy); validation and the gateway enforce the pairing.
    assert.doesNotMatch(migration, /DB::statement/);
    assert.match(migration, /credit_daily_cap/);
    // The gateway skips a credit route at its cap and fails closed without one.
    assert.match(gateway, /credit_cap_reached/);
    assert.match(gateway, /\$cap <= 0/);
    // The owner form requires the cap and the hard-cap statement before saving.
    assert.match(page, /credit_hard_cap_attested/);
    assert.match(page, /cannot\s+bill\s+me\s+beyond\s+the\s+free\s+credits/);
    // Bulk approval and rules stay free-only and reset the class.
    assert.match(controller, /'cost_class' => 'free'/);
    assert.doesNotMatch(page, /enable[_ -]?paid fallback/i);
});
