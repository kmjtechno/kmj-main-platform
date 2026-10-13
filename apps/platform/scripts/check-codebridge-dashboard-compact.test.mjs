import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const dashboard = readFileSync(
    'resources/js/pages/services/codebridge.tsx',
    'utf8',
);

void test('CodeBridge dashboard exposes keyboard-reachable anchored sections', () => {
    for (const anchor of [
        'codebridge-overview',
        'codebridge-devices',
        'codebridge-clients',
        'codebridge-connection',
        'codebridge-security',
    ]) {
        assert.match(dashboard, new RegExp('id="' + anchor + '"'));
        assert.match(dashboard, new RegExp("'#" + anchor + "'"));
    }
    assert.match(dashboard, /aria-label="CodeBridge dashboard sections"/);
    assert.match(dashboard, /focus-visible:ring-2/);
    assert.doesNotMatch(dashboard, /overflow-x-auto p-4 sm:p-6/);
});

void test('device search respects authorized projects and never invents live status', () => {
    assert.match(dashboard, /id="codebridge-device-search"/);
    assert.match(dashboard, /device\.projects\.flatMap/);
    assert.match(dashboard, /visibleDevices\.map\(\(device\)/);
    assert.match(dashboard, /matchingDevices\.slice\(0, 4\)/);
    assert.match(dashboard, /aria-expanded=\{showAllDevices\}/);
    assert.match(dashboard, /No registered devices match this search/);
    assert.match(dashboard, /Registration does not confirm live connectivity/);
    assert.match(dashboard, /Live connection: Not verified/);
});

void test('client management defaults to four grants, has scope search and two-step revocation', () => {
    assert.match(dashboard, /id="codebridge-client-search"/);
    assert.match(dashboard, /visibleClients\.map\(\(client\)/);
    assert.match(dashboard, /matchingClients\.slice\(0, 4\)/);
    assert.match(dashboard, /aria-expanded=\{showAllClients\}/);
    assert.match(dashboard, /client grants/);
    assert.match(dashboard, /not proof that the application is currently online/);
    assert.match(dashboard, /revokeCandidate === client\.client_id/);
    assert.match(dashboard, /Confirm revoke/);
    assert.match(dashboard, /Cancel/);
    assert.match(dashboard, /router\.post\(/);
    assert.doesNotMatch(dashboard, /onClick=\{\(\) =>\s*revokeClient\(client\.client_id\)\}/);
});

void test('privacy and capability claims reflect real server data, not fictional permissions', () => {
    assert.match(dashboard, /service\.permissions\.map/);
    assert.match(dashboard, /No permissions reported/);
    assert.doesNotMatch(dashboard, /\['read', 'write', 'execute'\]/);
    assert.match(dashboard, /OAuth configuration, not live agent status/);
    assert.match(dashboard, /navigator\.clipboard\.writeText\(service\.endpoint\)/);
    assert.match(dashboard, /aria-live="polite"/);
});
