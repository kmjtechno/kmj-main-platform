import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(
    new URL('../resources/js/layouts/owner-module-shell.tsx', import.meta.url),
    'utf8',
);

void test('owner mobile nav Escape returns focus to the visible trigger', () => {
    assert.match(source, /useRef<HTMLButtonElement>\(null\)/);
    assert.match(source, /ref=\{menuButton\}/);
    assert.match(source, /if \(event\.key !== 'Escape'\) return;/);
    assert.match(source, /setNavOpen\(false\);\s*menuButton\.current\?\.focus\(\)/);
    assert.match(source, /\}, \[navOpen\]\);/);
});

void test('owner mobile nav announces its current expanded action', () => {
    assert.match(source, /aria-expanded=\{navOpen\}/);
    assert.match(
        source,
        /aria-label=\{navOpen \? 'Close owner navigation' : 'Open owner navigation'\}/,
    );
    assert.match(source, /aria-controls="owner-module-navigation"/);
});

void test('closing on existing navigation links remains enabled', () => {
    assert.match(source, /onClick=\{\(\) => setNavOpen\(false\)\}/);
    assert.match(source, /href="\/operator"/);
    assert.match(source, /id="owner-main"/);
});
