import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { passwordRequirements } from '../resources/js/lib/password-rules-hint.ts';

const production =
    'minlength: 12; required: lower; required: upper; required: digit; required: [-];';

void test('requirements come from the server rules string', () => {
    const items = passwordRequirements(production);
    assert.deepEqual(
        items.map((item) => item.id),
        ['length', 'lower', 'upper', 'digit', 'symbol'],
    );
    assert.equal(items[0].label, 'At least 12 characters');
    assert.equal(passwordRequirements('').length, 0);
});

void test('requirement checks follow what is typed', () => {
    const items = passwordRequirements(production);
    const ok = (password) => items.every((item) => item.test(password));
    assert.equal(ok('Short1!a'), false);
    assert.equal(ok('alllowercase123!'), false);
    assert.equal(ok('NoSymbolsHere1234'), false);
    assert.equal(ok('Correct-Horse-Battery-9'), true);
});

void test('register page shows live requirements and what happens next', () => {
    const page = readFileSync(
        new URL('../resources/js/pages/auth/register.tsx', import.meta.url),
        'utf8',
    );
    assert.match(page, /passwordRequirements\(passwordRules\)/);
    assert.match(page, /id="password-requirements"/);
    assert.match(page, /What happens next/);
    assert.match(page, /country code/);
});
