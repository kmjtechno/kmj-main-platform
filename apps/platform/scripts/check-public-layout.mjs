// Executable regression check for public Inertia layouts.
// Run from apps/platform after npm ci: node scripts/check-public-layout.mjs
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
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
assert.match(header, /lg:hidden/, 'menu toggle must exist on tablet sizes');

console.log(
    'PUBLIC_SITE_LAYOUT_PASS: ' +
        publicPages.length +
        ' standalone pages, ' +
        protectedPages.length +
        ' protected pages, responsive navigation',
);
