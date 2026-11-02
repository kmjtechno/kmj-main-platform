import test from 'node:test';
import assert from 'node:assert/strict';
import { deviceRecoveryAction } from '../resources/js/components/codebridge/device-recovery.mjs';

void test('only exact Calibration Pro Windows enrollment gets the scoped installer', () => {
    for (const platform of ['win32', 'Windows', ' WIN32 ']) {
        const action = deviceRecoveryAction(platform, {
            deviceId: 'kmj-homeoffice-desktop-5fvjmet',
            pendingProjectIds: [],
        });
        assert.equal(action.href, '/install-codebridge-windows.cmd');
        assert.equal(action.download, 'KMJ-CodeBridge-Connect-Windows.cmd');
        assert.equal(action.label, 'Reconnect Calibration Pro');
    }
});

void test('VIOSO pending on Calibration Pro registration cannot download the Calibration Pro installer', () => {
    const action = deviceRecoveryAction('win32', {
        deviceId: 'kmj-homeoffice-desktop-5fvjmet',
        pendingProjectIds: ['vioso-clone'],
    });
    assert.equal(action.href, '/codebridge/pair');
    assert.equal(action.download, undefined);
    assert.equal(action.label, 'Review Windows project setup');
    assert.match(action.guidance, /VIOSO-Clone/);
    assert.match(action.guidance, /pending assignments/i);
});

void test('other Windows device IDs and unknown scopes never receive the Calibration Pro installer', () => {
    const cases = [
        { deviceId: 'kmj-vioso-clone-desktop-5fvjmet', pendingProjectIds: [] },
        { deviceId: 'kmj-kmj-omnidesk-desktop-5fvjmet', pendingProjectIds: [] },
        { deviceId: '', pendingProjectIds: [] },
        { deviceId: 'kmj-homeoffice-desktop-5fvjmet' },
        {},
    ];
    for (const scope of cases) {
        const action = deviceRecoveryAction('windows', scope);
        assert.equal(action.href, '/codebridge/pair');
        assert.equal(action.download, undefined);
        assert.doesNotMatch(action.label, /^Reconnect Calibration Pro$/);
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
