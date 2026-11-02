import test from 'node:test';
import assert from 'node:assert/strict';
import { pendingProjectCards } from '../resources/js/components/codebridge/pending-project-cards.mjs';

void test('VIOSO pending assignment becomes a separate request card, not an extra Calibration grant', () => {
    const calibration = {
        id: 'kmj-homeoffice-desktop-5fvjmet',
        name: 'DESKTOP-5FVJMET',
        projects: [{ id: 'kmj-calibration-pro', name: 'KMJ Calibration Pro' }],
        pending_projects: [{
            id: 'vioso-clone',
            name: 'VIOSO Clone',
            status: 'pending_local_setup',
        }],
    };
    const before = structuredClone(calibration);
    const cards = pendingProjectCards([calibration]);
    assert.deepEqual(calibration, before);
    assert.deepEqual(calibration.projects.map(p => p.id), ['kmj-calibration-pro']);
    assert.equal(cards.length, 1);
    assert.equal(cards[0].projectId, 'vioso-clone');
    assert.equal(cards[0].sourceDeviceId, 'kmj-homeoffice-desktop-5fvjmet');
    assert.equal(cards[0].registration, 'not_registered');
    assert.equal(cards[0].connectionStatus, 'not_verified');
    assert.equal(Object.hasOwn(cards[0], 'credential'), false);
    assert.equal(Object.hasOwn(cards[0], 'projects'), false);
});

void test('requests are scoped to their originating registration and deduplicated', () => {
    const card = {
        id: 'device1', name: 'P520', pending_projects: [
            { id: 'vioso-clone', name: 'VIOSO', status: 'pending_local_setup' },
            { id: 'vioso-clone', name: 'VIOSO', status: 'pending_local_setup' },
            { id: 'not-pending', name: 'Done', status: 'approved' },
        ],
    };
    const cards = pendingProjectCards([card, { ...card, id: 'device2' }]);
    assert.equal(cards.length, 2);
    assert.notEqual(cards[0].key, cards[1].key);
    assert.equal(cards[0].sourceDeviceId, 'device1');
    assert.equal(cards[1].sourceDeviceId, 'device2');
});

void test('malformed or missing requests never become fake device cards', () => {
    assert.deepEqual(pendingProjectCards(null), []);
    assert.deepEqual(pendingProjectCards([{}, { id: 'desktop', pending_projects: null }]), []);
    assert.deepEqual(pendingProjectCards([{
        id: 'desktop', pending_projects: [{ id: '', status: 'pending_local_setup' }],
    }]), []);
});
