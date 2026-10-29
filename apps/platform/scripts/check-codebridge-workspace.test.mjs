import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const page = readFileSync(
    'resources/js/pages/services/codebridge-workspace.tsx',
    'utf8',
);
const controller = readFileSync(
    'app/Http/Controllers/CodeBridgeWorkspaceController.php',
    'utf8',
);
const routes = readFileSync('routes/codebridge-workspace.php', 'utf8');
const web = readFileSync('routes/web.php', 'utf8');

void test('workspace route is registered inside the authenticated group', () => {
    assert.match(routes, /services\/kmj-codebridge\/workspace/);
    const auth = web.indexOf("Route::middleware(['auth', 'verified'])");
    assert.ok(
        auth >= 0 &&
            web.indexOf("require __DIR__.'/codebridge-workspace.php'") > auth,
    );
});

void test('workspace never invents progress, replies or paid capability', () => {
    const withoutClasses = page.replace(
        /className=\{?("[^"]*"|`[^`]*`)\}?/g,
        '',
    );
    assert.doesNotMatch(withoutClasses, /\b\d{1,3}\s?%/);
    assert.doesNotMatch(
        page,
        /12 of 18|GPT-4o|unlimited|Math\.random|setTimeout/i,
    );
    assert.match(page, /disabled/);
    assert.match(page, /not verified/);
});

void test('controller exposes no secrets and marks missing backends unavailable', () => {
    assert.doesNotMatch(controller, /api_key/);
    for (const key of ['job_events'])
        assert.match(
            controller,
            new RegExp(`'${key}' => \\[\\s*'available' => false`),
        );
});

void test('device pairing stays in the Control Center', () => {
    assert.match(page, /#devices/);
    // The page may only post to workspace conversation endpoints.
    for (const call of page.match(/router\.post\(\s*[^,]+/g) ?? [])
        assert.match(call, /BASE|conversationUrl/, call);
    assert.doesNotMatch(page, /device-pairings|device-enrollments/);
});

void test('chat routes are authenticated, throttled and ULID/UUID constrained', () => {
    assert.match(routes, /whereUuid\('conversation'\)/);
    assert.match(routes, /whereUlid\('message'\)/);
    assert.equal((routes.match(/throttle:/g) ?? []).length >= 5, true);
});
