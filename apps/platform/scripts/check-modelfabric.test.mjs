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

void test('sticky sessions only reorder routes the plan already admitted', () => {
    const gateway = read('app/Services/AiProviders/ModelFabricGateway.php');
    const api = read('app/Http/Controllers/ModelFabricApiController.php');
    assert.match(gateway, /preferSticky\(\$plan\['routes'\]/);
    assert.match(gateway, /Sticky sessions are a preference only/);
    assert.match(api, /X-ModelFabric-Session/);
    assert.match(api, /\[A-Za-z0-9\._:-\]\{1,64\}/);
});

void test('API tokens tab shows a copy-ready connect guide without persisting the token', () => {
    const page = read('resources/js/pages/operator-modelfabric.tsx');
    assert.match(page, /function ConnectGuide/);
    assert.match(page, /modelfabric-connect-guide/);
    assert.match(page, /modelfabric-auto/);
    assert.match(page, /<ConnectGuide origin=\{origin\} token=\{newToken\}/);
    assert.doesNotMatch(page, /localStorage|sessionStorage/);
});

void test('Overview lists expiring approvals, unhealthy providers and expiring tokens as a to-do', () => {
    const page = read('resources/js/pages/operator-modelfabric.tsx');
    assert.match(page, /modelfabric-todo/);
    assert.match(page, /expire within 7 days/);
    assert.match(page, /no longer routed/);
    assert.match(page, /not healthy/);
    assert.doesNotMatch(page, /localStorage|sessionStorage/);
});

void test('token form warns when a private-source token could not route anything', () => {
    const page = read('resources/js/pages/operator-modelfabric.tsx');
    assert.match(page, /useState\(privateReady\)/);
    assert.match(page, /modelfabric-private-warning/);
    assert.match(page, /Untick Private source/);
});

void test('provider errors are explained in plain language with a next step', () => {
    const page = read('resources/js/pages/operator-modelfabric.tsx');
    assert.match(page, /const errorHelp/);
    assert.match(page, /Check token permissions/);
    assert.match(page, /modelfabric-error-help/);
    assert.match(page, /startsWith\('invalid_catalog'\)/);
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
    const providerPage = read('resources/js/pages/services/ai-providers.tsx');
    assert.match(page, /<AiProviders\s+embedded/);
    assert.match(
        providerPage,
        /embedded \? \{ return_to: 'modelfabric' \} : \{\}/,
    );
    assert.match(
        providerPage,
        /free_account_confirmed: true, return_to: 'modelfabric'/,
    );
    assert.match(hf, /modelfabric_provider_tab/);
    assert.match(or, /modelfabric_provider_tab/);
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

void test('GitHub Models is retired and cannot admit inference', () => {
    const config = read('config/ai_providers.php');
    const adapter = read(
        'app/Services/AiProviders/OpenAiCompatibleAdapter.php',
    );
    assert.match(
        config,
        /'github' => \['label' => 'GitHub Models \(retired\)', 'base_url' => 'https:\/\/models\.github\.ai\/inference', 'free_tier' => 'none', 'retired' => true\]/,
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

void test('ModelFabric guided flow keeps outbound prompts explicit and owner controlled', () => {
    const page = read('resources/js/pages/operator-modelfabric.tsx');
    const playground = read(
        'resources/js/components/modelfabric-safe-playground.tsx',
    );
    const api = read('app/Http/Controllers/ModelFabricApiController.php');

    assert.match(page, /modelfabric-setup-journey/);
    assert.match(page, /setupJourney\.map/);
    assert.match(page, /'playground'/);
    assert.match(page, /<ModelFabricSafePlayground/);
    assert.match(page, /hasActiveToken=\{activeTokens > 0\}/);
    assert.match(playground, /data-testid="modelfabric-safe-playground"/);
    assert.match(playground, /data-testid="modelfabric-check-token"/);
    assert.match(playground, /data-testid="modelfabric-send-test"/);
    assert.match(playground, /!canChat/);
    assert.match(playground, /consent &&/);
    assert.match(playground, /MAX_PROMPT_CHARS = 1000/);
    assert.match(playground, /redirect: 'error'/);
    assert.match(playground, /mode: 'same-origin'/);
    assert.match(playground, /credentials: 'same-origin'/);
    assert.match(playground, /cache: 'no-store'/);
    assert.match(playground, /Authorization: 'Bearer ' \+ apiKey\.trim\(\)/);
    assert.match(
        playground,
        /API_ROOT \+ \(sendPrompt \? '\/chat\/completions' : '\/models'\)/,
    );
    assert.match(playground, /NO_FREE_ROUTE_AVAILABLE/);
    assert.match(playground, /new AbortController/);
    assert.match(playground, /inFlight\.current\?\.abort/);
    assert.doesNotMatch(
        playground,
        /localStorage\.(?:getItem|setItem)|sessionStorage\.(?:getItem|setItem)/,
    );
    assert.doesNotMatch(
        playground,
        /https:\/\/api\.openai\.com|openrouter\.ai\/api/,
    );
    assert.match(api, /ignored on purpose/);
});

void test('Playground checks an existing ModelFabric token without creating keys or bypassing routing', () => {
    const playground = read(
        'resources/js/components/modelfabric-safe-playground.tsx',
    );
    assert.match(playground, /'\/api\/modelfabric\/v1'/);
    assert.match(playground, /'modelfabric-auto'/);
    assert.match(playground, /!routeReady/);
    assert.match(playground, /verifiedRoutes > 0/);
    assert.match(playground, /No requests run automatically/);
    assert.match(playground, /owner-initiated/i);
    assert.doesNotMatch(playground, /fetch\(.*(?:https?:\/\/|provider_url)/);
    assert.match(
        read('routes/model-fabric-api.php'),
        /AuthenticateModelFabricToken::class/,
    );
    assert.match(
        read('app/Http/Controllers/ModelFabricApiController.php'),
        /\$this->gateway->complete\(/,
    );
});

void test('connection samples do not embed the issued bearer or claim unsupported APIs', () => {
    const guide = page.slice(
        page.indexOf('function ConnectGuide'),
        page.indexOf('export default function OperatorModelFabric'),
    );
    assert.match(guide, /KMJ_MODELFABRIC_TOKEN/);
    assert.match(guide, /read-only model check/);
    assert.match(guide, /native Responses, tool calling/);
    assert.doesNotMatch(guide, /const key = token|\$\{key\}/);
    const api = read('app/Http/Controllers/ModelFabricApiController.php');
    assert.match(api, /\$token->private_source \? 'code' : 'chat'/);
});

void test('secure coding UI never declares source transfer ready from model evidence plus token alone', () => {
    const api = read('app/Http/Controllers/ModelFabricApiController.php');
    assert.match(page, /Activation pending/);
    assert.doesNotMatch(page, /Route and token ready/);
    assert.match(page, /account billing proof/);
    assert.match(page, /single-use admission ticket/);
    assert.match(page, /explicit source-transfer consent/);
    assert.match(api, /native_admission_required/);
    assert.match(
        api,
        /\$token->private_source && \(! \$strictFreeCloud \|\| \$nativeRoute === null\)/,
    );
});

void test('secure coding token guide excludes bare SDK completions and explains native admission', () => {
    assert.match(page, /data-testid="modelfabric-coding-connect-warning"/);
    assert.match(
        page,
        /Secure coding tokens cannot use a bare OpenAI SDK\s+completion/,
    );
    assert.match(page, /request-bound single-use native admission ticket/);
    assert.match(page, /id: 'coding-preflight'/);
    assert.match(page, /X-ModelFabric-Policy: strict-free-cloud/);
    assert.match(
        page,
        /const snippets: \{ id: string; label: string; code: string \}\[\] = coding/,
    );
});

void test('guided readiness separates general chat from secure coding and gates unusable tokens', () => {
    assert.match(page, /modelfabric-workflow-readiness/);
    assert.match(page, /token.active && !token.private_source/);
    assert.match(page, /token.active && token.private_source/);
    assert.match(page, /if \(!generalReady\)/);
    assert.match(page, /if \(chatTokens === 0\)/);
    assert.match(page, /complete: okRequests24h > 0/);
    assert.match(page, /A chat token cannot authorize\s+private\s+source/);
    assert.match(
        page,
        /disabled=\{\s*tokenPrivate\s*\?\s*!privateReady\s*:\s*!generalReady\s*\}/,
    );
    assert.match(page, /Never submit\s+private code using a chat token/);
    assert.doesNotMatch(
        page,
        /Create an API token so the coding worker can use these routes/,
    );
});

void test('provider management has a dedicated tab, repair action and progressive disclosure', () => {
    assert.match(page, /\{ key: 'providers', label: 'AI workspace' \}/);
    assert.match(page, /tab === 'providers'/);
    assert.match(page, /reconnect the provider and run Test connection/);
    assert.match(
        page,
        /<summary[^>]*>\s*Usage and routing limits\s*<\/summary>/,
    );
    assert.match(page, /p.models.length === 0/);
    // A disabled provider can never count as healthy: readiness only counts enabled + ok.
    assert.match(page, /\(p\) => p\.enabled && p\.health === 'ok'/);
});

void test('premium guided setup keeps chat and coding journeys separate', () => {
    assert.match(page, /const codingJourney: typeof chatJourney/);
    assert.match(page, /workflow === 'coding' \? codingJourney : chatJourney/);
    assert.match(page, /setTokenPrivate\(workflow === 'coding'\)/);
    assert.match(page, /aria-pressed=\{\s*workflow === mode\s*\}/);
    assert.match(page, /aria-valuenow=\{completedSteps\}/);
    assert.match(page, /index === activeStep/);
    assert.match(page, /Routing diagnostics &amp;\s+provider\s+eligibility/);
    assert.match(page, /Secure coding · next step/);
});

void test('worker verification remains pending without device evidence', () => {
    assert.match(
        page,
        /title: 'Connect and verify the worker',[\s\S]*?complete: false/,
    );
    assert.match(
        page,
        /Source consent and real worker execution still need separate verification/,
    );
    assert.match(page, /href: '\/services\/kmj-codebridge'/);
    assert.match(
        page,
        /Changing the purpose never carries forward another attestation/,
    );
    assert.match(page, /setConfirmed\(false\)/);
});

void test('provider setup stays inside the native ModelFabric workspace', () => {
    const controller = read('app/Http/Controllers/ModelFabricController.php');
    const providerPage = read('resources/js/pages/services/ai-providers.tsx');
    assert.doesNotMatch(page, /\/services\/kmj-codebridge\/ai-providers/);
    assert.match(page, /\/operator\/modelfabric\?tab=providers/);
    assert.match(page, /renderRoutingControls=\{\(id\) =>/);
    assert.doesNotMatch(page, /title="Routing controls"/);
    assert.match(
        providerPage,
        /routingControls=\{renderRoutingControls\?\.\(\s*provider\.id,?\s*\)\}/,
    );
    assert.match(providerPage, /\{routingControls\}/);
    assert.match(providerPage, /Connect or reconnect a provider/);
    assert.match(page, /presets=\{providerPresets\}/);
    assert.match(controller, /'providerPresets' => collect/);
    assert.match(controller, /modelfabric_provider_tab/);
    assert.match(
        providerPage,
        /embedded \? 'provider-connections' : undefined/,
    );
    assert.match(providerPage, /!embedded && <Head/);
});

void test('one-click provider inference proof requires public consent and existing zero-spend reservation', () => {
    const gateway = read('app/Services/AiProviders/ModelFabricGateway.php');
    const providers = read('resources/js/pages/services/ai-providers.tsx');
    assert.match(routes, /providers\/\{provider\}\/inference-check/);
    assert.match(routes, /throttle:3,10/);
    assert.match(controller, /public function verifyInference/);
    assert.match(controller, /'public_prompts_confirmed' => \['accepted'\]/);
    assert.match(controller, /gateway->completeSelected/);
    assert.match(gateway, /selectedRoute:/);
    assert.match(providers, /Run one bounded synthetic inference/);
});
