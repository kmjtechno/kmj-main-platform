import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

for (const page of ['login', 'register']) {
    void test(`auth ${page} follows natural keyboard order`, () => {
        const source = readFileSync(
            `resources/js/pages/auth/${page}.tsx`,
            'utf8',
        );
        assert.doesNotMatch(
            source,
            /tabIndex=\{[1-9]\d*\}/,
            'positive tabindex overrides natural visual and screen-reader order',
        );
        assert.match(source, /autoFocus/);
    });
}
