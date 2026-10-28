import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createSingleFlightGate } from '../resources/js/lib/single-flight-gate.mjs';

void test('request gate admits the first action only until it finishes', () => {
    const gate = createSingleFlightGate();
    assert.equal(gate.isBusy(), false);
    assert.equal(gate.enter(), true);
    assert.equal(gate.enter(), false);
    assert.equal(gate.isBusy(), true);
    gate.leave();
    assert.equal(gate.isBusy(), false);
    assert.equal(gate.enter(), true);
});

void test('separate editors have independent request gates', () => {
    const first = createSingleFlightGate();
    const second = createSingleFlightGate();
    assert.equal(first.enter(), true);
    assert.equal(first.enter(), false);
    assert.equal(second.enter(), true);
    first.leave();
    assert.equal(second.isBusy(), true);
});

void test('content and artwork share one ref-backed gate and release in finally', () => {
    const source = readFileSync(
        new URL('../resources/js/components/product-content-editor.tsx', import.meta.url),
        'utf8',
    );
    assert.match(source, /useRef\(createSingleFlightGate\(\)\)/);
    assert.match(source, /if \(!requestGate\.current\.enter\(\)\) return;/);
    assert.match(source, /finally \{\s*requestGate\.current\.leave\(\);/);
    assert.equal((source.match(/run\(async \(\) => \{/g) ?? []).length, 2);
    assert.doesNotMatch(source, /if \(busy\) return;/);
});

void test('quick-create ID errors release its existing gate without locking up UI', () => {
    const source = readFileSync(
        new URL('../resources/js/components/quick-product-creator.tsx', import.meta.url),
        'utf8',
    );
    const tryStart = source.indexOf('        try {');
    const newId = source.indexOf('crypto.randomUUID()');
    const finallyStart = source.indexOf('        } finally {');
    const gateRelease = source.indexOf('inFlight.current = false;', finallyStart);
    assert.ok(tryStart > -1 && newId > tryStart && newId < finallyStart);
    assert.ok(gateRelease > finallyStart);
});
