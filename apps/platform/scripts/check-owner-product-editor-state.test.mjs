import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
    withNewProductName,
    withProductLifecycle,
} from '../resources/js/lib/product-editor-state.mjs';

const form = {
    name: 'Old product',
    slug: 'old-product',
    lifecycle: 'available',
    purchase_enabled: true,
    summary: 'Keep the user-written draft',
    content: { features: ['Original feature'], image_alt: 'Kept artwork' },
};

void test('product name and slug update atomically without dropping draft fields', () => {
    const changed = withNewProductName(form, 'KMJ Calibration Pro 2.0');
    assert.equal(changed.name, 'KMJ Calibration Pro 2.0');
    assert.equal(changed.slug, 'kmj-calibration-pro-2-0');
    assert.equal(changed.summary, form.summary);
    assert.equal(changed.content, form.content);
    assert.equal(form.name, 'Old product');
});

void test('manually entered slug is never overridden by name suggestions', () => {
    const changed = withNewProductName(form, 'New product name', true);
    assert.equal(changed.slug, 'old-product');
    assert.equal(changed.name, 'New product name');
});

void test('slug keeps the existing normalization and length safeguards', () => {
    assert.equal(
        withNewProductName(form, '  Café & Cloud OS!  ').slug,
        'cafe-cloud-os',
    );
    assert.ok(withNewProductName(form, 'a'.repeat(150)).slug.length <= 96);
});

void test('non-Available lifecycle always clears purchase permission atomically', () => {
    for (const lifecycle of [
        'preview',
        'public-beta',
        'research',
        'planned',
        'retired',
    ]) {
        const changed = withProductLifecycle(form, lifecycle);
        assert.equal(changed.lifecycle, lifecycle);
        assert.equal(changed.purchase_enabled, false);
        assert.equal(changed.content, form.content);
    }
    assert.equal(form.purchase_enabled, true);
});

void test('moving back to Available never grants purchase permission implicitly', () => {
    const planned = withProductLifecycle(form, 'planned');
    const available = withProductLifecycle(planned, 'available');
    assert.equal(available.lifecycle, 'available');
    assert.equal(available.purchase_enabled, false);
});

void test('new and existing owner editors use one atomic Inertia state update', () => {
    const source = readFileSync(
        new URL(
            '../resources/js/components/operator-product-manager.tsx',
            import.meta.url,
        ),
        'utf8',
    );
    assert.match(source, /withNewProductName\(current, name, slugEdited\)/);
    assert.equal(
        (source.match(/withProductLifecycle\(current, lifecycle\)/g) ?? [])
            .length,
        2,
    );
    assert.doesNotMatch(source, /form\.setData\('lifecycle', lifecycle\)/);
    assert.doesNotMatch(source, /form\.setData\('purchase_enabled', false\)/);
    assert.doesNotMatch(source, /form\.setData\('name', name\)/);
});
