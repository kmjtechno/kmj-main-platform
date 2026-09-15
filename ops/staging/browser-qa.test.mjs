import test from 'node:test';
import assert from 'node:assert/strict';
import { assess, matchesMarker } from './browser-qa.mjs';

const healthy = { path: '/info', url: 'https://staging.kmjtechno.com/info',
    httpStatus: 200, bodyLength: 200, markerFound: true, exceptions: 0, overflowPx: 0 };

test('CSS uppercase and responsive whitespace preserve visible content identity', () => {
    assert.equal(matchesMarker('STAGING LIVE\nOPERATIONS MONITOR', 'Staging live operations monitor'), true);
    assert.equal(matchesMarker('VERIFIED  DELIVERY PROGRESS', 'Verified delivery progress'), true);
    assert.equal(matchesMarker('Loading...', 'Verified delivery progress'), false);
});

test('blank, redirected, failed and crashed pages cannot pass', () => {
    for (const change of [{ bodyLength: 0 }, { url: 'https://kmjtechno.com/info' },
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
