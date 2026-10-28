import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const script = readFileSync(
    new URL('./browser-preview-verify.mjs', import.meta.url),
    'utf8',
);

void test('visual preview covers locked pages and real owner Operations shell through ultrawide responsive widths', () => {
    assert.match(
        script,
        /for \(const width of \[320, 390, 768, 1170, 1440, 1536, 1920, 2560\]\)/,
    );
    assert.match(script, /\['landing', '\/'\]/);
    assert.match(script, /\['super-admin', '\/super-admin'\]/);
    assert.match(script, /\['owner-ops', '\/operator\/ops'\]/);
    assert.match(script, /Real Operations component missing/);
    assert.match(script, /Owner CodeBridge controls missing/);
    assert.match(script, /Real device control component missing/);
    assert.match(script, /chromiumSandbox: true/);
    assert.match(script, /Old customer workspace leaked into owner page/);
    assert.match(script, /Exactly one current owner module required/);
    assert.match(script, /if \(width <= 390\)/);
    assert.match(script, /name: 'Toggle owner navigation'/);
    assert.match(script, /Owner mobile menu Escape focus not restored/);
    assert.match(script, /Signed-out Login CTA missing or outside viewport/);
    assert.match(script, /Signed-out Register CTA missing or outside viewport/);
    assert.match(script, /Landing canvas must fill the viewport width/);
    assert.match(script, /Owner Command OS must fill the viewport width/);
});

void test('preview fails on broken assets or horizontal overflow, never real owner login', () => {
    assert.match(script, /localhost/);
    assert.match(script, /127\.0\.0\.1/);
    assert.match(script, /Preview verification is restricted to loopback/);
    assert.match(script, /response\.status\(\) === 200/);
    assert.match(script, /!broken\.length/);
    assert.match(script, /!overflow/);
    assert.match(script, /!errors\.length/);
    assert.doesNotMatch(script, /\/operator\/login|\/api\/login/);
});

void test('owner Operations preview is synthetic-only and renders the real owner component', () => {
    const fixture = readFileSync(
        new URL('../visual/entry.tsx', import.meta.url),
        'utf8',
    );
    assert.match(fixture, /function OwnerOpsPreview\(/);
    assert.match(fixture, /<OwnerModuleShell>/);
    assert.match(fixture, /<OperatorOps/);
    assert.match(fixture, /ownerOps\s*\?\s*'operator-ops'/);
    assert.match(fixture, /\['\/operator', '\/super-admin'\]\.includes/);
    assert.match(fixture, /registration_available: false/);
    assert.match(fixture, /: null,/);
    assert.match(fixture, /environment: 'synthetic-preview'/);
    assert.match(fixture, /status: 'unknown'/);
    assert.doesNotMatch(fixture, /fetch\(|router\.post\(|APP_KEY|\.env/);
});
