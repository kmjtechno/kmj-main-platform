import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, statSync } from 'node:fs';
import ts from 'typescript';

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

void test('public Kristi guidance selects the actual topic and destination', async () => {
    const functionSource = source.match(
        /function publicGuidanceIndex[\s\S]*?\n}/,
    )?.[0];
    const topicsSource = source.match(/const guidance = \[[\s\S]*?\n\];/)?.[0];
    assert.ok(functionSource && topicsSource);
    const compiled = ts.transpileModule(
        topicsSource +
            '\n' +
            functionSource +
            '\nexport { guidance, publicGuidanceIndex };',
        {
            compilerOptions: {
                module: ts.ModuleKind.ESNext,
                target: ts.ScriptTarget.ES2022,
            },
        },
    ).outputText;
    const { guidance, publicGuidanceIndex } = await import(
        'data:text/javascript;charset=utf-8,' + encodeURIComponent(compiled)
    );
    for (const [query, label, href] of [
        ['technical support', 'Technical support', '#contact'],
        ['ANDROID mobile app', 'Mobile apps & development', '#contact'],
        ['enterprise inquiry', 'General inquiries', '#contact'],
        [
            'pricing and license',
            'Licensing & pricing',
            '/products/kmj-licensing-hub',
        ],
        ['cloud development', 'Software solutions', '/capabilities'],
        ['show products', 'Product information', '/products'],
    ]) {
        const topic = guidance[publicGuidanceIndex(query)];
        assert.equal(topic[0], label, query);
        assert.equal(topic[2], href, query);
    }
});

void test('landing guidance starts collapsed and overview does not promise a missing video', () => {
    const widget =
        source
            .split('function PublicKristi()')[1]
            ?.split('export default')[0] ?? '';
    assert.match(widget, /useState\(false\)/);
    assert.doesNotMatch(widget, /useState\(true\)/);
    assert.match(widget, /Ask Kristi/);
    assert.doesNotMatch(source, /Watch\s+Company Video/);
    assert.match(source, /Engineering IDE/);
});

void test('public homepage exposes accessible account entry without bypassing verification readiness', () => {
    const styles = readFileSync('resources/css/locked-landing.css', 'utf8');
    assert.match(header, /usePage\(\)\.props/);
    assert.match(
        header,
        /registrationAvailable = publicSite\?\.registration_available === true/,
    );
    assert.match(header, /href="\/login"/);
    assert.match(header, /href="\/register"/);
    assert.match(header, /className="lock-auth-login"/);
    assert.match(header, /className="lock-auth-register"/);
    assert.match(header, /lock-mobile-account/);
    assert.match(header, /Registration paused — details/);
    assert.match(styles, /\.lock-auth-login/);
    assert.match(styles, /\.lock-mobile-account/);
    assert.match(
        readFileSync('resources/css/public-theme.css', 'utf8'),
        /max-width: none/,
    );
    assert.match(styles, /@media \(max-width: 1050px\)/);
    assert.match(styles, /@media \(max-width: 560px\)/);
    assert.doesNotMatch(
        header,
        /autoSubmitRegistration|bypassEmailVerification/,
    );
});

void test('locked canvas keeps both account buttons visible on mobile and owner links target secure super-admin', () => {
    const styles = readFileSync('resources/css/locked-landing.css', 'utf8');
    const ownerStyles = readFileSync('resources/css/owner-lock.css', 'utf8');
    const owner = readFileSync(
        'resources/js/components/operator-command-os.tsx',
        'utf8',
    );
    assert.match(
        readFileSync('resources/css/public-theme.css', 'utf8'),
        /max-width: none/,
    );
    assert.match(
        styles,
        /\.lock-auth-register,\s*\.lock-auth-login\s*\{\s*display: inline-flex/,
    );
    assert.doesNotMatch(styles, /\.lock-auth-register\s*\{\s*display: none/);
    assert.match(ownerStyles, /max-width: 1520px/);
    assert.match(owner, /href="\/super-admin"/);
    assert.match(
        header,
        /ownerEnabled\s*\?\s*'\/super-admin'\s*:\s*'\/dashboard'/,
    );
    assert.match(header, /href="\/login"/);
    assert.match(header, /href="\/register"/);
});

void test('owner-configured product imagery never displays an unrelated product visual', async () => {
    const policy = readFileSync(
        'resources/js/lib/product-image-identity.ts',
        'utf8',
    );
    const compiled = ts.transpileModule(policy, {
        compilerOptions: {
            module: ts.ModuleKind.ESNext,
            target: ts.ScriptTarget.ES2022,
        },
    }).outputText;
    const { productImageForSlug } = await import(
        'data:text/javascript;charset=utf-8,' + encodeURIComponent(compiled)
    );

    assert.equal(
        productImageForSlug('kmj-cloudos', '/assets/products/kmj-cloudos.webp'),
        '/assets/products/kmj-cloudos.webp',
    );
    assert.equal(
        productImageForSlug(
            'kmj-codebridge',
            '/assets/products/kmj-codebridge-screenshot.webp',
        ),
        '/assets/products/kmj-codebridge-screenshot.webp',
    );
    assert.equal(
        productImageForSlug(
            'kmj-calibration-pro',
            '/assets/products/kmj-calibration.webp',
        ),
        '/assets/products/kmj-calibration.webp',
    );
    for (const bad of [
        '/assets/products/kmj-cloudos.webp',
        '/assets/products/kmj-codebridge.webp',
        '/assets/products/../private.webp',
        'https://example.com/kmj-omnidesk.webp',
        '/assets/locked/cinema.webp',
        '/assets/products/kmj-omnidesk.svg',
        '/assets/products/kmj-omnidesk.webp?token=secret',
    ])
        assert.equal(productImageForSlug('kmj-omnidesk', bad), null, bad);

    const detail = readFileSync(
        'resources/js/components/public/product-visual.tsx',
        'utf8',
    );
    const artwork = readFileSync(
        'resources/js/components/product-artwork.tsx',
        'utf8',
    );
    assert.match(detail, /productImageForSlug\(slug, imagePath\)/);
    assert.match(
        detail,
        /onError=\{\(\) => setFailedVisual\(generatedVisual\)\}/,
    );
    assert.match(source, /productImageForSlug\(\s*p\.slug,\s*p\.image_path/);
    assert.match(artwork, /<strong>\{name\}<\/strong>/);
    assert.doesNotMatch(policy, /\/private\/|fetch\(|eval\(/);
});

void test('locked and owner product galleries never borrow adjacent product artwork', () => {
    const owner = readFileSync(
        'resources/js/components/operator-command-os.tsx',
        'utf8',
    );
    const css = readFileSync('resources/css/locked-landing.css', 'utf8');
    assert.doesNotMatch(source, /'kmj-cinecore': 'cinema'/);
    for (const oldMapping of [
        "'kmj-cinecore': 'cinema'",
        "'kmj-360-dome': 'cinema'",
        "'kmj-cinema-player': 'cinema'",
        "'kmj-connect': 'omnidesk'",
    ]) {
        assert.ok(!owner.includes(oldMapping), oldMapping);
    }
    assert.match(css, /grid-template-columns: repeat\(4, minmax\(0, 1fr\)\)/);
    assert.match(css, /@media \(max-width: 420px\)/);
    assert.doesNotMatch(
        css,
        /top: calc\(\(100vw - (?:8vw|12vw)\) \/(?:5|3|2)\/2\.12/,
    );
    assert.match(css, /\.lock-product-category \{[\s\S]*?top: 12px;/);
});

void test('official header/footer logo preserves lossless pixels without an opaque backplate', () => {
    const svg = readFileSync(
        'public/assets/brand/kmj-logo-horizontal-readable.svg',
        'utf8',
    );
    assert.doesNotMatch(svg, /<rect\b/);
    const encoded = svg.match(/data:image\/png;base64,([^"]+)/)?.[1];
    assert.ok(encoded);
    assert.deepEqual(
        Buffer.from(encoded, 'base64'),
        readFileSync('public/assets/brand/kmj-email-lockup-dark.png'),
    );
    assert.match(brand, /kmj-logo-horizontal-readable\.svg/);
});

void test('landing uses the same public header/footer components as inner pages', () => {
    assert.match(source, /<PublicSiteHeader \/>/);
    // Prettier puts JSX attributes on separate lines. Still insist on the
    // same shared component and its real product prop, not a duplicate footer.
    assert.match(source, /<PublicSiteFooter\s+products=\{ecosystemProducts\}/);
    assert.equal((source.match(/<PublicSiteFooter\b/g) ?? []).length, 1);
    assert.doesNotMatch(
        source,
        /<header className="lock-header">|<footer className="lock-footer">/,
    );
});

void test('shared logo has a readable vector tagline at desktop and compact sizes', () => {
    for (const [variant, fontSize, width] of [
        ['readable', 56, 1060],
        ['readable-compact', 80, 1060],
    ]) {
        const svg = readFileSync(
            `public/assets/brand/kmj-logo-horizontal-${variant}.svg`,
            'utf8',
        );
        assert.match(svg, /<text[^>]+>INNOVATE \| BUILD \| SCALE<\/text>/);
        assert.ok(svg.includes(`font-size="${fontSize}"`));
        assert.match(svg, /clip-path="url\(#official-wordmark\)"/);
        assert.doesNotMatch(svg, /<rect\b/);
        const minimumRenderedWidth = variant === 'readable-compact' ? 108 : 180;
        assert.ok(
            (fontSize * minimumRenderedWidth) / width >= 8,
            'tagline must stay at least eight CSS pixels high at the smallest supported logo width',
        );
    }
    assert.match(brand, /media="\(max-width: 560px\)"/);
});
