import assert from 'node:assert/strict';
import test from 'node:test';
import { compareProductCategories } from '../resources/js/lib/product-category-order.mjs';

void test('interleaved backend categories render one contiguous group each', () => {
    const categories = [
        'Cloud & Infrastructure',
        'Industrial & Calibration',
        'Cinema & Immersive',
        'Business & Platform',
        'Developer & AI',
        'Business & Platform',
        'Cloud & Infrastructure',
        'Developer & AI',
    ];
    const sorted = [...categories].sort(compareProductCategories);
    const headings = sorted.filter(
        (category, index) => index === 0 || category !== sorted[index - 1],
    );
    assert.equal(headings.length, new Set(categories).size);
    assert.equal(sorted.length, categories.length);
});

void test('unknown categories stay contiguous without dropping products', () => {
    const sorted = [
        'Zeta',
        'Other',
        'Zeta',
        'Cloud & Infrastructure',
        'Other',
    ].sort(compareProductCategories);
    assert.deepEqual(sorted, [
        'Cloud & Infrastructure',
        'Other',
        'Other',
        'Zeta',
        'Zeta',
    ]);
    assert.equal(
        compareProductCategories('Developer & AI', 'Developer & AI'),
        0,
    );
});
