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
    assert.match(page, /router\.post\(\s*BASE\s*\+\s*'\/connect\/openrouter'/);
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
    assert.match(hub, /Connect \{guide\.title\}/);
    assert.match(hub, /rel="noopener noreferrer"/);
    assert.match(hub, /onChooseKeyProvider\(guide\.key\)/);
    assert.doesNotMatch(
        hub,
        /connect\/groq\/callback|connect\/gemini\/callback/,
    );
});

void test('one-action guided key connection verifies only read-only models', () => {
    assert.match(page, /verify_connection: true/);
    assert.match(page, /Save & verify \$\{selected\?\.label/);
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

void test('catalog-only and paid models never enter free selectable defaults', () => {
    const ui = read('resources/js/pages/services/ai-providers.tsx');
    assert.match(
        manager,
        /public function admittedFreeModels\(AiProvider \$provider\): array/,
    );
    assert.match(manager, /FreePolicy::inferenceAllowed/);
    assert.match(manager, /\$known = \$this->admittedFreeModels\(\$provider\)/);
    assert.match(
        manager,
        /'models' => \$this->admittedFreeModels\(\$provider\)/,
    );
    assert.match(manager, /discovered_model_count/);
    assert.match(ui, /Verified-free default model/);
    assert.match(ui, /Verified-free fallback models/);
    assert.match(ui, /Paid and unknown-price models cannot be selected/);
});

void test('Official key launcher resumes secure form safely', () => {
    assert.match(hub, /onChooseKeyProvider\(guide\.key\)/);
    assert.match(hub, /data-selected=\{\s*selectedPreset\s*===\s*guide\.key/);
    assert.match(hub, /Connect \{guide\.title\}/);
    assert.match(page, /setPreferredPreset\(\(prev\) =>/);
    assert.match(page, /preferredPreset\.key/);
    assert.match(page, /window\.requestAnimationFrame/);
    assert.match(page, /formRef\.current\?\.scrollIntoView/);
    assert.match(page, /keyInputRef\.current\?\.focus/);
    assert.match(page, /ref=\{keyInputRef\}/);
    assert.match(page, /Finish \{selected\?\.label/);
    assert.match(page, /verify_connection: true/);
    assert.doesNotMatch(
        hub,
        /localStorage|sessionStorage|document\.cookie|navigator\.clipboard/,
    );
});

void test('configured providers use honest summary and deliberate advanced controls', () => {
    assert.match(page, /discovered_model_count/);
    assert.match(page, /verified-free models/);
    assert.match(page, /Inference blocked until verified-free admission/);
    assert.match(page, /const \[expanded, setExpanded\] = useState\(false\)/);
    assert.match(page, /aria-expanded=\{expanded\}/);
    assert.match(page, /\{expanded && \(/);
    assert.match(page, /\{canManage && replaceVisible && \(/);
    assert.match(page, /window\.confirm/);
    assert.match(page, /data: \{ confirm: 'DELETE' \}/);
    assert.match(page, /fallback_models: next/);
    assert.match(page, /\{ api_key: newKey \}/);
    assert.match(page, /onSuccess:\s*\(\)\s*=>\s*\{\s*setNewKey\(''\);/);
    assert.match(page, /setReplaceVisible\(\s*false,\s*\);/);
});

void test('API-key setup is progressive instead of a permanently open form', () => {
    assert.match(
        page,
        /const \[showKeyForm, setShowKeyForm\] = useState\(false\)/,
    );
    assert.match(page, /setShowKeyForm\(true\)/);
    assert.match(page, /\{showKeyForm \? \(/);
    assert.match(page, /Close key setup/);
    assert.match(
        page,
        /setShowKeyForm\(false\);\s*setPreferredPreset\(null\);/,
    );
    assert.match(page, /Connect another provider using an API key/);
    assert.match(page, /<AddProvider/);
});

void test('draft secrets clear when provider or key editor changes', () => {
    assert.match(page, /lastPreferredSelection\.current/);
    assert.match(page, /onManualProviderChange/);
    assert.match(page, /setApiKey\(''\)/);
    assert.match(page, /setReplaceVisible\(false\)/);
    assert.match(page, /setNewKey\(''\)/);
    const browser = read('scripts/browser-preview-verify.mjs');
    assert.match(browser, /Key persisted across provider cards/);
    assert.match(browser, /Key persisted across manual preset change/);
    assert.match(browser, /Cancelled replacement key was retained/);
});

void test('empty provider view remains cloud-only with strict zero-spend policy', () => {
    assert.match(page, /No cloud AI providers connected/);
    assert.match(page, /inference stays blocked/);
    assert.doesNotMatch(page, /Local Ollama|local LLM/i);
});
