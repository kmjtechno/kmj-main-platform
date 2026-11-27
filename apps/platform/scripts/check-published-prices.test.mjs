import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { priceLines } from '../resources/js/lib/price-labels.ts';

const json = (path) =>
    JSON.parse(readFileSync(new URL('../' + path, import.meta.url), 'utf8'));
const published = json('resources/pricing/published-prices.json');
const draft = json('resources/private/kmj-commercial-pricebook-20261123.json');

void test('published list matches the approved 23 Nov amounts', () => {
    assert.equal(published.tax, 'plus_gst');
    assert.equal(published.checkout_enabled, false);
    const sellable = draft.products.filter(
        (p) => p.entry_amount_minor !== null,
    );
    assert.equal(Object.keys(published.products).length, sellable.length);

    for (const product of sellable) {
        const plans = published.products[product.slug];
        assert.ok(plans, product.slug);
        const amounts = plans.flatMap((plan) => [
            plan.monthly_minor,
            plan.annual_minor,
            plan.quote_from_minor,
        ]);

        for (const key of [
            'entry_amount_minor',
            'annual_amount_minor',
            'secondary_amount_minor',
            'team_amount_minor_per_user',
            'team_annual_amount_minor_per_user',
        ]) {
            if (product[key]) {
                assert.ok(
                    amounts.includes(product[key]),
                    `${product.slug} ${key}`,
                );
            }
        }

        // Nothing invented: every paid amount exists in the draft.
        const known = new Set(Object.values(product));
        for (const amount of amounts.filter(Boolean)) {
            assert.ok(known.has(amount), `${product.slug} ${amount}`);
        }
        assert.equal(
            plans.some((plan) => plan.quote_from_minor !== undefined),
            product.quote_only === true,
        );
    }
});

void test('price wording states GST, quote and minimum seats', () => {
    assert.deepEqual(priceLines(published.products['kmj-codebridge'][1]), [
        '₹299 + GST per user / month',
        'or ₹2,499 + GST per user / year',
    ]);
    assert.deepEqual(priceLines(published.products['kmj-calibration-pro'][0]), [
        'Price on quote · from ₹9,999 + GST per site',
    ]);
    assert.deepEqual(priceLines(published.products['kmj-codebridge'][0]), [
        'Free',
    ]);
    assert.ok(
        priceLines(published.products['kmj-connect'][0]).includes(
            'Minimum 3 seats',
        ),
    );
});
