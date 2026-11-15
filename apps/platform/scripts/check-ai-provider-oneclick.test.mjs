/** KMJ AI Provider One-Click Connect — offline, no credentials or network. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (path) => readFileSync(resolve(root, path), 'utf8');
const page = read('resources/js/pages/services/ai-providers.tsx');
const hub = read('resources/js/components/ai-provider-connect-hub.tsx');
const css = read('resources/css/ai-provider-connect.css');
const controller = read('app/Http/Controllers/AiProviderController.php');
const routes = read('routes/ai-providers.php');
const oauth = read('app/Services/AiProviders/OpenRouterConnect.php');
const manager = read('app/Services/AiProviders/ProviderManager.php');

void test('OpenRouter account click starts real protected PKCE route once', () => {
    assert.match(page, /onConnectOpenRouter=\{startOpenRouter\}/);
    assert.match(page, /router\.post\(BASE \+ '\/connect\/openrouter'/);
    assert.match(page, /if \(oauthBusy\) return/);
    assert.match(hub, /aria-busy=\{oauthBusy\}/);
    assert.match(routes, /connect\/openrouter.*password\.confirm/);
    assert.match(oauth, /code_challenge_method/);
    assert.match(oauth, /code_verifier/);
    assert.match(oauth, /CURLOPT_RESOLVE/);
});

void test('other providers use only exact official key pages, no fake OAuth', () => {
    assert.match(hub, /https:\/\/console\.groq\.com\/keys/);
    assert.match(hub, /https:\/\/aistudio\.google\.com\/apikey/);
    assert.match(hub, /https:\/\/console\.mistral\.ai\/api-keys\//);
    assert.match(hub, /https:\/\/huggingface\.co\/settings\/tokens/);
    assert.match(hub, /Get key &amp; connect/);
    assert.match(hub, /rel="noopener noreferrer"/);
    assert.match(hub, /onChooseKeyProvider\(guide\.key\)/);
    assert.doesNotMatch(
        hub,
        /connect\/groq\/callback|connect\/gemini\/callback/,
    );
});

void test('one-action guided key connection verifies only read-only models', () => {
    assert.match(page, /verify_connection: true/);
    assert.match(page, /Save & verify connection/);
    assert.match(
        controller,
        /'verify_connection' => \['sometimes', 'boolean'\]/,
    );
    assert.match(controller, /manager->test\(\$created\)/);
    assert.match(manager, /GET \{base\}\/models|GET \/models/);
    assert.match(controller, /verifiedFreeModels/);
    assert.match(controller, /free model\(s\)/);
});

void test('unverified model or failed OAuth never produces fake success', () => {
    assert.match(controller, /Authorization was declined or canceled/);
    assert.match(controller, /verification is pending/);
    assert.match(controller, /Inference remains blocked/);
    assert.match(controller, /str_ends_with\(\$model, ':free'\)/);
    assert.match(
        controller,
        /manager->update\(\$tested, \['default_model' => \$free\[0\]\]\)/,
    );
    assert.match(controller, /No inference enabled/);
});

void test('ownership, session-bound OAuth and no paid overrides remain in place', () => {
    assert.match(controller, /scope\['can_manage'\]/);
    assert.match(controller, /session\(\)->pull\('ai_provider_oauth'\)/);
    assert.match(controller, /session\(\)->put\('ai_provider_oauth'/);
    assert.match(controller, /'free_only' => \['prohibited'\]/);
    assert.match(manager, /'free_only' => true/);
    assert.match(manager, /assertInferenceAllowed/);
});

void test('owner enterprise styles are scoped and inputs remain accessible', () => {
    assert.match(
        page,
        /import '\.\.\/\.\.\/\.\.\/css\/ai-provider-connect\.css'/,
    );
    assert.match(page, /className="kmj-ai-providers flex/);
    assert.match(css, /\.owner-module-shell \.kmj-ai-providers/);
    assert.match(css, /focus-visible/);
    assert.match(css, /prefers-reduced-motion/);
    assert.match(css, /min-height: 44px/);
    assert.doesNotMatch(css, /^(?:html|body)\s*\{/m);
});
