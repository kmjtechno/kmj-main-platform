import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) =>
    readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const registry = read('app/Services/Operator/OperatorModules.php');
const sidebar = read('resources/js/components/app-sidebar.tsx');
const inertia = read('app/Http/Middleware/HandleInertiaRequests.php');

const entries = [...registry.matchAll(/'id' => '([^']+)'/g)].map((m) => m[1]);
const icons = [...registry.matchAll(/'icon' => '([^']+)'/g)].map((m) => m[1]);
const hrefs = [...registry.matchAll(/'href' => '([^']+)'/g)].map((m) => m[1]);

void test('module registry has unique ids and only operator hrefs', () => {
    assert.ok(entries.length >= 6);
    assert.equal(new Set(entries).size, entries.length);
    assert.equal(hrefs.length, entries.length);
    for (const href of hrefs) {
        assert.match(href, /^\/operator(\/[a-z-]+|#[a-z-]+)?$/);
    }
});

void test('every registry icon has a mapped sidebar icon', () => {
    const map = sidebar.slice(
        sidebar.indexOf('const operatorIcons'),
        sidebar.indexOf('export function AppSidebar'),
    );
    for (const icon of icons) {
        assert.ok(
            new RegExp(`\\b${icon}\\b`).test(map),
            `${icon} missing in operatorIcons`,
        );
    }
});

void test('modules are shared only behind the platform owner guard', () => {
    assert.ok(
        inertia.includes("'modules' => $enabled ? OperatorModules::all() : []"),
    );
    assert.ok(
        inertia.includes('app(PlatformOwnerAccess::class)->allows($user)'),
    );
});
