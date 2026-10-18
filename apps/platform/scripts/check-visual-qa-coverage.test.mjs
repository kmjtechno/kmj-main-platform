import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const script = readFileSync(
    new URL('./browser-preview-verify.mjs', import.meta.url),
    'utf8',
);

void test('visual preview covers both locked pages at six responsive widths', () => {
    assert.match(
        script,
        /for \(const width of \[320, 390, 768, 1170, 1440, 1536\]\)/,
    );
    assert.match(script, /\['landing', '\/'\]/);
    assert.match(script, /\['super-admin', '\/operator'\]/);
    assert.match(script, /if \(width <= 390\)/);
    assert.match(script, /name: 'Toggle owner navigation'/);
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
