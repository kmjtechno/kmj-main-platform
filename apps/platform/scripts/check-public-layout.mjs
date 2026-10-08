// Executable regression check for public Inertia layouts.
// Run from apps/platform after npm ci: node scripts/check-public-layout.mjs
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import ts from 'typescript';

const root = resolve(import.meta.dirname, '..');
const appSource = readFileSync(join(root, 'resources/js/app.tsx'), 'utf8');
const publicSource = readFileSync(
    join(root, 'resources/js/lib/public-page-layout.ts'),
    'utf8',
);
const compiled = ts.transpileModule(publicSource, {
    compilerOptions: {
        module: ts.ModuleKind.ESNext,
        target: ts.ScriptTarget.ES2022,
    },
}).outputText;
const url = 'data:text/javascript;charset=utf-8,' + encodeURIComponent(compiled);
const { isPublicMarketingPage } = await import(url);

const publicPages = [
    'welcome',
    'company',
    'capabilities',
    'trust',
    'public-page',
    'products/index',
    'products/show',
    'products/codebridge/terms',
    'products/codebridge/privacy',
    'products/codebridge/support',
    'legal/index',
    'legal/terms',
    'legal/privacy',
    'legal/refund-policy',
    'legal/acceptable-use',
    'legal/cookie-policy',
];
const protectedPages = [
    'dashboard',
    'purchase',
    'sandbox-licenses',
    'operator',
    'operator-ops',
    'operator-kslp',
    'info',
    'info-control',
    'services/codebridge',
    'auth/login',
    'auth/register',
    'settings/profile',
    'products/internal-manager',
    'legal/operator-private',
];

for (const page of publicPages) {
    assert.equal(isPublicMarketingPage(page), true, page + ' must be standalone');
    assert.equal(
        existsSync(join(root, 'resources/js/pages', page + '.tsx')),
        true,
        page + ' missing component',
    );
}
// Every standalone page must own a visible public shell, directly or through
// the shared LegalDocument component. A half-wrapped page looks unfinished.
for (const page of publicPages) {
    const source = readFileSync(
        join(root, 'resources/js/pages', page + '.tsx'),
        'utf8',
    );
    assert.ok(
        source.includes('PublicSiteHeader') ||
            source.includes('LegalDocument'),
        page + ' is missing its public header',
    );
    assert.ok(
        source.includes('PublicSiteFooter') ||
            source.includes('LegalDocument'),
        page + ' is missing its public footer',
    );
    assert.ok(
        source.includes('id="main-content"') ||
            source.includes('LegalDocument'),
        page + ' has no skip-navigation destination',
    );
}
const legalDocument = readFileSync(
    join(root, 'resources/js/components/legal/legal-document.tsx'),
    'utf8',
);
assert.match(legalDocument, /<PublicSiteHeader \/>/);
assert.match(legalDocument, /<PublicSiteFooter \/>/);
assert.match(legalDocument, /id="main-content"/);

for (const page of protectedPages) {
    assert.equal(
        isPublicMarketingPage(page),
        false,
        page + ' must not be silently reclassified public',
    );
}

assert.match(
    appSource,
    /case isPublicMarketingPage\(name\):\s*return null;/,
    'public pages must not inherit AppLayout sidebar',
);
assert.match(appSource, /case name\.startsWith\('auth\/'\):/);
assert.match(appSource, /case name\.startsWith\('settings\/'\):/);
assert.match(appSource, /default:\s*return AppLayout;/);

const header = readFileSync(
    join(root, 'resources/js/components/public-site-header.tsx'),
    'utf8',
);
assert.match(header, /aria-label=\{open \? 'Close navigation' : 'Open navigation'\}/);
assert.equal(
    (header.match(/lg:hidden/g) ?? []).length,
    2,
    'tablet header must render both the menu toggle and expanded navigation',
);
assert.match(
    header,
    /<nav className="hidden items-center gap-1 lg:flex">/,
    'desktop navigation must appear at lg while the mobile menu hides at lg',
);
assert.doesNotMatch(
    header,
    /sm:hidden|md:hidden/,
    'a smaller breakpoint must not remove mobile navigation before desktop navigation appears',
);

const footer = readFileSync(
    join(root, 'resources/js/components/public-site-footer.tsx'),
    'utf8',
);
assert.match(footer, /const \{ auth \} = usePage\(\)\.props;/);
assert.match(footer, /\{auth\.user \? \(/);
assert.match(footer, /href=\{dashboard\(\)\}/);

const productPage = readFileSync(
    join(root, 'resources/js/pages/products/index.tsx'),
    'utf8',
);
assert.match(productPage, /<PublicSiteHeader \/>/);
assert.match(productPage, /<PublicSiteFooter \/>/);
assert.match(productPage, /business and engineering\./);
assert.match(productPage, /text-white\/72/);

// Readability regression: body copy, status labels, and microcopy must not
// disappear into the dark marketing background at sub-50% text opacity.
for (const page of [
    'welcome',
    'company',
    'capabilities',
    'trust',
    'legal/index',
    'products/index',
    'products/show',
]) {
    const source = readFileSync(
        join(root, 'resources/js/pages', page + '.tsx'),
        'utf8',
    );
    assert.doesNotMatch(
        source,
        new RegExp('text-white/(?:[0-4][0-9])(?![0-9])'),
        page + ' contains low-contrast marketing text',
    );
}

// The public and logged-in areas must share one official KMJ mark asset;
// a starter-template SVG or old third-party mark looks like another brand.
const officialMark = '/assets/brand/kmj-mark.webp';
assert.ok(existsSync(join(root, 'public', officialMark.slice(1))));
const appLogo = readFileSync(
    join(root, 'resources/js/components/app-logo.tsx'),
    'utf8',
);
const appIcon = readFileSync(
    join(root, 'resources/js/components/app-logo-icon.tsx'),
    'utf8',
);
assert.ok(appLogo.includes(officialMark));
assert.ok(appIcon.includes(officialMark));
assert.doesNotMatch(appIcon, /fillRule="evenodd"/);

// Every statically referenced product visual must ship with the public build.
// Dynamic catalog image_path values still require database + browser acceptance.
const imagePattern = new RegExp('/assets/products/[A-Za-z0-9_-]+[.]webp', 'g');
const imageReferences = new Set();
for (const page of ['welcome', 'products/show']) {
    const source = readFileSync(
        join(root, 'resources/js/pages', page + '.tsx'),
        'utf8',
    );
    for (const image of source.matchAll(imagePattern)) {
        imageReferences.add(image[0]);
    }
}
assert.ok(imageReferences.size > 0, 'public product images were not discovered');
for (const imagePath of imageReferences) {
    assert.ok(
        existsSync(join(root, 'public', imagePath.slice(1))),
        imagePath + ' is missing from public assets',
    );
}

console.log(
    'PUBLIC_SITE_LAYOUT_PASS: ' +
        publicPages.length +
        ' standalone pages, ' +
        protectedPages.length +
        ' protected pages, responsive navigation',
);
