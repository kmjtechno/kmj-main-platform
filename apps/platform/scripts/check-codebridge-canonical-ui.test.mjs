import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
    CODEBRIDGE_SECTIONS,
    codeBridgeAnchorFromHash,
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
    assert.match(owner, /<DeviceControlCenter/);
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
