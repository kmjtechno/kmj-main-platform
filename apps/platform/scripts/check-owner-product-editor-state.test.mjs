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

void test('pricing book covers the canonical product registry without enabling commerce', () => {
    const book = JSON.parse(
        readFileSync(
            new URL(
                '../resources/private/kmj-commercial-pricebook-20261123.json',
                import.meta.url,
            ),
            'utf8',
        ),
    );
    assert.equal(book.status, 'owner_review_only');
    assert.equal(book.checkout_enabled, false);
    assert.equal(book.live_payment_enabled, false);
    assert.equal(book.customer_visible, false);
    assert.equal(book.approved_for_commercial_orders, false);
    assert.equal(book.automatic_license_issuance_enabled, false);
    assert.equal(book.products.length, 15);
    assert.equal(new Set(book.products.map((p) => p.slug)).size, 15);

    const registry = readFileSync(
        new URL('../app/Services/Commerce/KmjProductCatalog.php', import.meta.url),
        'utf8',
    );
    for (const product of book.products) {
        assert.equal(product.pricing_status, 'review_only');
        assert.equal(product.ready_to_sell, false);
        assert.equal(product.payment_and_tax, 'not_approved');
        assert.match(product.slug, /^kmj-[a-z0-9-]+$/);
        assert.equal(typeof product.name, 'string');
        for (const amount of [
            product.entry_amount_minor,
            product.annual_amount_minor,
        ]) {
            assert.ok(
                amount === null ||
                    (Number.isSafeInteger(amount) && amount >= 0),
                product.slug,
            );
        }
        if (product.slug !== 'kmj-cloudos') {
            assert.ok(registry.includes(`'${product.slug}'`), product.slug);
        }
    }
    assert.equal(book.supplemental_unregistered.length, 4);
});

void test('preexisting CodeBridge owner pricing and bundle math are preserved', () => {
    const book = JSON.parse(
        readFileSync(
            new URL(
                '../resources/private/kmj-commercial-pricebook-20261123.json',
                import.meta.url,
            ),
            'utf8',
        ),
    );
    const codebridge = book.products.find((p) => p.slug === 'kmj-codebridge');
    assert.equal(codebridge.entry_amount_minor, 29900);
    assert.equal(codebridge.annual_amount_minor, 249900);
    assert.equal(codebridge.team_amount_minor_per_user, 69900);
    assert.equal(
        codebridge.pricing_source,
        'owner_approved_existing_reference',
    );
    const omnidesk = book.products.find((p) => p.slug === 'kmj-omnidesk');
    const bundle = book.bundle_ideas[0];
    assert.ok(
        bundle.monthly_amount_minor <
            codebridge.entry_amount_minor + omnidesk.entry_amount_minor,
    );
    assert.ok(
        bundle.annual_amount_minor <
            codebridge.annual_amount_minor + omnidesk.annual_amount_minor,
    );
    assert.equal(bundle.activation_enabled, false);
});

void test('proposal preview stays behind owner auth, never a checkout API', () => {
    const source = readFileSync(
        new URL('../routes/product-manager.php', import.meta.url),
        'utf8',
    );
    const page = readFileSync(
        new URL('../resources/js/pages/operator-products.tsx', import.meta.url),
        'utf8',
    );
    const service = readFileSync(
        new URL(
            '../app/Services/Commerce/CommercialPriceProposalBook.php',
            import.meta.url,
        ),
        'utf8',
    );
    assert.match(source, /PlatformOwnerAccess/);
    assert.match(source, /'auth', 'verified', 'password.confirm'/);
    assert.match(source, /'pricingProposal' => \$priceBook->snapshot\(\)/);
    assert.match(page, /Owner review only/);
    assert.match(page, /Unapproved proposal/);
    assert.match(service, /owner_review_only/);
    assert.match(service, /approved_for_commercial_orders/);
    assert.doesNotMatch(service, /DB::|->save\(|->insert\(/);
});
