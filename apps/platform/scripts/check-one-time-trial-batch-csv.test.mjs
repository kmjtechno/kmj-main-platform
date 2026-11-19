import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildOneTimeTrialBatchCsv } from '../resources/js/lib/one-time-trial-batch-csv.mjs';

const batch = [
    {
        customer_id: '@signed-customer',
        product_code: 'VENDOR.APP',
        license_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        key: 'KMJ1-' + 'A'.repeat(43),
    },
    {
        customer_id: 'customer-2',
        product_code: 'VENDOR.APP',
        license_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
        key: 'KMJ1-' + 'B'.repeat(43),
    },
];

test('bounded, one-time CSV preserves exact secrets only in local return value', () => {
    const csv = buildOneTimeTrialBatchCsv(batch);
    assert.equal(csv.split('\r\n').filter(Boolean).length, 3);
    assert.match(csv, /one_time_trial_bootstrap_key/);
    assert.match(csv, /KMJ1-A{43}/);
    assert.match(csv, /KMJ1-B{43}/);
    assert.match(csv, /"''?@signed-customer"/);
    assert.ok(csv.startsWith('customer_id,product_code,license_id'));
});

test('rejects forged, duplicate, paid-like or unbounded payloads', () => {
    for (const value of [
        [],
        [batch[0]],
        Array(11).fill(batch[0]),
        [{ ...batch[0], key: 'FAKE' }, batch[1]],
        [{ ...batch[0], customer_id: '=2+3' }, batch[1]],
        [{ ...batch[0], product_code: 'INVALID;FILE' }, batch[1]],
        [{ ...batch[0], license_id: 'malformed' }, batch[1]],
        [batch[0], { ...batch[1], license_id: batch[0].license_id }],
        [batch[0], { ...batch[1], customer_id: batch[0].customer_id }],
    ]) {
        assert.throws(
            () => buildOneTimeTrialBatchCsv(value),
            /KSLP_ONE_TIME_TRIAL_BATCH_(?:SIZE|SHAPE)_REJECTED/,
        );
    }
});

test('helper is side-effect free; download must stay in one-time UI on explicit confirmation', () => {
    const helper = readFileSync(
        'resources/js/lib/one-time-trial-batch-csv.mjs',
        'utf8',
    );
    const page = readFileSync('resources/js/pages/developer-apps.tsx', 'utf8');
    assert.doesNotMatch(
        helper,
        /\b(fetch|XMLHttpRequest|sendBeacon|localStorage|sessionStorage|indexedDB|console\.log|navigator\.sendBeacon)\b/,
    );
    assert.ok(page.includes('buildOneTimeTrialBatchCsv'));
    assert.ok(page.includes('window.confirm('));
    assert.ok(page.includes('Download one-time trial batch CSV'));
    assert.ok(page.includes('newKeys && newKeys.length > 0'));
    assert.ok(page.includes('URL.revokeObjectURL('));
});
