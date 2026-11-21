import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const read = (path) =>
    readFileSync(new URL('../' + path, import.meta.url), 'utf8');

const layout = read('resources/js/layouts/app-layout.tsx');
const shell = read('resources/js/layouts/owner-module-shell.tsx');
const command = read('resources/js/components/operator-command-os.tsx');
const shellCss = read('resources/css/owner-module-shell.css');

const ownerPages = [
    'operator-products.tsx',
    'operator-directory.tsx',
    'operator-payments.tsx',
    'operator-kslp.tsx',
    'operator-ops.tsx',
    'operator-codebridge-owner.tsx',
];

void test('all protected owner modules inherit one locked Command Center shell', () => {
    assert.match(layout, /if \(isOwner\)/);
    assert.match(layout, /<OwnerModuleShell>/);
    assert.match(shell, /data-owner-design="command-center-v1"/);
    assert.match(shell, /owner-lock owner-module-shell/);
    assert.match(shell, /<LockedBrand/);
    for (const file of ownerPages) {
        const source = read('resources/js/pages/' + file);
        assert.match(
            source,
            /owner-admin-page kmj-admin-shell|owner-product-workspace owner-admin-page kmj-admin-shell/,
        );
        assert.match(source, /owner-admin-hero kmj-admin-hero/);
        assert.match(source, /<Head title=/);
        assert.match(source, /<OperatorModuleNavigation active=/);
    }
    assert.match(command, /owner-hero/);
    assert.match(command, /owner-panel/);
});

void test('one canonical Licensing Hub is shown in the owner sidebar', () => {
    const groups = shell.slice(0, shell.indexOf('export default function'));
    assert.equal((groups.match(/href: '\/operator\/kslp'/g) ?? []).length, 1);
    assert.match(groups, /label: 'KMJ Licensing Hub'/);
    assert.doesNotMatch(groups, /href: '\/developer\/apps'/);
    assert.doesNotMatch(groups, /label: 'Subscriptions & Plans'/);
    const hub = read('resources/js/pages/operator-kslp.tsx');
    assert.match(hub, /<DeveloperAppsWorkspace [\s\S]*?embedded/);
    assert.match(hub, /Apps, Keys & SDK/);
});

void test('products, payments, people and CodeBridge use one content width and metric scale', () => {
    for (const file of ownerPages) {
        const source = read('resources/js/pages/' + file);
        assert.doesNotMatch(source, /className="kmj-admin-shell min-h-screen/);
        assert.doesNotMatch(source, /className="mx-auto w-full max-w-6xl"/);
        assert.doesNotMatch(source, /className="mx-auto max-w-7xl"/);
        assert.match(source, /min-w-0/);
    }
    assert.match(
        shellCss,
        /\.owner-module-shell \.owner-admin-page \.owner-admin-hero h1/,
    );
    assert.match(shellCss, /--owner-surface-1:/);
    assert.match(shellCss, /--owner-line:/);
});

void test('shared CodeBridge, AI and security settings preserve customer theme', () => {
    for (const file of [
        'services/codebridge.tsx',
        'services/ai-providers.tsx',
    ]) {
        assert.match(read('resources/js/pages/' + file), /owner-admin-surface/);
    }
    for (const file of ['profile.tsx', 'security.tsx', 'appearance.tsx']) {
        assert.match(
            read('resources/js/pages/settings/' + file),
            /owner-admin-settings/,
        );
    }
    assert.match(
        shellCss,
        /\.owner-module-shell \.owner-module-content \.owner-admin-surface/,
    );
    assert.match(shellCss, /\.owner-module-shell \.owner-admin-settings/);
    assert.doesNotMatch(shellCss, /(^|\n)\s*\.owner-admin-settings\s*\{/);
    assert.doesNotMatch(shellCss, /(^|\n)\s*\.owner-admin-surface\s*\{/);
});

void test('mobile and accessible one-dashboard styles remain locked', () => {
    assert.match(shell, /aria-current=/);
    assert.match(shell, /aria-label=/);
    assert.match(shellCss, /@media \(max-width: 700px\)/);
    assert.match(shellCss, /prefers-reduced-motion: reduce/);
    assert.match(shellCss, /focus-visible/);
    assert.match(shellCss, /min-height: 42px/);
});
