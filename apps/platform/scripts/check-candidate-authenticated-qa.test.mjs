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
    auditImagesInPage,
    hashServedManifest,
    installCandidateNetworkGuard,
    isCandidateRequestUrl,
    MAX_MANIFEST_BYTES,
    sha256,
    judge,
    loadOwnerStorageState,
    runPage,
    validateEnv,
} from './candidate-authenticated-qa.mjs';

const dir = mkdtempSync(path.join(tmpdir(), 'qa-'));
const state = path.join(dir, 'state.json');
writeFileSync(state, JSON.stringify({ cookies: [], origins: [] }));
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

void test('owner session is pinned to a validated file descriptor, not a later path lookup', () => {
    const privatePath = path.join(dir, 'owner-state-to-swap.json');
    const replacement = path.join(dir, 'untrusted-owner-state.json');
    writeFileSync(privatePath, JSON.stringify({ cookies: [], origins: [] }), { mode: 0o600 });
    writeFileSync(replacement, JSON.stringify({ cookies: [{ name: 'bad' }], origins: [] }));
    const checked = validateEnv({ ...good, KMJ_QA_STORAGE_STATE: privatePath });
    assert.deepEqual(checked.problems, []);
    unlinkSync(privatePath);
    symlinkSync(replacement, privatePath);
    try {
        assert.deepEqual(checked.storageState, { cookies: [], origins: [] });
        assert.ok(
            validateEnv({ ...good, KMJ_QA_STORAGE_STATE: privatePath })
                .problems.includes('STORAGE_STATE_NOT_PRIVATE_FILE'),
        );
    } finally {
        unlinkSync(privatePath);
        unlinkSync(replacement);
    }
});

void test('owner state rejects invalid JSON and invalid Playwright shape without printing secrets', () => {
    const badPath = path.join(dir, 'bad-owner-state.json');
    try {
        for (const value of ['not-json', '{}', '{"cookies":[], "origins":null}']) {
            writeFileSync(badPath, value, { mode: 0o600 });
            chmodSync(badPath, 0o600);
            assert.ok(
                validateEnv({ ...good, KMJ_QA_STORAGE_STATE: badPath })
                    .problems.includes('STORAGE_STATE_INVALID'),
            );
        }
    } finally {
        unlinkSync(badPath);
    }
});

void test('validated state object, not its path, is passed to the browser', async () => {
    const checked = validateEnv(good);
    assert.deepEqual(checked.problems, []);
    let observedState;
    const browser = {
        async newContext(options) {
            observedState = options.storageState;
            return {
                async newPage() { throw new Error('EXPECTED_STOP'); },
                async close() {},
            };
        },
    };
    await assert.rejects(
        runPage(browser, checked.storageState, checked.base, VIEWPORTS[0], PAGES[0]),
        /EXPECTED_STOP/,
    );
    assert.deepEqual(observedState, { cookies: [], origins: [] });
    assert.notEqual(observedState, state);
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
            '/services/kmj-codebridge/workspace',
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

void test('candidate QA checks real CodeBridge workspace panels without sending requests', () => {
    const source = readFileSync(
        new URL('./candidate-authenticated-qa.mjs', import.meta.url),
        'utf8',
    );
    assert.match(source, /page\.id === 'codebridge-ai-workspace'/);
    for (const id of ['ai-workspace', 'pane-left', 'pane-center', 'pane-right'])
        assert.ok(source.includes("'" + id + "'"), id);
    assert.match(source, /WORKSPACE_MOBILE_DRAWER_TRIGGER_MISSING/);
});

void test('candidate owner browser contexts close after page creation and navigation errors', async () => {
    for (const failure of ['newPage', 'goto']) {
        let closed = 0;
        const context = {
            async newPage() {
                if (failure === 'newPage') throw new Error('SIMULATED_NEW_PAGE');
                return {
                    on() {},
                    async goto() {
                        throw new Error('SIMULATED_GOTO');
                    },
                };
            },
            async close() {
                closed++;
            },
        };
        const browser = { async newContext() { return context; } };
        await assert.rejects(
            runPage(browser, state, new URL(good.KMJ_QA_BASE_URL), VIEWPORTS[0], PAGES[0]),
            /SIMULATED_(NEW_PAGE|GOTO)/,
        );
        assert.equal(closed, 1, `context must close exactly once after ${failure}`);
    }
});


void test('late SPA navigation must fail closed even after an initial HTTP 200', async () => {
    for (const destination of [
        'http://127.0.0.1:8123/login',
        'http://127.0.0.1:8123/other-page',
        'http://127.0.0.1:9999/services/kmj-codebridge',
    ]) {
        let currentUrl = good.KMJ_QA_BASE_URL + PAGES[1].path;
        let closed = 0;
        let evaluateCount = 0;
        const tab = {
            on() {},
            url() { return currentUrl; },
            async goto() { return { status: () => 200 }; },
            mouse: {
                async wheel() { currentUrl = destination; },
            },
            async waitForTimeout() {},
            async evaluate() { return evaluateCount++ === 0 ? false : 0; },
        };
        const browser = {
            async newContext() {
                return {
                    async newPage() { return tab; },
                    async close() { closed++; },
                };
            },
        };
        const result = await runPage(
            browser, state, new URL(good.KMJ_QA_BASE_URL),
            VIEWPORTS[0], PAGES[1],
        );
        assert.equal(result.pass, false, destination);
        assert.equal(closed, 1, 'owner browser context must close');
        assert.ok(
            result.problems.some((problem) =>
                ['NOT_AUTHENTICATED', 'CANDIDATE_ORIGIN_MISMATCH', 'CANDIDATE_PATH_MISMATCH'].includes(problem)
            ),
            destination,
        );
    }
});

void test('image audit fails on corrupt and stalled decodes, without an unbounded wait', async () => {
    const previous = globalThis.document;
    globalThis.document = {
        images: [
            { naturalWidth: 8, naturalHeight: 8, decode: () => Promise.resolve() },
            // A corrupt file can expose dimensions while decode still rejects.
            { naturalWidth: 8, naturalHeight: 8, decode: () => Promise.reject(new Error('CORRUPT')) },
            { naturalWidth: 0, naturalHeight: 0, decode: () => new Promise(() => {}) },
        ],
    };
    try {
        assert.equal(await auditImagesInPage(10), 2);
        globalThis.document.images = [];
        assert.equal(await auditImagesInPage(10), 0);
    } finally {
        if (previous === undefined) delete globalThis.document;
        else globalThis.document = previous;
    }
});


void test('candidate manifest fetch is SHA-bound, bounded and fail-closed', async () => {
    const base = new URL(good.KMJ_QA_BASE_URL);
    const expectedUrl = new URL('/build/manifest.json', base).href;
    const body = '{"assets":true}';
    let fetchOptions;
    const response = (value, { url = expectedUrl, status = 200, headers = {} } = {}) => {
        const result = new Response(value, { status, headers });
        Object.defineProperty(result, 'url', { value: url });
        return result;
    };
    const valid = await hashServedManifest(base, async (url, options) => {
        assert.equal(url.href, expectedUrl);
        fetchOptions = options;
        return response(body, { headers: { 'content-length': String(Buffer.byteLength(body)) } });
    });
    assert.equal(valid, sha256(Buffer.from(body)));
    assert.equal(fetchOptions.redirect, 'manual');
    assert.ok(fetchOptions.signal instanceof AbortSignal);
    assert.equal(
        await hashServedManifest(base, async () => response(body, { url: 'http://127.0.0.1:9999/build/manifest.json' })),
        null,
    );
    assert.equal(
        await hashServedManifest(base, async () => response(body, { status: 404 })),
        null,
    );
    for (const length of ['not-a-number', '-1', String(MAX_MANIFEST_BYTES + 1)]) {
        assert.equal(
            await hashServedManifest(base, async () => response(body, { headers: { 'content-length': length } })),
            null,
            length,
        );
    }
    assert.equal(await hashServedManifest(base, async () => { throw new Error('PRIVATE'); }), null);
    assert.equal(await hashServedManifest(base, async () => response('')), null);
});

void test('chunked manifest exceeding byte cap cannot pass even without Content-Length', async () => {
    const base = new URL(good.KMJ_QA_BASE_URL);
    const url = new URL('/build/manifest.json', base).href;
    let cancelled = false;
    const reader = {
        async read() { return { done: false, value: new Uint8Array(MAX_MANIFEST_BYTES + 1) }; },
        async cancel() { cancelled = true; },
    };
    const result = await hashServedManifest(base, async () => ({
        ok: true, url, headers: { get: () => null },
        body: { getReader: () => reader },
    }));
    assert.equal(result, null);
    assert.equal(cancelled, true);
});

void test('owner QA network guard blocks external HTTP and every WebSocket', async () => {
    const base = new URL(good.KMJ_QA_BASE_URL);
    for (const allowed of [
        'http://127.0.0.1:8123/services/kmj-codebridge',
        'http://127.0.0.1:8123/build/manifest.json',
    ])
        assert.equal(isCandidateRequestUrl(allowed, base), true, allowed);
    for (const blocked of [
        'https://kmjtechno.com/',
        'http://127.0.0.1:8124/',
        'http://localhost:8123/',
        'http://example.com/',
        'file:///etc/passwd',
        'ws://127.0.0.1:8123/',
        'invalid',
    ])
        assert.equal(isCandidateRequestUrl(blocked, base), false, blocked);

    let httpHandler;
    let socketHandler;
    const context = {
        async route(pattern, handler) {
            assert.equal(pattern, '**/*');
            httpHandler = handler;
        },
        async routeWebSocket(pattern, handler) {
            assert.equal(pattern, '**/*');
            socketHandler = handler;
        },
    };
    await installCandidateNetworkGuard(context, base);
    for (const [url, expected] of [
        ['http://127.0.0.1:8123/products', 'continue'],
        ['https://external.example/private', 'abort'],
        ['http://127.0.0.1:8124/private', 'abort'],
    ]) {
        let actual;
        await httpHandler({
            request: () => ({ url: () => url }),
            async continue() { actual = 'continue'; },
            async abort(reason) {
                assert.equal(reason, 'blockedbyclient');
                actual = 'abort';
            },
        });
        assert.equal(actual, expected, url);
    }
    let socketClosed = 0;
    await socketHandler({ close() { socketClosed++; } });
    assert.equal(socketClosed, 1);
    await assert.rejects(
        installCandidateNetworkGuard({ route() {} }, base),
        /CANDIDATE_NETWORK_ISOLATION_UNAVAILABLE/,
    );
    await assert.rejects(
        installCandidateNetworkGuard({ routeWebSocket() {} }, base),
        /CANDIDATE_NETWORK_ISOLATION_UNAVAILABLE/,
    );
});
