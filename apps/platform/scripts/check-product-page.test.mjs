import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) =>
    readFileSync(new URL('../' + path, import.meta.url), 'utf8');
const page = read('resources/js/pages/products/show.tsx');

void test('product page keeps internal words and invented proof off screen', () => {
    assert.doesNotMatch(
        page,
        /Canonical|Entitlement governed|Operational boundary|verifiable authority/,
    );
    assert.match(page, /illustrative, not measured results/);
    assert.doesNotMatch(page, /aggregateRating|Most popular|trusted by/i);
});

void test('questions shown on the page are the ones published to search', () => {
    assert.match(page, /mainEntity: answers\.map/);
    assert.match(page, /answers\.map\(\(item, index\)/);
    assert.match(
        read('app/Services/Seo/PublicInitialMetadata.php'),
        /\$page\['props'\]\['answers'\]/,
    );
    assert.match(read('resources/views/app.blade.php'), /<noscript>/);
});
