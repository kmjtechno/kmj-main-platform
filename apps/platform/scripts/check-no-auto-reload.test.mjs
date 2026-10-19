import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const app = readFileSync(
    new URL('../resources/js/app.tsx', import.meta.url),
    'utf8',
);

const ops = readFileSync(
    new URL('../resources/js/pages/operator-ops.tsx', import.meta.url),
    'utf8',
);

void test('owner Ops telemetry never polls hidden tabs and resumes on visibility', () => {
    assert.match(ops, /document\.visibilityState !== 'visible'/);
    assert.match(ops, /document\.visibilityState === 'visible'/);
    assert.match(ops, /document\.addEventListener\('visibilitychange'/);
    assert.match(ops, /document\.removeEventListener\('visibilitychange'/);
    assert.match(ops, /window\.clearInterval\(timer\)/);
    assert.match(ops, /window\.setInterval\(refreshVisible, 15_000\)/);
    assert.doesNotMatch(ops, /location\.reload\s*\(/);
});

void test('the app shell never reloads or polls the page by itself', () => {
    // A background watcher that reloaded the page on every deployment discarded
    // unsaved input (for example an API key being typed). Users refresh when they choose to.
    assert.ok(!/location\.reload\s*\(/.test(app));
    assert.ok(!/setInterval\s*\(/.test(app));
    assert.ok(!/buildFingerprint|BuildUpdateWatcher/.test(app));
});
