import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { deliverProductLink } from '../resources/js/lib/product-share-actions.mjs';

const title = 'KMJ CineCore — KMJ TECHNO';
const url = 'https://kmjtechno.com/products/kmj-cinecore';

void test('native share succeeds without copying', async () => {
    let payload;
    let copies = 0;
    const result = await deliverProductLink({
        mode: 'share',
        title,
        url,
        nativeShare: async (data) => {
            payload = data;
        },
        copyText: async () => {
            copies++;
        },
    });
    assert.equal(result, 'shared');
    assert.deepEqual(payload, { title, text: title, url });
    assert.equal(copies, 0);
});

void test('native share cancellation never writes the clipboard', async () => {
    let copies = 0;
    const result = await deliverProductLink({
        mode: 'share',
        title,
        url,
        nativeShare: async () => {
            throw Object.assign(new Error('cancelled'), { name: 'AbortError' });
        },
        copyText: async () => {
            copies++;
        },
    });
    assert.equal(result, 'cancelled');
    assert.equal(copies, 0);
});

void test('native share rejection falls back to a verified copy', async () => {
    const copied = [];
    const result = await deliverProductLink({
        mode: 'share',
        title,
        url,
        nativeShare: async () => {
            throw Object.assign(new Error('blocked'), { name: 'NotAllowedError' });
        },
        copyText: async (value) => {
            copied.push(value);
        },
    });
    assert.equal(result, 'copied');
    assert.deepEqual(copied, [url]);
});

void test('missing native share safely uses clipboard', async () => {
    const copied = [];
    const result = await deliverProductLink({
        mode: 'share',
        title,
        url,
        copyText: async (value) => {
            copied.push(value);
        },
    });
    assert.equal(result, 'copied');
    assert.deepEqual(copied, [url]);
});

void test('copy button does not activate native share', async () => {
    let shares = 0;
    const result = await deliverProductLink({
        mode: 'copy',
        title,
        url,
        nativeShare: async () => {
            shares++;
        },
        copyText: async () => {},
    });
    assert.equal(result, 'copied');
    assert.equal(shares, 0);
});

void test('denied clipboard write never claims copied', async () => {
    assert.equal(
        await deliverProductLink({
            mode: 'copy',
            title,
            url,
            copyText: async () => {
                throw new Error('permission denied');
            },
        }),
        'unavailable',
    );
});

void test('unavailable browser APIs fail closed', async () => {
    for (const mode of ['copy', 'share']) {
        assert.equal(
            await deliverProductLink({ mode, title, url }),
            'unavailable',
        );
    }
});

void test('product page has accessible status and synchronous click guard', () => {
    const source = readFileSync(
        'resources/js/components/public/product-share.tsx',
        'utf8',
    );
    assert.match(source, /deliverProductLink\(/);
    assert.match(source, /role="status"/);
    assert.match(source, /aria-live="polite"/);
    assert.match(source, /inFlight\.current/);
    assert.doesNotMatch(source, /window\.setTimeout/);
    assert.doesNotMatch(source, /await navigator\.clipboard\.writeText/);
});
