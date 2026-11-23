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

void test('KMJ Mail renders exactly one inherited shell for owner and staff', () => {
    const appEntry = read('resources/js/app.tsx');
    const mailPage = read('resources/js/pages/mail-center.tsx');

    // Inertia mounts AppLayout for mail-center once, and its owner branch
    // renders OwnerModuleShell. A second page-level AppLayout caused the
    // duplicate branding/header/sidebar visible on the live mail screenshot.
    assert.match(appEntry, /default:\s*return AppLayout;/);
    assert.match(layout, /if \(isOwner\)/);
    assert.match(layout, /<OwnerModuleShell>/);
    assert.doesNotMatch(mailPage, /<AppLayout\b|<OwnerModuleShell\b/);
    assert.doesNotMatch(mailPage, /import AppLayout from/);
    assert.match(mailPage, /data-test="kmj-native-mail"/);
    assert.match(mailPage, /owner-admin-page kmj-admin-shell/);
    assert.match(mailPage, /<Head title="KMJ Mail/);
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

void test('KMJ Mail enterprise inbox controls operate on real mailbox records', () => {
    const source = read('resources/js/pages/mail-center.tsx');
    assert.match(source, /'archive', label: 'Archive'/);
    assert.match(source, /'starred', label: 'Starred'/);
    assert.match(source, /base \+ '\/messages\/manage'/);
    assert.match(source, /selectedIds\.length > 0/);
    assert.match(source, /mailbox\.total > mailbox\.page_size/);
    assert.match(source, /forwardMessage/);
    assert.match(source, /aria-label="Select all visible messages"/);
    assert.match(source, /External inbound\s+is not active/);
    assert.doesNotMatch(source, /Gmail inbox synced|External inbox connected/);
});

void test('KMJ Mail premium workspace replaces oversized empty reader with actionable controls', () => {
    const source = read('resources/js/pages/mail-center.tsx');
    assert.match(source, /KMJ TECHNO \/ COMMUNICATIONS/);
    assert.match(source, /Mail that means business|Your next conversation starts here/);
    assert.match(source, /Open latest message/);
    assert.match(source, /onClick=\{startCompose\}/);
    assert.match(source, /navigate\(folder, mailbox\.items\[0\]\.id, q, mailbox\.page\)/);
    assert.match(source, /owner-admin-page kmj-admin-shell/);
    assert.match(source, /mailbox\.total/);
    assert.match(source, /item\.delivery_state === 'failed'/);
    assert.match(source, /Internet inbound: Not connected/);
    assert.doesNotMatch(source, /Private\. Clear\. In control\./);
    assert.doesNotMatch(source, /Gmail inbox synced|External inbox connected/);
});
