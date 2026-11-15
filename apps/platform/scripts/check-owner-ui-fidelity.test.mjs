/**
 * KMJ TECHNO locked Enterprise Command OS / Super Admin fidelity contracts.
 * Static regression only: no credentials, browser login, server or production mutations.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (path) => readFileSync(resolve(root, path), 'utf8');
const shell = read('resources/js/layouts/owner-module-shell.tsx');
const app = read('resources/js/app.tsx');
const os = read('resources/js/components/operator-command-os.tsx');
const css = read('resources/css/owner-module-shell.css');
const bridge = read('resources/js/pages/services/codebridge.tsx');
const device = read(
    'resources/js/components/codebridge/device-control-center.tsx',
);
const premium = read('resources/css/codebridge-premium.css');

void test('locked owner route does not fall back to customer sidebar', () => {
    assert.match(app, /name\.startsWith\('operator-'\)/);
    assert.match(app, /return OwnerModuleShell/);
    const layout = read('resources/js/layouts/app-layout.tsx');
    assert.match(layout, /const isOwner/);
    assert.match(layout, /if \(isOwner\)[\s\S]*?OwnerModuleShell/);
});

void test('owner brand, verified existing identity and 3 navigation sections remain', () => {
    assert.match(shell, /LockedBrand compact/);
    assert.match(shell, /Platform Owner \/ Super Admin/);
    for (const group of ['BUSINESS', 'PLATFORM', 'OPERATIONS']) {
        assert.ok(shell.includes("title: '" + group + "'"));
    }
    assert.match(shell, /href="\/super-admin"/);
    assert.match(shell, /href="\/operator"/);
    assert.match(shell, /href\.split\('#'\)\[0\] === url/);
});

void test('original locked dashboard earth hero, product gallery and Kristi panel are retained', () => {
    assert.match(os, /owner-earth\.webp/);
    assert.match(os, /Product Suite Overview/);
    assert.match(os, /owner-product-track/);
    assert.match(os, /KristiOwnerAssistant/);
    assert.match(os, /\/assets\/locked\//);
});

void test('shared owner shell uses readable typography and scoped dark enterprise colors', () => {
    assert.match(css, /Locked Owner\/Super Admin subpage fidelity/);
    assert.match(css, /font-size: 14px;/);
    assert.match(css, /\.owner-module-shell \.owner-sidebar nav > a/);
    assert.match(css, /\.owner-module-shell \.kmj-admin-tab/);
    assert.match(css, /min-height: 44px;/);
    assert.match(css, /@media \(max-width: 700px\)/);
    assert.doesNotMatch(css, /^(?:html|body)\s*\{/m);
});

void test('CodeBridge page imports premium CSS within real authenticated owner content', () => {
    assert.match(
        bridge,
        /import '\.\.\/\.\.\/\.\.\/css\/codebridge-premium\.css';/,
    );
    assert.match(bridge, /className="kmj-codebridge-premium flex/);
    assert.match(premium, /owner-earth\.webp/);
    assert.match(
        premium,
        /\.kmj-codebridge-premium :is\(\.text-xs, \.text-sm\)/,
    );
    assert.match(premium, /#codebridge-device-control/);
    assert.match(premium, /@media \(max-width: 720px\)/);
});

void test('device registration, gateway heartbeat and pairing are never invented', () => {
    assert.match(device, /connection_status: 'not_verified'/);
    assert.match(
        device,
        /Live connection not verified · Gateway\s+heartbeat required/,
    );
    assert.match(device, /Registration saved/);
    assert.doesNotMatch(device, /Registered · Live status unknown/);
    assert.match(device, /'approved_unredeemed'/);
    assert.match(device, /'approval_expired'/);
    assert.match(device, /missingReceiptHeading/);
    assert.match(device, /pairingRecoveryGuidance/);
});

void test('device controls retain secure owner confirmation and no silent pairing changes', () => {
    assert.match(device, /confirmation !== device\.id/);
    assert.match(device, /router\.post\(/);
    assert.match(device, /\/disconnect/);
    assert.match(device, /\/projects\/assign/);
    assert.match(device, /onFinish: \(\) => setSubmitting\(false\)/);
    assert.match(device, /\/codebridge\/pair/);
    assert.match(device, /aria-expanded=\{\s*details === device\.id\s*\}/);
});

void test('accessible device filtering and progressive disclosure are retained', () => {
    assert.match(device, /useMemo\(\(\) => \{/);
    assert.match(device, /setView\(event\.target\.value as View\)/);
    assert.match(device, /aria-live="polite"/);
    assert.match(
        device,
        /Showing \{visibleDevices\.length\} of \{devices\.length\}[\s\S]{0,160}registered devices/,
    );
    assert.match(device, /Setup guidance and enrollment safety/);
    assert.match(device, /<summary className=/);
    assert.match(device, /Select an existing device\/project grant/);
});

void test('layout uses readable, keyboard-accessible, responsive controls', () => {
    assert.match(premium, /font-size: 14px/);
    assert.match(premium, /min-height: 44px/);
    assert.match(premium, /:focus-visible/);
    assert.match(premium, /prefers-reduced-motion/);
    assert.match(css, /prefers-reduced-motion/);
    assert.match(premium, /grid-template-columns: minmax\(0, 1fr\)/);
});

void test('owner functional pages remain routed to their real protected modules', () => {
    for (const path of [
        'resources/js/pages/operator.tsx',
        'resources/js/pages/operator-products.tsx',
        'resources/js/pages/operator-directory.tsx',
        'resources/js/pages/operator-payments.tsx',
        'resources/js/pages/operator-kslp.tsx',
        'resources/js/pages/operator-ops.tsx',
    ]) {
        assert.match(read(path), /<Head\b/, path);
    }
    assert.match(shell, /href: '\/operator\/payments'/);
    assert.match(shell, /href: '\/operator\/kslp'/);
    assert.match(shell, /href: '\/operator\/directory'/);
    assert.match(shell, /href: '\/settings\/profile'/);
    assert.match(
        read('routes/settings.php'),
        /Route::get\('settings\/profile'/,
    );
});

void test('owner Ops navigation targets actual backed sections, not generic page top', () => {
    const ops = read('resources/js/pages/operator-ops.tsx');
    const shellNav = read('resources/js/layouts/owner-module-shell.tsx');
    const lockedNav = read('resources/js/components/operator-command-os.tsx');
    for (const id of [
        'owner-readiness',
        'owner-backup-freshness',
        'owner-action-audit',
        'owner-guardrail-signals',
    ]) {
        assert.ok(ops.includes(`id="${id}"`), id);
        assert.ok(shellNav.includes(`/operator/ops#${id}`), id);
        assert.ok(lockedNav.includes(`/operator/ops#${id}`), id);
    }
});

void test('registered and pending project names are not clipped to badge-sized ellipses', () => {
    assert.match(
        device,
        /className="text-sm leading-5 font-black break-words"[\s\S]{0,100}\{device\.name\}/,
    );
    assert.doesNotMatch(
        device,
        /className="truncate text-sm font-black"[\s\S]{0,100}\{device\.name\}/,
    );
    assert.match(
        device,
        /className="min-w-0 text-sm leading-5 font-black break-words"/,
    );
    const browser = read('scripts/browser-preview-verify.mjs');
    assert.match(browser, /CodeBridge device name clipped at width/);
    assert.match(browser, /identity\.ellipsis/);
});

void test('no false claims of live status or fabricated owner revenue are introduced', () => {
    assert.doesNotMatch(premium, /Online\s*:\s*(?:true|yes)/i);
    assert.match(device, /Online status: Not verified/);
    assert.match(os, /confirmed_inr_revenue_minor/);
    assert.match(os, /'Not verified'/);
});
