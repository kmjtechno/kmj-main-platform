import test from 'node:test';
import assert from 'node:assert/strict';
import { chmodSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import {
    PAGES,
    VIEWPORTS,
    judge,
    validateEnv,
} from './candidate-authenticated-qa.mjs';

const dir = mkdtempSync(path.join(tmpdir(), 'qa-'));
const state = path.join(dir, 'state.json');
writeFileSync(state, '{}');
chmodSync(state, 0o600);
const good = {
    KMJ_QA_BASE_URL: 'http://127.0.0.1:8123',
    KMJ_QA_CANDIDATE_SHA: 'a'.repeat(40),
    KMJ_QA_MANIFEST_SHA256: 'b'.repeat(64),
    KMJ_QA_STORAGE_STATE: state,
};

void test('valid environment is accepted', () => {
    assert.deepEqual(validateEnv(good).problems, []);
});

void test('anything but loopback http with a port is refused (never production)', () => {
    for (const url of [
        'https://kmjtechno.com',
        'http://kmjtechno.com:8080',
        'http://127.0.0.1',
        'ftp://127.0.0.1:1',
        'nope',
        '',
    ])
        assert.ok(
            validateEnv({ ...good, KMJ_QA_BASE_URL: url }).problems.length > 0,
            url,
        );
});

void test('candidate sha, manifest hash and private storage state are required', () => {
    assert.ok(
        validateEnv({ ...good, KMJ_QA_CANDIDATE_SHA: 'abc' }).problems.includes(
            'CANDIDATE_SHA_INVALID',
        ),
    );
    assert.ok(
        validateEnv({ ...good, KMJ_QA_MANIFEST_SHA256: 'z' }).problems.includes(
            'MANIFEST_SHA256_INVALID',
        ),
    );
    assert.ok(
        validateEnv({
            ...good,
            KMJ_QA_STORAGE_STATE: path.join(dir, 'missing'),
        }).problems.includes('STORAGE_STATE_MISSING'),
    );
    chmodSync(state, 0o644);
    assert.ok(
        validateEnv(good).problems.includes('STORAGE_STATE_NOT_PRIVATE_FILE'),
    );
    chmodSync(state, 0o600);
});

void test('judge fails closed on every defect and never passes an unauthenticated page', () => {
    const ok = {
        page: 'p',
        viewport: 'v',
        http: 200,
        consoleErrors: 0,
        pageErrors: 0,
        overflow: false,
        brokenImages: 0,
        redirectedToLogin: false,
        problems: [],
    };
    assert.equal(judge(ok).pass, true);
    for (const patch of [
        { http: 500 },
        { consoleErrors: 1 },
        { pageErrors: 1 },
        { overflow: true },
        { brokenImages: 2 },
        { redirectedToLogin: true },
        { problems: ['X'] },
    ])
        assert.equal(
            judge({ ...ok, ...patch }).pass,
            false,
            JSON.stringify(patch),
        );
});

void test('scope covers owner fleet, canonical center, deep link, product manager at desktop and 390px', () => {
    assert.deepEqual(
        VIEWPORTS.map((v) => v.width),
        [1440, 390],
    );
    assert.deepEqual(
        PAGES.map((p) => p.path),
        [
            '/operator/codebridge/owner-plan',
            '/services/kmj-codebridge',
            '/services/kmj-codebridge#codebridge-device-control',
            '/operator/products',
        ],
    );
});
