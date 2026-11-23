import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';

const md5 = (path) =>
    createHash('md5').update(readFileSync(path)).digest('hex');

// Blobs of the stock Laravel starter-kit icons that previously shipped as the
// browser tab icon (favicon.ico) and iOS home-screen icon (apple-touch-icon.png).
const LARAVEL_DEFAULT_ICON_MD5 = new Set([
    '08242d646ff63d0fa7f43b1f34868700',
    '4ec34bfee5050d402638888ce2e9a968',
]);

void test('browser and home-screen icons are the KMJ brand, not the Laravel defaults', () => {
    for (const file of ['public/favicon.ico', 'public/apple-touch-icon.png']) {
        assert.ok(
            !LARAVEL_DEFAULT_ICON_MD5.has(md5(file)),
            `${file} is the stock Laravel icon`,
        );
    }

    const png = readFileSync('public/apple-touch-icon.png');
    assert.equal(png.subarray(1, 4).toString(), 'PNG');
    assert.equal(png.readUInt32BE(16), 180);
    assert.equal(png.readUInt32BE(20), 180);

    const ico = readFileSync('public/favicon.ico');
    assert.equal(
        ico.readUInt16LE(2),
        1,
        'favicon.ico must be an icon resource',
    );
    assert.ok(ico.readUInt16LE(4) >= 2, 'favicon.ico must carry several sizes');

    const svg = readFileSync('public/favicon.svg', 'utf8');
    assert.match(svg, /<image /);
});

void test('page head references the KMJ icon set and no external icon', () => {
    const head = readFileSync('resources/views/app.blade.php', 'utf8');
    // The contrast variant is the reviewed, accessible favicon. Legacy
    // .ico/.svg resources remain available for browser fallbacks, but the
    // document must consistently select the high-contrast KMJ emblem.
    assert.match(
        head,
        /<link rel="icon" href="\/favicon-contrast-v1\.svg" type="image\/svg\+xml" sizes="any">/,
    );
    assert.match(head, /href="\/apple-touch-icon\.png"/);
    assert.doesNotMatch(head, /href="https?:\/\/[^"]*icon/i);
    assert.doesNotMatch(head, /laravel/i);
});

function walk(dir, out = []) {
    for (const name of readdirSync(dir)) {
        const path = join(dir, name);
        if (statSync(path).isDirectory()) walk(path, out);
        else if (/\.(tsx?|css|blade\.php)$/.test(name)) out.push(path);
    }
    return out;
}

void test('customer-facing UI source carries no Laravel starter-kit links or logos', () => {
    for (const file of walk('resources/js').concat(walk('resources/views'))) {
        const text = readFileSync(file, 'utf8');
        assert.doesNotMatch(
            text,
            /laravel\.com|laravel\/react-starter-kit|laravel-logo/i,
            `${file} still references Laravel starter-kit branding`,
        );
    }
});
