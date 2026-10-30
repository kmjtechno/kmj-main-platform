import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
    CODEBRIDGE_SECTIONS,
    codeBridgeAnchorFromHash,
    codeBridgeHashIsNavigable,
    codeBridgeSectionFromHash,
} from '../resources/js/components/codebridge/section-routing.mjs';

const read = (file) => readFileSync(file, 'utf8');
const header = read('resources/js/components/app-header.tsx');
const owner = read('resources/js/pages/operator-codebridge-owner.tsx');
const service = read('resources/js/pages/services/codebridge.tsx');
const hub = read('resources/js/components/codebridge/control-center-hub.tsx');
const routes = read('routes/web.php');

void test('every CodeBridge link targets the one canonical Control Center route', () => {
    assert.match(routes, /Route::get\('services\/kmj-codebridge'/);
    assert.match(routes, /->name\('services\.codebridge'\)/);
    // The header previously pointed at a route that does not exist (404).
    assert.doesNotMatch(header, /href: '\/services\/codebridge'/);
    assert.match(header, /href: '\/services\/kmj-codebridge'/);
    // Legacy path redirects instead of rendering a second page.
    assert.match(
        routes,
        /Route::get\('services\/codebridge', fn \(\) => redirect\(\)->route\('services\.codebridge'/,
    );
});

void test('owner fleet page does not duplicate connect/install actions', () => {
    for (const duplicated of [
        '/install-codebridge-windows.cmd',
        'href="/install"',
        '/install-chatgpt-desktop.ps1',
        'KMJ-CodeBridge-Connect-Linux.sh',
        'Approve pairing code',
    ]) {
        assert.ok(
            !owner.includes(duplicated),
            `owner page must not re-implement ${duplicated}`,
        );
    }
    assert.match(owner, /href="\/services\/kmj-codebridge"/);
    // Owner-only controls stay on the owner page.
    assert.match(owner, /UPGRADE_CODEBRIDGE_OWNER/);
    // Multi-org visibility stays, but read-only: no nested interactive
    // Control Center, pairing, disconnect or project-assignment controls.
    assert.doesNotMatch(owner, /<DeviceControlCenter/);
    assert.match(owner, /organizations\.map\(/);
    assert.match(owner, /Read-only summary/);
    for (const action of [
        '/disconnect',
        'projects/assign',
        '/codebridge/pair',
        'confirm_device_id',
    ]) {
        assert.ok(
            !owner.includes(action),
            `owner page must not expose ${action}`,
        );
    }
    assert.equal(
        (owner.match(/router\.post\(/g) ?? []).length,
        1,
        'only the owner-tier upgrade may post from the owner page',
    );
});

void test('canonical page keeps the audited setup actions and owner cross-link', () => {
    assert.match(service, /href="\/install-codebridge-windows\.cmd"/);
    assert.match(service, /href="\/codebridge\/pair"/);
    assert.match(service, /download="KMJ-CodeBridge-VPS\.sh"/);
    assert.match(hub, /href="\/operator\/codebridge\/owner-plan"/);
});

void test('deep links select a whitelisted section and never unknown state', () => {
    assert.equal(
        codeBridgeSectionFromHash('#codebridge-device-control'),
        'devices',
    );
    assert.equal(codeBridgeSectionFromHash('#codebridge-clients'), 'clients');
    assert.equal(codeBridgeSectionFromHash('#Billing'), 'billing');
    for (const section of CODEBRIDGE_SECTIONS) {
        assert.equal(codeBridgeSectionFromHash(`#${section}`), section);
    }
    for (const hostile of [
        '',
        '#',
        '#__proto__',
        '#constructor',
        '#toString',
        '#<script>',
        '#unknown',
        undefined,
        null,
        42,
    ]) {
        assert.equal(codeBridgeSectionFromHash(hostile), 'overview');
        assert.equal(codeBridgeAnchorFromHash(hostile), null);
    }
    assert.equal(
        codeBridgeAnchorFromHash('#codebridge-device-control'),
        'codebridge-device-control',
    );
    assert.equal(codeBridgeAnchorFromHash('#devices'), null);
});

void test('the dashboard deep link lands on a section that renders its target', () => {
    const dashboard = read('resources/js/pages/dashboard.tsx');
    assert.match(
        dashboard,
        /href="\/services\/kmj-codebridge#codebridge-device-control"/,
    );
    assert.match(
        service,
        /codeBridgeSectionFromHash\(window\.location\.hash\)/,
    );
    assert.match(
        read('resources/js/components/codebridge/device-control-center.tsx'),
        /id="codebridge-device-control"/,
    );
    // The device center is only rendered in the devices section.
    assert.match(
        service,
        /activeSection === 'devices'[\s\S]{0,400}<DeviceControlCenter/,
    );
});

void test('empty and #overview hashes navigate back to Overview; hostile hashes do nothing', () => {
    for (const hash of ['', '#', '#overview', '#OVERVIEW']) {
        assert.equal(codeBridgeHashIsNavigable(hash), true, hash);
        assert.equal(codeBridgeSectionFromHash(hash), 'overview', hash);
    }
    for (const hash of [
        '#__proto__',
        '#constructor',
        '#unknown',
        '#devices;x',
        null,
        undefined,
        5,
    ]) {
        assert.equal(codeBridgeHashIsNavigable(hash), false, String(hash));
    }
    assert.equal(codeBridgeHashIsNavigable('#devices'), true);
    assert.equal(codeBridgeHashIsNavigable('#codebridge-device-control'), true);
});

void test('canonical page applies navigable hashes (including overview) on hashchange', () => {
    assert.match(
        service,
        /codeBridgeHashIsNavigable\(window\.location\.hash\)/,
    );
    // The old early-return skipped overview, leaving Devices selected.
    assert.doesNotMatch(service, /section === 'overview'\) return/);
});

void test('owner navigation reaches the canonical CodeBridge workspace, not a second device page', () => {
    for (const file of [
        'resources/js/components/app-sidebar.tsx',
        'resources/js/components/operator-command-os.tsx',
        'resources/js/components/operator-control-overview.tsx',
        'resources/js/components/operator-module-navigation.tsx',
        'resources/js/layouts/owner-module-shell.tsx',
    ]) {
        const text = read(file);
        assert.match(
            text,
            /\/services\/kmj-codebridge#codebridge-device-control/,
            file,
        );
        assert.doesNotMatch(text, /\/operator\/codebridge\/owner-plan/, file);
    }
    // The workspace map keeps exactly one link to owner-plan, honestly labelled
    // as licence settings (the read-only fleet + Owner Plan page), not devices.
    const map = read('resources/js/components/operator-workspace-map.tsx');
    assert.match(
        map,
        /label: 'CodeBridge Owner License Settings'[\s\S]{0,160}href: '\/operator\/codebridge\/owner-plan'/,
    );
    assert.equal(
        (map.match(/\/operator\/codebridge\/owner-plan/g) ?? []).length,
        1,
    );
    // Owner license settings stay reachable from the canonical page itself.
    assert.match(hub, /href="\/operator\/codebridge\/owner-plan"/);
});
