import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const page = readFileSync(
    new URL('../resources/js/pages/dashboard.tsx', import.meta.url),
    'utf8',
);

void test('customer dashboard shows purchasable products first and folds the rest away', () => {
    assert.match(page, /product\.purchase_enabled/);
    assert.match(page, /products-available/);
    assert.match(page, /<details[\s\S]*?products-upcoming/);
    assert.match(page, /In development \(/);
});
