import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { pendingProjectCards } from '../resources/js/components/codebridge/pending-project-cards.mjs';

void test('VIOSO pending remains unregistered', () => {
    const calibration = {
        id: 'kmj-homeoffice-desktop-5fvjmet',
        name: 'DESKTOP-5FVJMET',
        projects: [{ id: 'kmj-calibration-pro', name: 'KMJ Calibration Pro' }],
        pending_projects: [
            {
                id: 'vioso-clone',
                name: 'VIOSO Clone',
                status: 'pending_local_setup',
            },
        ],
    };
    const before = structuredClone(calibration);
    const cards = pendingProjectCards([calibration]);

    assert.deepEqual(calibration, before);
    assert.deepEqual(
        calibration.projects.map((project) => project.id),
        ['kmj-calibration-pro'],
    );
    assert.equal(cards.length, 1);
    assert.equal(cards[0].projectId, 'vioso-clone');
    assert.equal(cards[0].sourceDeviceId, calibration.id);
    assert.equal(cards[0].registration, 'not_registered');
    assert.equal(cards[0].connectionStatus, 'not_verified');
    assert.equal(Object.hasOwn(cards[0], 'credential'), false);
    assert.equal(Object.hasOwn(cards[0], 'projects'), false);
});

void test('requests are scoped to each device and deduplicated', () => {
    const device = {
        id: 'device1',
        name: 'P520',
        pending_projects: [
            { id: 'vioso-clone', name: 'VIOSO', status: 'pending_local_setup' },
            { id: 'vioso-clone', name: 'VIOSO', status: 'pending_local_setup' },
            { id: 'not-pending', name: 'Done', status: 'approved' },
        ],
    };
    const cards = pendingProjectCards([device, { ...device, id: 'device2' }]);

    assert.equal(cards.length, 2);
    assert.notEqual(cards[0].key, cards[1].key);
    assert.equal(cards[0].sourceDeviceId, 'device1');
    assert.equal(cards[1].sourceDeviceId, 'device2');
});

void test('invalid pending entries cannot create device cards', () => {
    assert.deepEqual(pendingProjectCards(null), []);
    const missing = [{}, { id: 'desktop', pending_projects: null }];
    assert.deepEqual(pendingProjectCards(missing), []);
    const invalid = [
        {
            id: 'desktop',
            pending_projects: [{ id: '', status: 'pending_local_setup' }],
        },
    ];
    assert.deepEqual(pendingProjectCards(invalid), []);
});

void test('dashboard renders separate request-only cards', () => {
    const root = path.dirname(fileURLToPath(import.meta.url));
    const file = path.resolve(
        root,
        '../resources/js/components/codebridge/device-control-center.tsx',
    );
    const ui = readFileSync(file, 'utf8');

    assert.match(ui, /pendingRequests\.map\(\(request\)/);
    assert.match(ui, /Pending project setup — separate from registered devices/);
    assert.match(ui, /Request project on this existing/);
    assert.match(ui, /this does not grant another project to its/);
    assert.doesNotMatch(ui, /Awaiting local project setup/);
    assert.doesNotMatch(ui, /Connect this Windows PC/);
    assert.doesNotMatch(ui, /download="KMJ-CodeBridge-Connect-Windows\.cmd"/);
});
