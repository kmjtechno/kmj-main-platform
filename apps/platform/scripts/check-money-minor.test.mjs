import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { minorDigits, toMinorUnits } from '../resources/js/lib/money-minor.ts';

void test('typed amounts convert to exact integer minor units', () => {
    assert.equal(toMinorUnits('1499', 'INR'), 149900);
    assert.equal(toMinorUnits('1,499.50', 'INR'), 149950);
    assert.equal(toMinorUnits('0.10', 'USD'), 10);
    assert.equal(toMinorUnits('19.99', 'USD'), 1999);
    assert.equal(toMinorUnits('500', 'JPY'), 500);
    assert.equal(toMinorUnits('1.234', 'KWD'), 1234);
});

void test('ambiguous, negative, zero or over-precise amounts are rejected', () => {
    for (const bad of [
        '',
        'abc',
        '-5',
        '0',
        '0.00',
        '10.999',
        '1e3',
        '1.2.3',
    ]) {
        assert.equal(toMinorUnits(bad, 'INR'), null, bad);
    }
    assert.equal(toMinorUnits('10.5', 'JPY'), null);
    assert.equal(minorDigits('inr'), 2);
});

void test('the confirm form submits minor units and blocks invalid amounts', () => {
    const page = readFileSync(
        new URL('../resources/js/pages/operator.tsx', import.meta.url),
        'utf8',
    );
    assert.match(page, /toMinorUnits\(form\.data\.amount_minor/);
    assert.match(page, /amount_minor: String\(minor\)/);
    assert.match(page, /disabled=\{form\.processing \|\| minor === null\}/);
    assert.doesNotMatch(page, /Amount in paise\/cents/);
});
