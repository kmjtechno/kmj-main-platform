import test from 'node:test';
import assert from 'node:assert/strict';
import { assess, matchesMarker, waitForMarker } from './browser-qa.mjs';

const healthy = { path: '/products', url: 'https://staging.kmjtechno.com/products',
    httpStatus: 200, bodyLength: 200, markerFound: true, exceptions: 0, overflowPx: 0 };

test('CSS uppercase and responsive whitespace preserve visible content identity', () => {
    assert.equal(matchesMarker('KMJ CALIBRATION\nPRO', 'KMJ Calibration Pro'), true);
    assert.equal(matchesMarker('VIRTUAL  DEMO', 'Virtual demo'), true);
    assert.equal(matchesMarker('Loading...', 'KMJ Calibration Pro'), false);
});

test('blank, redirected, failed and crashed pages cannot pass', () => {
    for (const change of [{ bodyLength: 0 }, { url: 'https://kmjtechno.com/products' },
        { httpStatus: 500 }, { markerFound: false }, { exceptions: 1 }]) {
        assert.ok(assess({ ...healthy, ...change }).failures.length > 0);
    }
    assert.deepEqual(assess(healthy).failures, []);
});

test('layout overflow is visible as an advisory without blocking deployment', () => {
    const result = assess({ ...healthy, overflowPx: 24 });
    assert.deepEqual(result.failures, []);
    assert.deepEqual(result.warnings, ['horizontal_overflow']);
});

test('bounded marker readiness accepts a late render without weakening failure', async () => {
    let checks = 0;
    assert.equal(await waitForMarker(() => ++checks >= 3, 100, 0), true);
    assert.ok(checks >= 3);

    assert.equal(await waitForMarker(() => false, 0, 0), false);
});
