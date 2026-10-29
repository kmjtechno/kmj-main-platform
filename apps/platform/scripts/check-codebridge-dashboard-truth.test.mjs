import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { readSourceText } from './source-text.mjs';

const ui = readSourceText('resources/js/pages/services/codebridge.tsx');
// Device cards are rendered by the Device Control Center component (PR #377);
// device-health truth rules apply to the page and the component together.
const deviceCenter = readSourceText(
    'resources/js/components/codebridge/device-control-center.tsx',
);
const deviceUi = `${ui}\n${deviceCenter}`;
const directory = readFileSync(
    'app/Services/Licensing/CodeBridge/CodeBridgeCustomerDeviceDirectory.php',
    'utf8',
);
const routes = readFileSync('routes/web.php', 'utf8');

void test('green entitlement badge and owner plan ceiling cannot imply device online', () => {
    assert.match(ui, /Entitlement: \{entitlement\.status\}/);
    assert.match(ui, /codeBridgeDeviceQuotaDisplay/);
    assert.match(ui, /\.registrationHint/);
    assert.doesNotMatch(ui, />\s*\{entitlement\.status\}\s*<\/span>/);
    assert.doesNotMatch(ui, /'Limit ' \+ service\.device_limit/);
});

void test('dashboard never invents online device presence from registration', () => {
    assert.match(directory, /'connection_status' => 'not_verified'/);
    assert.match(deviceCenter, /Online status: Not verified/);
    assert.match(deviceCenter, /Live connection has not been verified/);
    assert.match(deviceCenter, /Registered · Live status unknown/);
    assert.doesNotMatch(deviceUi, /connection_status === 'online'/);
    assert.doesNotMatch(deviceUi, />\s*Online\s*</);
});

void test('approved-but-unredeemed device cannot masquerade as a successfully paired agent', () => {
    assert.match(directory, /'pairing_state' =>/);
    assert.match(directory, /'approved_unredeemed'/);
    assert.match(directory, /'redeemed'/);
    assert.match(deviceCenter, /Approved · Not redeemed/);
    assert.match(deviceCenter, /Approval has not reached this computer/);
    assert.match(deviceCenter, /recent\s+password confirmation required/);
    assert.match(deviceCenter, /gateway heartbeat is verified/);
    assert.match(deviceCenter, /connection_status: 'not_verified'/);
});

void test('permissions must be backed by actual server-authorized scope', () => {
    assert.match(ui, /service\.permissions\.map\(\(permission\)/);
    assert.match(ui, /No permissions reported/);
    assert.doesNotMatch(ui, /\['read', 'write', 'execute'\]/);
});

void test('device cards are searchable without changing tenant authorization', () => {
    assert.match(
        ui,
        /<DeviceControlCenter[\s\S]*tenantId=\{organization\.id\}/,
    );
    assert.match(deviceCenter, /visibleDevices\.map\(\(device\)/);
    assert.match(deviceCenter, /Search device, OS, project or ID/);
    assert.match(
        routes,
        /\$deviceDirectory->forTenant\(\(string\) \$organization\['id'\], time\(\)\)/,
    );
    assert.match(directory, /->where\('c\.tenant_id', \$tenantId\)/);
});

void test('OAuth grants are not mislabeled as live IDE connections', () => {
    assert.match(ui, /authorized refresh sessions/);
    assert.match(ui, /Last token activity/);
    assert.match(ui, /authorized OAuth refresh grants/);
    assert.doesNotMatch(ui, /\} active\s*<\/span>/);
});

void test('revocation requires confirmation and prevents duplicate clicks', () => {
    assert.match(ui, /window\.confirm\(/);
    assert.match(ui, /disabled=\{revokingClient !== null\}/);
    assert.match(ui, /onFinish: \(\) => setRevokingClient\(null\)/);
});

void test('clipboard failures have visible feedback', () => {
    assert.match(
        ui,
        /await navigator\.clipboard\.writeText\(service\.endpoint\)/,
    );
    assert.match(ui, /Copy unavailable/);
    assert.match(ui, /role="status"/);
});

void test('many OAuth grants have compact, searchable cards and unique client clues', () => {
    assert.match(ui, /visibleClients\.map\(\(client\)/);
    assert.match(ui, /matchingClients\.slice\(0, 5\)/);
    assert.match(ui, /client\.client_id\.slice\(-10\)/);
    assert.match(ui, /Search client name or scope/);
});

void test('offline recovery stays inside the KMJ-hosted device dashboard', () => {
    assert.match(deviceCenter, /\/install-codebridge-windows\.cmd/);
    assert.match(deviceCenter, /Connect this Windows PC/);
    assert.match(deviceCenter, /deviceRecoveryAction\(device\.platform\)/);
    assert.match(deviceCenter, /href=\{recovery\.href\}/);
    assert.match(deviceCenter, /\{recovery\.label\}/);
    assert.match(deviceCenter, /Registration · \{device\.id\.slice\(-8\)\}/);
    assert.match(deviceCenter, /Registration alone is not an/);
    assert.match(deviceCenter, /Live connection has not been verified/);
    assert.doesNotMatch(deviceCenter, /github\.com\/kmjtechno\/kmj-codebridge/);
    assert.doesNotMatch(
        ui,
        /raw\.githubusercontent\.com\/kmjtechno\/kmj-codebridge/,
    );
});

const hub = readSourceText(
    'resources/js/components/codebridge/control-center-hub.tsx',
);

void test('control center provides working sections and scoped device onboarding', () => {
    for (const [target, source] of [
        ['codebridge-overview', hub],
        ['codebridge-device-control', deviceCenter],
        ['codebridge-usage', hub],
        ['codebridge-plan-billing', hub],
        ['codebridge-clients', ui],
        ['codebridge-settings', hub],
    ]) {
        assert.match(source, new RegExp(target));
    }
    assert.match(ui, /<CodeBridgeControlCenterHub/);
    assert.match(ui, /id="codebridge-clients"/);
    assert.match(hub, /href="\/codebridge\/pair"/);
    assert.match(hub, /href="\/settings\/security"/);
    assert.match(hub, /href="\/purchase"/);
});

void test('usage billing and device state never invent measurements or connectivity', () => {
    assert.match(hub, /No authoritative metering feed connected/);
    assert.match(hub, /Registration does not establish live presence/);
    assert.match(hub, /Refresh grants, not live app sessions/);
    assert.match(hub, /Invoices and paid consumption must be obtained/);
    assert.match(hub, /codeBridgeDeviceQuotaDisplay/);
    assert.doesNotMatch(hub, /connection_status === 'online'/);
    assert.doesNotMatch(hub, /100%|unlimited calls|live sessions/);
});

const deviceQuota = readSourceText(
    'resources/js/components/codebridge/device-policy-display.ts',
);

void test('owner numeric sentinel never appears as a customer-facing hard limit', () => {
    assert.match(deviceQuota, /OWNER_POLICY_DEVICE_CEILING = 2147483647/);
    assert.match(deviceQuota, /plan === 'owner'/);
    assert.match(deviceQuota, /Owner-tier technical ceiling/);
    assert.match(deviceQuota, /not live or executable capacity/);
    assert.match(deviceCenter, /codeBridgeDeviceQuotaDisplay/);
    assert.match(deviceCenter, /plan: string \| null/);
    assert.match(ui, /plan=\{service\.plan\}/);
    assert.doesNotMatch(deviceQuota, /unlimited device capacity/i);
});

void test('control center uses accessible section switching instead of one long dashboard', () => {
    assert.match(hub, /aria-pressed=\{activeSection === id\}/);
    assert.match(hub, /onSectionChange\(id\)/);
    assert.match(hub, /\{children\}/);
    assert.match(ui, /activeSection=\{activeSection\}/);
    assert.match(ui, /onSectionChange=\{setActiveSection\}/);
    for (const section of ['overview', 'devices', 'setup', 'clients']) {
        assert.match(ui, new RegExp(`activeSection === '${section}'`));
    }
    for (const section of ['overview', 'usage', 'billing', 'settings']) {
        assert.match(
            hub,
            new RegExp(`hidden=\\{activeSection !== '${section}'\\}`),
        );
    }
    assert.doesNotMatch(hub, /href=\{href\}/);
});

void test('CodeBridge customer controls avoid sub-12px utility labels', () => {
    for (const source of [ui, deviceCenter, hub]) {
        assert.doesNotMatch(source, /text-\[(?:9|10|11)px\]/);
    }
});

void test('CodeBridge dashboard uses the existing official product icon', () => {
    assert.match(ui, /src="\/assets\/kmj-codebridge-icon\.png"/);
    assert.match(ui, /alt="Official KMJ CodeBridge icon"/);
    assert.ok(existsSync('public/assets/kmj-codebridge-icon.png'));
    assert.doesNotMatch(ui, /laravel\.(?:svg|png)|<Cable className="h-7 w-7"/i);
    assert.match(ui, /setActiveSection\('devices'\)/);
});

const ownerLicenseSettings = readSourceText(
    'resources/js/pages/operator-codebridge-owner.tsx',
);

void test('one canonical device dashboard; owner route is licensing only', () => {
    assert.match(ownerLicenseSettings, /CodeBridge Owner License Settings/);
    assert.match(ownerLicenseSettings, /href="\/services\/kmj-codebridge#codebridge-device-control"/);
    assert.doesNotMatch(ownerLicenseSettings, /<DeviceControlCenter\b/);
    assert.match(ownerLicenseSettings, /UPGRADE_CODEBRIDGE_OWNER/);
    assert.match(ui, /activeSection === 'devices'/);
    assert.match(ui, /'#codebridge-device-control': 'devices'/);
    assert.match(ui, /window\.addEventListener\('hashchange', selectCodeBridgeHash\)/);
    assert.match(ui, /window\.removeEventListener\('hashchange', selectCodeBridgeHash\)/);
});
