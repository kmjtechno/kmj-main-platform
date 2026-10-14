import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const root = new URL('../', import.meta.url);
const read = (name) => readFileSync(new URL(name, root), 'utf8');
const shell = read('resources/js/pages/mail/index.tsx');
const routes = read('routes/web.php');

void test('mail workspace defaults to no transport or messages', () => {
    assert.match(shell, /transportStatus = 'not_configured'/);
    assert.match(shell, /messages = \[\]/);
    assert.match(shell, /const scoped = ready \? messages : \[\]/);
    assert.match(shell, /No demo messages are shown as real mail/);
});

void test('no client-side send or unsafe HTML rendering', () => {
    assert.doesNotMatch(shell, /dangerouslySetInnerHTML|innerHTML\s*=/);
    assert.doesNotMatch(shell, /\bfetch\s*\(|router\.post\s*\(|axios\./);
    assert.match(shell, /\{selected\.body_text\}/);
    assert.match(shell, /disabled aria-disabled="true"/);
    assert.match(shell, /Send unavailable/);
});

void test('responsive accessible navigation and keyboard search', () => {
    assert.match(shell, /aria-label="Mail folders"/);
    assert.match(shell, /aria-label="Search mail"/);
    assert.match(shell, /<Dialog open=\{compose\}/);
    assert.match(shell, /aria-current=/);
    assert.match(shell, /event\.key === '\/'/);
    assert.match(shell, /event\.key === 'Escape'/);
    assert.match(shell, /lg:grid-cols/);
});

void test('preview route only exists in development and enforces verified login', () => {
    assert.match(routes, /app\(\)->environment\('local', 'testing'\)/);
    assert.match(routes, /Route::middleware\(\['auth', 'verified'\]\)/);
    assert.match(routes, /abort_unless\(app\(\)->environment\('local', 'testing'\), 404\)/);
    assert.match(routes, /'transportStatus' => 'not_configured'/);
    assert.match(routes, /'messages' => \[\]/);
    assert.doesNotMatch(routes, /Route::post\('internal\/kmj-mail-preview'/);
});
