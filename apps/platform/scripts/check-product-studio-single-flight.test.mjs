import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as flight from '../resources/js/lib/single-flight-gate.mjs';

void test('provider cooldown honors Retry-After without sending retries', () => {
    let now = 1000;
    const cooldown = flight.createCloudCooldown(() => now);
    cooldown.defer(90);
    assert.equal(cooldown.remaining(), 90);
    now += 1500;
    assert.equal(cooldown.remaining(), 89);
    cooldown.defer(1);
    assert.equal(cooldown.remaining(), 89);
    now += 90000;
    assert.equal(cooldown.remaining(), 0);
});

void test('retry intervals are bounded and malformed values use a safe fallback', () => {
    for (const value of [
        undefined,
        null,
        '',
        0,
        -1,
        NaN,
        Infinity,
        true,
        'junk',
    ]) {
        assert.equal(flight.normalizeRetryAfter(value), 60);
    }
    assert.equal(flight.normalizeRetryAfter('120'), 120);
    assert.equal(flight.normalizeRetryAfter(999999), 86400);
});

void test('cooldown observers update together and can unsubscribe', () => {
    const cooldown = flight.createCloudCooldown();
    let first = 0;
    let second = 0;
    const stopFirst = cooldown.subscribe(() => first++);
    const stopSecond = cooldown.subscribe(() => second++);
    try {
        cooldown.defer(60);
        assert.equal(first, 1);
        assert.equal(second, 1);
        stopFirst();
        cooldown.defer(120);
        assert.equal(first, 1);
        assert.equal(second, 2);
    } finally {
        stopFirst();
        stopSecond();
    }
});

void test('a request gate blocks a second click', () => {
    const gate = flight.createSingleFlightGate();
    assert.equal(gate.isBusy(), false);
    assert.equal(gate.enter(), true);
    assert.equal(gate.enter(), false);
    assert.equal(gate.isBusy(), true);
    gate.leave();
    assert.equal(gate.isBusy(), false);
    assert.equal(gate.enter(), true);
});

void test('separate editors use independent request gates', () => {
    const first = flight.createSingleFlightGate();
    const second = flight.createSingleFlightGate();
    assert.equal(first.enter(), true);
    assert.equal(first.enter(), false);
    assert.equal(second.enter(), true);
    first.leave();
    assert.equal(second.isBusy(), true);
});

void test('content and artwork share a synchronous gate', () => {
    const source = readFileSync(
        'resources/js/components/product-content-editor.tsx',
        'utf8',
    );
    assert.match(source, /useRef\(createSingleFlightGate\(\)\)/);
    assert.match(source, /if \(!requestGate\.current\.enter\(\)\) return;/);
    assert.match(source, /finally \{\s*requestGate\.current\.leave\(\);/);
    assert.equal((source.match(/run\(async \(\) => \{/g) ?? []).length, 2);
    assert.doesNotMatch(source, /if \(busy\) return;/);
});

void test('quick creator releases its guard on UUID errors', () => {
    const source = readFileSync(
        'resources/js/components/quick-product-creator.tsx',
        'utf8',
    );
    const tryStart = source.indexOf('        try {');
    const newId = source.indexOf('crypto.randomUUID()');
    const finallyStart = source.indexOf('        } finally {');
    const gateRelease = source.indexOf(
        'inFlight.current = false;',
        finallyStart,
    );
    assert.ok(tryStart > -1 && newId > tryStart && newId < finallyStart);
    assert.ok(gateRelease > finallyStart);
});
