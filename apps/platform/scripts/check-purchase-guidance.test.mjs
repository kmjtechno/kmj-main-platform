import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { orderProgress } from '../resources/js/lib/order-progress.ts';

void test('every order status has a plain-language label and next step', () => {
    assert.equal(orderProgress('requested').step, 1);
    assert.equal(orderProgress('confirmed').step, 2);
    assert.equal(orderProgress('cancelled').label, 'Cancelled');
    assert.match(orderProgress('confirmed').message, /dashboard/);
    assert.equal(orderProgress('weird').label, 'weird');
});

void test('purchase page explains the path and no longer uses internal jargon', () => {
    const page = readFileSync(
        new URL('../resources/js/pages/purchase.tsx', import.meta.url),
        'utf8',
    );
    assert.doesNotMatch(page, /Revenue lane|Governed manual sales/);
    assert.match(page, /KMJ confirms payment/);
    assert.match(page, /Access activated/);
    assert.match(page, /Browse the catalog/);
    assert.match(page, /orderProgress\(order\.status\)/);
    assert.match(page, /minorDigits\(order\.currency\)/);
});
