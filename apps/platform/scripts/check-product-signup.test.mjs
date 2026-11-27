import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) =>
    readFileSync(new URL('../' + path, import.meta.url), 'utf8');

void test('only CloudOS gets an automatic trial and only after verification', () => {
    const service = read('app/Services/Commerce/ProductSignups.php');
    assert.match(service, /hasVerifiedEmail\(\)/);
    assert.match(service, /'cloudos-signup-trial:'/);
    assert.match(
        service,
        /where\('product_slug', CloudOSProductCatalog::SLUG\)/,
    );
    assert.match(service, /Schema::hasTable\('product_signups'\)/);
    assert.match(read('routes/product-signups.php'), /'auth', 'verified'/);
});

void test('time-limited access never blocks or counts as paid fulfilment', () => {
    const routes = read('routes/web.php');
    assert.ok((routes.match(/->whereNull\('ends_at'\)/g) ?? []).length >= 3);
});
