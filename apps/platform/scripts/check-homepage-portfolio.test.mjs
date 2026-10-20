import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, statSync } from 'node:fs';

const source = readFileSync('resources/js/pages/welcome.tsx', 'utf8');
const brand = readFileSync('resources/js/components/locked-brand.tsx', 'utf8');
const header = readFileSync(
    'resources/js/components/public-site-header.tsx',
    'utf8',
);
const footer = readFileSync(
    'resources/js/components/public-site-footer.tsx',
    'utf8',
);

void test('the locked KMJ brand is the single shared public header/footer asset', () => {
    assert.match(brand, /\/assets\/brand\/kmj-logo-horizontal\.webp/);
    assert.match(brand, /INNOVATE \| BUILD \| SCALE/);
    assert.match(header, /<LockedBrand compact/);
    assert.match(footer, /<LockedBrand/);
    assert.ok(
        statSync('public/assets/brand/kmj-logo-horizontal.webp').size > 1024,
    );
});

void test('public hero describes cross-platform engineering without inventing product availability', () => {
    assert.match(source, /Build Any Software\./);
    assert.match(source, /Power Every[\s\S]*?Experience\./);
    assert.match(
        source,
        /Product\s+availability and access remain governed by/,
    );
    assert.match(source, /verified lifecycle and release states/);
});

void test('homepage offers eight distinct capability areas and accessible navigation', () => {
    const block =
        source.split('const whatWeBuild = [')[1]?.split('];')[0] ?? '';
    const titles = [...block.matchAll(/title: '([^']+)'/g)].map((m) => m[1]);
    assert.equal(titles.length, 8);
    assert.equal(new Set(titles).size, 8);
    for (const area of [
        'Mobile applications',
        'Web platforms',
        'Desktop applications',
        'AI & automation',
        'Enterprise systems',
        'Industrial technology',
        'Immersive experiences',
    ]) {
        assert.ok(titles.includes(area), area);
    }
    assert.match(source, /aria-labelledby="what-we-build-heading"/);
    assert.match(source, /href="\/capabilities"/);
});

void test('company overview preserves keyboard focus and Escape semantics', () => {
    for (const primitive of [
        'DialogPrimitive.Root',
        'DialogPrimitive.Trigger',
        'DialogPrimitive.Overlay',
        'DialogPrimitive.Content',
        'DialogPrimitive.Close',
        'DialogPrimitive.Title',
        'DialogPrimitive.Description',
    ])
        assert.ok(source.includes(primitive), primitive);
    assert.match(source, /onOpenChange=\{setTour\}/);
    assert.match(source, /aria-label="Company overview"/);
    assert.match(
        source,
        /<DialogPrimitive\.Title[\s\S]*?className="sr-only"[\s\S]*?Company overview[\s\S]*?<\/DialogPrimitive\.Title>/,
    );
    assert.match(source, /<h2>Build\. Connect\. Scale\.<\/h2>/);
    assert.doesNotMatch(source, /\{tour &&/);
});

void test('unrecognized public products never inherit unrelated cinema artwork', () => {
    assert.match(source, /<ProductArtwork/);
    assert.match(source, /artwork\[p\.slug\]/);
    assert.match(source, /p\.image_path/);
    assert.match(source, /lock-product-art-unavailable/);
    assert.match(source, /artwork not available/);
    assert.doesNotMatch(
        source,
        /p\.image_path\s*\|\|\s*['"]\/assets\/locked\/cinema\.webp/,
    );
});

void test('loaded KMJ artwork keeps original geometry while missing assets fail closed', () => {
    const image = readFileSync(
        'resources/js/components/product-artwork.tsx',
        'utf8',
    );
    assert.match(image, /onError=\{\(\) => setFailedSource\(source\)\}/);
    assert.match(image, /failedSource !== source/);
    assert.match(image, /loading="lazy"/);
    assert.match(image, /alt=\{name \+ ' product artwork'\}/);
    assert.match(image, /aria-label=\{name \+ ' artwork not available'\}/);
    assert.match(source, /fallbackClassName="lock-product-art-unavailable"/);
    assert.doesNotMatch(image, /(?:cinema|cloudos)\.webp/);
});

void test('public Kristi guidance routes support, mobile and licensing honestly', () => {
    assert.match(
        source,
        /function publicGuidanceIndex\(input: string\): number/,
    );
    assert.match(source, /if \(\/support\|help/);
    assert.match(source, /if \(\/android\|ios\|mobile/);
    assert.match(source, /setAnswer\(publicGuidanceIndex\(query\)\)/);
    assert.doesNotMatch(source, /\/licens\|price\/i\.test\(query\)/);
});


void test('public homepage exposes accessible account entry without bypassing verification readiness', () => {
    const styles = readFileSync('resources/css/locked-landing.css', 'utf8');
    assert.match(source, /usePage\(\)\.props/);
    assert.match(source, /registrationAvailable = publicSite\?\.registration_available === true/);
    assert.match(source, /href="\/login"/);
    assert.match(source, /href="\/register"/);
    assert.match(source, /className="lock-auth-login"/);
    assert.match(source, /className="lock-auth-register"/);
    assert.match(source, /lock-mobile-account/);
    assert.match(source, /Registration paused — details/);
    assert.match(styles, /\.lock-auth-login/);
    assert.match(styles, /\.lock-mobile-account/);
    assert.match(styles, /max-width: 1360px/);
    assert.match(styles, /@media \(max-width: 1050px\)/);
    assert.match(styles, /@media \(max-width: 560px\)/);
    assert.doesNotMatch(source, /autoSubmitRegistration|bypassEmailVerification/);
});
