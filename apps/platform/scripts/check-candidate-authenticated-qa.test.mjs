import test from 'node:test';
import assert from 'node:assert/strict';
import {
    chmodSync,
    linkSync,
    mkdtempSync,
    readFileSync,
    symlinkSync,
    unlinkSync,
    writeFileSync,
} from 'node:fs';
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
        'http://user:password@127.0.0.1:8123',
        'http://127.0.0.1:8123/unexpected',
        'http://127.0.0.1:8123/?mode=owner',
        'http://127.0.0.1:8123/#untrusted',
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

void test('owner browser state must be a private single-link regular file, never a symlink', () => {
    const alias = path.join(dir, 'state-symlink.json');
    const hardlink = path.join(dir, 'state-hardlink.json');
    symlinkSync(state, alias);
    try {
        assert.ok(
            validateEnv({ ...good, KMJ_QA_STORAGE_STATE: alias }).problems.includes(
                'STORAGE_STATE_NOT_PRIVATE_FILE',
            ),
        );
    } finally {
        unlinkSync(alias);
    }
    linkSync(state, hardlink);
    try {
        assert.ok(
            validateEnv(good).problems.includes('STORAGE_STATE_NOT_PRIVATE_FILE'),
        );
        assert.ok(
            validateEnv({ ...good, KMJ_QA_STORAGE_STATE: hardlink }).problems.includes(
                'STORAGE_STATE_NOT_PRIVATE_FILE',
            ),
        );
    } finally {
        unlinkSync(hardlink);
    }
    assert.deepEqual(validateEnv(good).problems, []);
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
        finalOriginMatches: true,
        finalPathMatches: true,
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
        { finalOriginMatches: false },
        { finalOriginMatches: undefined },
        { finalPathMatches: false },
        { finalPathMatches: undefined },
        { problems: ['X'] },
    ])
        assert.equal(
            judge({ ...ok, ...patch }).pass,
            false,
            JSON.stringify(patch),
        );
});

void test('origin binding is mandatory even when the page reports HTTP 200', () => {
    const result = {
        http: 200,
        consoleErrors: 0,
        pageErrors: 0,
        overflow: false,
        brokenImages: 0,
        redirectedToLogin: false,
        problems: [],
    };
    assert.ok(
        judge({ ...result, finalOriginMatches: false }).problems.includes(
            'CANDIDATE_ORIGIN_MISMATCH',
        ),
    );
    assert.ok(
        judge({
            ...result,
            finalOriginMatches: true,
            finalPathMatches: false,
        }).problems.includes('CANDIDATE_PATH_MISMATCH'),
    );
    assert.ok(
        judge({ ...result, finalOriginMatches: true, finalPathMatches: true })
            .pass,
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

void test('candidate owner QA expects the split owner-only license heading', () => {
    const source = readFileSync(
        new URL('./candidate-authenticated-qa.mjs', import.meta.url),
        'utf8',
    );
    assert.match(source, /name: 'CodeBridge Owner License Settings'/);
    assert.doesNotMatch(source, /name: 'CodeBridge Control Center'/);
});
