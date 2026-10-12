import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const ui = readFileSync('resources/js/pages/services/codebridge.tsx', 'utf8');
const directory = readFileSync(
    'app/Services/Licensing/CodeBridge/CodeBridgeCustomerDeviceDirectory.php',
    'utf8',
);
const routes = readFileSync('routes/web.php', 'utf8');

void test('dashboard never invents online device presence from registration', () => {
    assert.match(directory, /'connection_status' => 'not_verified'/);
    assert.match(ui, /Online status: Not verified/);
    assert.match(ui, /Live connection has not been verified/);
    assert.doesNotMatch(ui, /device\.connection_status === 'online'/);
});

void test('permissions must be backed by actual server-authorized scope', () => {
    assert.match(ui, /service\.permissions\.map\(\(permission\)/);
    assert.match(ui, /No permissions reported/);
    assert.doesNotMatch(ui, /\['read', 'write', 'execute'\]/);
});

void test('device cards are searchable without changing tenant authorization', () => {
    assert.match(ui, /filteredDevices\.map\(\(device\)/);
    assert.match(ui, /Search device, platform or project/);
    assert.match(routes, /\$deviceDirectory->forTenant\(\(string\) \$organization\['id'\], time\(\)\)/);
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
    assert.match(ui, /await navigator\.clipboard\.writeText\(service\.endpoint\)/);
    assert.match(ui, /Copy unavailable/);
    assert.match(ui, /role="status"/);
});
