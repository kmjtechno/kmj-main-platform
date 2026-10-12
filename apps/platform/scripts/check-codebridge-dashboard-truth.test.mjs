import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const ui = readFileSync('resources/js/pages/services/codebridge.tsx', 'utf8');
// Device cards are rendered by the Device Control Center component (PR #377);
// device-health truth rules apply to the page and the component together.
const deviceCenter = readFileSync(
    'resources/js/components/codebridge/device-control-center.tsx',
    'utf8',
);
const deviceUi = `${ui}\n${deviceCenter}`;
const directory = readFileSync(
    'app/Services/Licensing/CodeBridge/CodeBridgeCustomerDeviceDirectory.php',
    'utf8',
);
const routes = readFileSync('routes/web.php', 'utf8');

void test('dashboard never invents online device presence from registration', () => {
    assert.match(directory, /'connection_status' => 'not_verified'/);
    assert.match(deviceCenter, /Online status: Not verified/);
    assert.match(deviceCenter, /Live connection has not been verified/);
    assert.match(deviceCenter, /Registered · Live status unknown/);
    assert.doesNotMatch(deviceUi, /connection_status === 'online'/);
    assert.doesNotMatch(deviceUi, />\s*Online\s*</);
});

void test('permissions must be backed by actual server-authorized scope', () => {
    assert.match(ui, /service\.permissions\.map\(\(permission\)/);
    assert.match(ui, /No permissions reported/);
    assert.doesNotMatch(ui, /\['read', 'write', 'execute'\]/);
});

void test('device cards are searchable without changing tenant authorization', () => {
    assert.match(ui, /<DeviceControlCenter[\s\S]*tenantId=\{organization\.id\}/);
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

void test('offline remediation links to exact documented Connection Doctor', () => {
    assert.match(deviceCenter, /docs\/CONNECTION-DOCTOR\.md/);
    assert.match(deviceUi, /connection_overview/);
    assert.match(deviceCenter, /Live connection has not been verified/);
});
