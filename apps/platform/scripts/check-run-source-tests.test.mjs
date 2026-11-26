import test from 'node:test';
import assert from 'node:assert/strict';
import { skipPattern } from './run-source-tests.mjs';

void test('skip pattern matches only the exact listed names', () => {
    const re = new RegExp(skipPattern(['a (b).c', 'second']));
    assert.ok(re.test('a (b).c'));
    assert.ok(!re.test('a (b)xc'));
    assert.ok(!re.test('second one'));
    assert.equal(skipPattern([]), null);
});
