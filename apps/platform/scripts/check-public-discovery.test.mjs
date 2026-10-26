// Deterministic, network-free SEO/GEO source contract. This prevents the
// canonical sitemap and server indexing policy from silently diverging.
// It is NOT a substitute for production Search Console or a live crawler.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

function source(relative) {
    return readFileSync(new URL('../' + relative, import.meta.url), 'utf8');
}

const routes = source('routes/web.php');
const blade = source('resources/views/app.blade.php');
const seo = source('resources/js/components/public-seo.tsx');
const robots = source('public/robots.txt');
const legalPaths = [
    '/legal',
    '/terms',
    '/privacy',
    '/refund-policy',
    '/acceptable-use',
    '/cookie-policy',
];

test('sitemap legal pages pass the server indexability gate', () => {
    const sitemap = routes
        .split("Route::get('sitemap.xml'")[1]
        ?.split("})->name('sitemap');")[0];
    assert.ok(sitemap, 'sitemap endpoint must exist');
    for (const path of legalPaths) {
        assert.ok(
            sitemap.includes("'" + path + "'"),
            path + ' must remain in the public sitemap',
        );
    }
    const allowlist = blade.split('request()->routeIs(')[1]?.split(');')[0];
    assert.ok(allowlist, 'server must explicitly classify public routes');
    assert.match(allowlist, /'legal\.\*'/);
    assert.match(allowlist, /'home'/);
    assert.match(allowlist, /'products\.\*'/);
    assert.match(allowlist, /'trust'/);
    assert.doesNotMatch(allowlist, /'auth\.\*'|'operator\.\*'|'dashboard'/);
    assert.match(blade, /app\.public_indexing.*\$publicIndexableRoute/);
});

test('public canonical, social cards and structured data exist', () => {
    assert.match(seo, /rel="canonical"/);
    assert.match(seo, /property="og:url"/);
    assert.match(seo, /property="og:image"/);
    assert.match(seo, /name="twitter:card"/);
    assert.match(seo, /application\/ld\+json/);
    assert.match(seo, /publicSite\.indexable/);
    assert.match(seo, /'noindex,nofollow'/);
    assert.match(routes, /\$product\['lifecycle_label'\]/);
    assert.match(routes, /preview labels must not be interpreted/);
});

test('robots and XML sitemap keep public-only paths', () => {
    assert.match(robots, /^User-agent: \*$/m);
    assert.match(robots, /^Sitemap: https:\/\/kmjtechno\.com\/sitemap\.xml$/m);
    assert.doesNotMatch(robots, /Disallow: \//);
    const sitemap = routes
        .split("Route::get('sitemap.xml'")[1]
        ?.split("})->name('sitemap');")[0];
    assert.ok(sitemap);
    assert.match(sitemap, /config\('app\.public_indexing', false\)/);
    assert.match(sitemap, /htmlspecialchars/);
    assert.doesNotMatch(sitemap, /\/dashboard|\/operator|\/login/);
    assert.doesNotMatch(sitemap, /\/api\/codebridge/);
});

test('AI discovery retains truthful lifecycle information', () => {
    const llms = routes
        .split("Route::get('llms.txt'")[1]
        ?.split("})->name('llms');")[0];
    assert.ok(llms, 'AI-readable optional discovery route must exist');
    assert.match(llms, /\$product\['lifecycle_label'\]/);
    assert.match(llms, /\$products->all\(\)/);
    assert.match(llms, /prefer the canonical product page and lifecycle label/);
    assert.doesNotMatch(llms, /#1 globally|guaranteed AI ranking/i);
});
