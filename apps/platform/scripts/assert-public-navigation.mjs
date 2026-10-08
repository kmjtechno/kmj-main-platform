import assert from 'node:assert/strict';

export function assertPublicNavigation(header) {
    assert.match(
        header,
        /aria-label=\{open \? 'Close navigation' : 'Open navigation'\}/,
    );
    assert.match(header, /aria-controls="public-mobile-nav"/);
    assert.match(header, /id="public-mobile-nav"/);
    assert.match(
        header,
        /role="navigation"\s+aria-label="Mobile primary navigation"/,
    );
    assert.match(header, /aria-label="Primary navigation"/);
    assert.equal(
        (header.match(/lg:hidden/g) ?? []).length,
        2,
        'tablet header must render both the menu toggle and expanded navigation',
    );
    assert.match(
        header,
        /<nav\s+className="hidden items-center gap-1 lg:flex"\s+aria-label="Primary navigation"\s*>/,
        'desktop navigation must appear at lg while the mobile menu hides at lg',
    );
    assert.doesNotMatch(
        header,
        /sm:hidden|md:hidden/,
        'a smaller breakpoint must not remove mobile navigation before desktop navigation appears',
    );
}
