import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { format } from 'oxfmt';
import { assertPublicNavigation } from './assert-public-navigation.mjs';

const header = readFileSync(
    new URL(
        '../resources/js/components/public-site-header.tsx',
        import.meta.url,
    ),
    'utf8',
);

void test('navigation guards accept the actual header after the locked formatter wraps JSX attributes', async () => {
    const result = await format('public-site-header.tsx', header, {
        printWidth: 80,
        tabWidth: 4,
        singleQuote: true,
        semi: true,
        singleAttributePerLine: false,
        htmlWhitespaceSensitivity: 'css',
    });
    assert.equal(result.errors.length, 0);
    assert.match(result.code, /<nav\s*\n/);
    assertPublicNavigation(header);
    assertPublicNavigation(result.code);
});

for (const [name, before, after] of [
    ['desktop breakpoint', 'lg:flex', 'md:flex'],
    ['mobile breakpoint', 'lg:hidden', 'md:hidden'],
    ['desktop label', 'Primary navigation', 'Unlabelled navigation'],
    ['mobile navigation landmark', 'role="navigation"', 'role="group"'],
    [
        'menu controls',
        'aria-controls="public-mobile-nav"',
        'data-controls="public-mobile-nav"',
    ],
]) {
    void test('navigation guards reject a missing ' + name, () => {
        assert.ok(
            header.includes(before),
            'mutation must alter the actual header',
        );
        assert.throws(() =>
            assertPublicNavigation(header.replace(before, after)),
        );
    });
}
