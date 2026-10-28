import assert from 'node:assert/strict';

export function assertPublicNavigation(header) {
    assert.match(
        header,
        /aria-label=\{open \? ["']Close navigation["'] : ["']Open navigation["']\}/,
    );
    assert.match(header, /aria-controls="public-mobile-nav"/);
    assert.match(header, /aria-expanded=\{open\}/);
    assert.match(header, /type="button"/);
    assert.match(header, /ref=\{menuButton\}/);
    assert.match(header, /onKeyDown=\{\(event\) => \{/);
    assert.match(header, /event\.key === 'Escape'/);
    assert.match(header, /menuButton\.current\?\.focus\(\)/);
    assert.match(header, /aria-current=\{/);
    assert.match(header, /id="public-mobile-nav"/);
    assert.match(header, /aria-label="Primary navigation"/);
    assert.match(header, /className=\{open \? ['"]is-open['"] : ['"]['"]\}/);
    assert.match(header, /lock-header kmj-public-header/);
    assert.match(
        header,
        /PublicLanguageSwitch className="lock-mobile-language"/,
    );
}
