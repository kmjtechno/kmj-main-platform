import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
const read = (path) =>
    readFileSync(new URL('../' + path, import.meta.url), 'utf8');
test('shared app pages use the owner shell only for server-verified owners', () => {
    const source = read('resources/js/layouts/app-layout.tsx');
    assert.match(source, /operator\.enabled === true/);
    assert.match(source, /if \(isOwner\)/);
    assert.match(source, /<OwnerModuleShell>\{children\}<\/OwnerModuleShell>/);
    assert.match(source, /<AppLayoutTemplate breadcrumbs=\{breadcrumbs\}>/);
    assert.doesNotMatch(source, /is_platform_owner|owner_email/);
});
test('owner theme applies to shared settings without customer global overrides', () => {
    const css = read('resources/css/owner-module-shell.css');
    assert.match(css, /\.owner-module-shell \{[\s\S]*?color-scheme: dark/);
    assert.match(css, /--card: #0b1016/);
    assert.doesNotMatch(css, /radial-gradient/);
});
test('browser favicon preserves the original emblem with a visible backplate', () => {
    const old = read('public/favicon.svg');
    const icon = read('public/favicon-contrast-v1.svg');
    assert.equal(
        icon.match(/href="([^"]+)"/)[1],
        old.match(/href="([^"]+)"/)[1],
    );
    assert.match(icon, /<rect[^>]+fill="#f5f7fa"/);
    assert.match(
        read('resources/views/app.blade.php'),
        /href="\/favicon-contrast-v1.svg"/,
    );
});
