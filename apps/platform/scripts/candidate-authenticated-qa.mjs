// Authenticated, READ-ONLY QA of an isolated release candidate runtime.
//
// Evidence this produces (JSON receipt on stdout): per-page, per-viewport
// results for the signed-in Platform Owner on the candidate. It is NOT the
// synthetic Vite harness, and it never creates/edits/deletes data: Product
// Manager mutation flows are reported NOT_ATTEMPTED because a candidate that
// shares the live database must not be mutated. Run it only against a
// candidate booted on a disposable restored database, bound to loopback.
//
// Required environment (all validated, none printed):
//   KMJ_QA_BASE_URL              http://127.0.0.1:<port> | http://localhost:<port>
//   KMJ_QA_CANDIDATE_SHA         40-hex release candidate commit
//   KMJ_QA_MANIFEST_SHA256       sha256 of the candidate's public/build/manifest.json
//                                (binds the served runtime to that commit's build)
//   KMJ_QA_STORAGE_STATE         Playwright storage-state file produced by the owner
//                                signing in themselves (mode 0600). This script never
//                                receives, stores or types a password or token.
// Optional: KMJ_CHROMIUM_EXECUTABLE, KMJ_PLAYWRIGHT_MODULE.
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { closeSync, constants, fstatSync, openSync, readFileSync } from 'node:fs';

export const VIEWPORTS = [
    { name: 'desktop', width: 1440, height: 900 },
    { name: 'mobile', width: 390, height: 844 },
];

export const PAGES = [
    { id: 'owner-codebridge-fleet', path: '/operator/codebridge/owner-plan' },
    { id: 'codebridge-control-center', path: '/services/kmj-codebridge' },
    {
        id: 'codebridge-devices-deeplink',
        path: '/services/kmj-codebridge#codebridge-device-control',
    },
    { id: 'codebridge-ai-workspace', path: '/services/kmj-codebridge/workspace' },
    { id: 'owner-product-manager', path: '/operator/products' },
];

export function validateEnv(env) {
    const problems = [];
    let base = null;
    try {
        base = new URL(env.KMJ_QA_BASE_URL ?? '');
    } catch {
        problems.push('BASE_URL_INVALID');
    }
    if (
        base &&
        (base.protocol !== 'http:' ||
            !['127.0.0.1', 'localhost', '[::1]'].includes(base.hostname) ||
            !base.port ||
            base.username ||
            base.password ||
            base.pathname !== '/' ||
            base.search ||
            base.hash)
    )
        problems.push('BASE_URL_MUST_BE_LOOPBACK_WITH_PORT');
    if (!/^[a-f0-9]{40}$/.test(env.KMJ_QA_CANDIDATE_SHA ?? ''))
        problems.push('CANDIDATE_SHA_INVALID');
    if (!/^[a-f0-9]{64}$/.test(env.KMJ_QA_MANIFEST_SHA256 ?? ''))
        problems.push('MANIFEST_SHA256_INVALID');
    // Read once through a no-follow file descriptor. Checking lstat(path)
    // then handing the path to Playwright lets a swapped symlink import a
    // different session after validation (TOCTOU).
    const loaded = loadOwnerStorageState(env.KMJ_QA_STORAGE_STATE ?? '');
    if (loaded.problem) problems.push(loaded.problem);
    return { problems, base, storageState: loaded.storageState };
}

export function loadOwnerStorageState(path) {
    // This owner-session runner is intentionally Linux/POSIX-only unless a
    // future implementation can prove equivalent no-follow + owner checks.
    if (
        typeof constants.O_NOFOLLOW !== 'number' ||
        typeof process.getuid !== 'function'
    )
        return { problem: 'STORAGE_STATE_SECURE_OPEN_UNAVAILABLE' };
    let fd;
    try {
        fd = openSync(
            path,
            constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK,
        );
        const info = fstatSync(fd);
        if (
            !info.isFile() ||
            info.nlink !== 1 ||
            info.uid !== process.getuid() ||
            (info.mode & 0o077) !== 0 ||
            info.size === 0 ||
            info.size > 2 * 1024 * 1024
        )
            return { problem: 'STORAGE_STATE_NOT_PRIVATE_FILE' };
        const storageState = JSON.parse(readFileSync(fd, 'utf8'));
        if (
            !storageState ||
            typeof storageState !== 'object' ||
            !Array.isArray(storageState.cookies) ||
            !Array.isArray(storageState.origins)
        )
            return { problem: 'STORAGE_STATE_INVALID' };
        return { storageState };
    } catch (error) {
        return {
            problem: error.code === 'ENOENT'
                ? 'STORAGE_STATE_MISSING'
                : error.code === 'ELOOP'
                    ? 'STORAGE_STATE_NOT_PRIVATE_FILE'
                    : 'STORAGE_STATE_INVALID',
        };
    } finally {
        if (fd !== undefined) closeSync(fd);
    }
}

export function sha256(buffer) {
    return createHash('sha256').update(buffer).digest('hex');
}

export const MAX_MANIFEST_BYTES = 8 * 1024 * 1024;

// A stalled or unbounded loopback response must never hang owner QA or exhaust
// memory before the runtime-to-candidate digest can be checked.
export async function hashServedManifest(base, fetchImpl = fetch) {
    const manifestUrl = new URL('/build/manifest.json', base);
    try {
        const response = await fetchImpl(manifestUrl, {
            redirect: 'manual',
            signal: AbortSignal.timeout(15000),
        });
        if (!response.ok || response.url !== manifestUrl.href) return null;
        const length = response.headers?.get('content-length');
        if (length !== null && length !== undefined) {
            if (!/^\d+$/.test(length) || Number(length) > MAX_MANIFEST_BYTES)
                return null;
        }
        const reader = response.body?.getReader();
        if (!reader) return null;
        const hash = createHash('sha256');
        let bytes = 0;
        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                bytes += value.byteLength;
                if (bytes > MAX_MANIFEST_BYTES) return null;
                hash.update(value);
            }
            return bytes > 0 ? hash.digest('hex') : null;
        } finally {
            await reader.cancel().catch(() => {});
        }
    } catch {
        return null; // No exception text, URL, cookie or response body in receipts.
    }
}

// Verdict for one page result; any recorded problem fails closed.
export function judge(result) {
    const problems = [...result.problems];
    if (result.http !== 200) problems.push(`HTTP_${result.http}`);
    if (result.consoleErrors > 0) problems.push('CONSOLE_ERRORS');
    if (result.pageErrors > 0) problems.push('PAGE_ERRORS');
    if (result.overflow) problems.push('HORIZONTAL_OVERFLOW');
    if (result.brokenImages > 0) problems.push('BROKEN_IMAGES');
    if (result.redirectedToLogin) problems.push('NOT_AUTHENTICATED');
    // A 200 from a redirect target is not proof of the candidate origin.
    if (result.finalOriginMatches !== true)
        problems.push('CANDIDATE_ORIGIN_MISMATCH');
    if (result.finalPathMatches !== true)
        problems.push('CANDIDATE_PATH_MISMATCH');
    return { ...result, problems, pass: problems.length === 0 };
}

// This function is serialized into the Playwright page; keep it self-contained.
export async function auditImagesInPage(timeoutMs = 5000) {
    const images = [...document.images];
    const results = await Promise.all(images.map(async (img) => {
        let timer;
        try {
            const decoded = await Promise.race([
                Promise.resolve().then(() => img.decode()).then(() => true, () => false),
                new Promise((resolve) => {
                    timer = setTimeout(() => resolve(false), timeoutMs);
                }),
            ]);
            return decoded && img.naturalWidth > 0 && img.naturalHeight > 0;
        } finally {
            clearTimeout(timer);
        }
    }));
    return results.filter((ok) => !ok).length;
}

export async function runPage(browser, state, base, viewport, page) {
    const context = await browser.newContext({
        storageState: state,
        viewport: { width: viewport.width, height: viewport.height },
    });
    try {
        return await runPageInContext(context, base, viewport, page);
    } finally {
        // Never retain an owner-authenticated candidate context after an error.
        await context.close();
    }
}

async function runPageInContext(context, base, viewport, page) {
    const tab = await context.newPage();
    let consoleErrors = 0;
    let pageErrors = 0;
    tab.on(
        'console',
        (message) => message.type() === 'error' && consoleErrors++,
    );
    tab.on('pageerror', () => pageErrors++);
    const problems = [];
    const response = await tab.goto(new URL(page.path, base).toString(), {
        waitUntil: 'networkidle',
        timeout: 60000,
    });
    const initialUrl = new URL(tab.url());
    const initiallyRedirectedToLogin = /^\/(login|register|two-factor)/.test(
        initialUrl.pathname,
    );
    await tab.mouse.wheel(0, 4000);
    await tab.waitForTimeout(300);
    const overflow = await tab.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth + 1,
    );
    // Bound image decode time: lazy/offscreen or stalled image requests must not
    // hang owner QA indefinitely, and decode errors are broken even when an
    // image has nonzero intrinsic dimensions.
    const brokenImages = await tab.evaluate(auditImagesInPage);

    if (!initiallyRedirectedToLogin && page.id === 'owner-codebridge-fleet') {
        const heading = await tab
            .getByRole('heading', {
                name: 'CodeBridge Owner License Settings',
                exact: true,
            })
            .count();
        if (heading !== 1) problems.push('FLEET_HEADING_MISSING');
        if (
            (await tab
                .getByRole('heading', {
                    name: 'Device Control Center',
                    exact: true,
                })
                .count()) !== 0
        )
            problems.push('INTERACTIVE_CONTROL_CENTER_NESTED_IN_OWNER_FLEET');
        for (const label of [
            'Disconnect',
            'Connect device',
            'Details & diagnose',
        ])
            if ((await tab.getByRole('button', { name: label }).count()) !== 0)
                problems.push(
                    `OWNER_FLEET_EXPOSES_${label.toUpperCase().replace(/\W+/g, '_')}`,
                );
        if (
            (await tab.locator('a[href^="/services/kmj-codebridge"]').count()) <
            1
        )
            problems.push('CANONICAL_LINK_MISSING');
    }
    // The merged owner/customer AI workspace must render its actual three-pane UI.
    // Read-only DOM checks: no chat send, tool request or mutation is attempted.
    if (!initiallyRedirectedToLogin && page.id === 'codebridge-ai-workspace') {
        for (const id of ['ai-workspace', 'pane-left', 'pane-center', 'pane-right'])
            if ((await tab.getByTestId(id).count()) !== 1)
                problems.push('WORKSPACE_' + id.toUpperCase().replace(/-/g, '_') + '_MISSING');
        if (viewport.width <= 390)
            for (const name of ['Open projects', 'Open tools and context'])
                if ((await tab.getByRole('button', { name, exact: true }).count()) !== 1)
                    problems.push('WORKSPACE_MOBILE_DRAWER_TRIGGER_MISSING');
    }
    if (!initiallyRedirectedToLogin && page.id === 'codebridge-devices-deeplink') {
        if (
            (await tab
                .getByRole('heading', {
                    name: 'Device Control Center',
                    exact: true,
                })
                .count()) !== 1
        )
            problems.push('DEVICE_CONTROL_CENTER_NOT_SHOWN_FOR_DEEPLINK');
        await tab.evaluate(() => {
            window.location.hash = '#overview';
        });
        await tab.waitForTimeout(300);
        if (
            (await tab
                .getByRole('heading', {
                    name: 'Device Control Center',
                    exact: true,
                })
                .count()) !== 0
        )
            problems.push('OVERVIEW_HASH_DID_NOT_LEAVE_DEVICES');
    }
    // SPA redirects can occur after goto() or during layout checks. A stale
    // URL captured immediately after navigation could falsely PASS an owner
    // page that subsequently moved to login or another origin.
    const finalUrl = new URL(tab.url());
    const redirectedToLogin =
        initiallyRedirectedToLogin ||
        /^\/(login|register|two-factor)/.test(finalUrl.pathname);
    return judge({
        page: page.id,
        viewport: viewport.name,
        http: response?.status() ?? 0,
        consoleErrors,
        pageErrors,
        overflow,
        brokenImages,
        redirectedToLogin,
        finalOriginMatches: finalUrl.origin === base.origin,
        finalPathMatches: finalUrl.pathname === new URL(page.path, base).pathname,
        problems,
    });
}

async function main() {
    const { problems, base, storageState } = validateEnv(process.env);
    const receipt = {
        kind: 'candidate-authenticated-qa',
        candidateSha: process.env.KMJ_QA_CANDIDATE_SHA ?? null,
        mutations: 'NONE',
        productManagerMutationFlows: 'NOT_ATTEMPTED',
        results: [],
        verdict: 'BLOCKED',
    };
    if (problems.length) {
        console.log(
            JSON.stringify({ ...receipt, blockers: problems }, null, 2),
        );
        process.exit(2);
    }
    const require = createRequire(import.meta.url);
    const { chromium } = require(
        process.env.KMJ_PLAYWRIGHT_MODULE || 'playwright',
    );
    const browser = await chromium.launch({
        headless: true,
        executablePath: process.env.KMJ_CHROMIUM_EXECUTABLE,
        chromiumSandbox: true,
    });
    try {
        // Bind the served runtime to the candidate build before trusting any page.
        const servedHash = await hashServedManifest(base);
        receipt.runtimeBoundToCandidateBuild =
            servedHash === process.env.KMJ_QA_MANIFEST_SHA256;
        if (!receipt.runtimeBoundToCandidateBuild) {
            console.log(
                JSON.stringify(
                    {
                        ...receipt,
                        blockers: ['SERVED_MANIFEST_DOES_NOT_MATCH_CANDIDATE'],
                    },
                    null,
                    2,
                ),
            );
            // A direct process.exit() would bypass finally and leak Chromium.
            process.exitCode = 2;
            return;
        }
        for (const viewport of VIEWPORTS)
            for (const page of PAGES)
                receipt.results.push(
                    await runPage(browser, storageState, base, viewport, page),
                );
    } finally {
        await browser.close();
    }
    receipt.verdict = receipt.results.every((r) => r.pass) ? 'PASS' : 'FAIL';
    console.log(JSON.stringify(receipt, null, 2));
    process.exit(receipt.verdict === 'PASS' ? 0 : 1);
}

if (
    process.argv[1] &&
    import.meta.url === new URL(`file://${process.argv[1]}`).href
)
    await main();
