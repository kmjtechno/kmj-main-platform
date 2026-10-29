import test from 'node:test';
import assert from 'node:assert/strict';
import { deviceRecoveryAction } from '../resources/js/components/codebridge/device-recovery.mjs';

void test('Windows registrations receive only the Windows connector', () => {
    for (const platform of ['win32', 'Windows', ' WIN32 ']) {
        const action = deviceRecoveryAction(platform);
        assert.equal(action.href, '/install-codebridge-windows.cmd');
        assert.equal(action.download, 'KMJ-CodeBridge-Connect-Windows.cmd');
        assert.equal(action.label, 'Reconnect on Windows');
    }
});

void test('Linux VPS registrations never download a Windows executable', () => {
    for (const platform of ['linux', 'Linux', ' LINUX ']) {
        const action = deviceRecoveryAction(platform);
        assert.equal(action.href, '/install');
        assert.equal(action.download, undefined);
        assert.equal(action.label, 'Linux / VPS setup');
        assert.doesNotMatch(action.guidance, /Windows|double-click|YES|NO/);
    }
});

void test('unknown platforms require an explicit setup choice', () => {
    for (const platform of [
        null,
        undefined,
        '',
        'darwin',
        'freebsd',
        'x64',
        'not-windows',
    ]) {
        const action = deviceRecoveryAction(platform);
        assert.equal(action.href, '/codebridge-connect.html');
        assert.equal(action.download, undefined);
        assert.equal(action.label, 'Choose device setup');
    }
});
