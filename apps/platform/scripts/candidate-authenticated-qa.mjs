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
import { statSync } from 'node:fs';

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
            !base.port)
    )
        problems.push('BASE_URL_MUST_BE_LOOPBACK_WITH_PORT');
    if (!/^[a-f0-9]{40}$/.test(env.KMJ_QA_CANDIDATE_SHA ?? ''))
        problems.push('CANDIDATE_SHA_INVALID');
    if (!/^[a-f0-9]{64}$/.test(env.KMJ_QA_MANIFEST_SHA256 ?? ''))
        problems.push('MANIFEST_SHA256_INVALID');
    const state = env.KMJ_QA_STORAGE_STATE ?? '';
    try {
        const info = statSync(state);
        if (!info.isFile() || (info.mode & 0o077) !== 0)
            problems.push('STORAGE_STATE_NOT_PRIVATE_FILE');
    } catch {
        problems.push('STORAGE_STATE_MISSING');
    }
    return { problems, base };
}

export function sha256(buffer) {
    return createHash('sha256').update(buffer).digest('hex');
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
    return { ...result, problems, pass: problems.length === 0 };
}

export async function runPage(browser, state, base, viewport, page) {
    const context = await browser.newContext({
        storageState: state,
        viewport: { width: viewport.width, height: viewport.height },
    });
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
    const url = new URL(tab.url());
    const redirectedToLogin = /^\/(login|register|two-factor)/.test(
        url.pathname,
    );
    await tab.mouse.wheel(0, 4000);
    await tab.waitForTimeout(300);
    const overflow = await tab.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth + 1,
    );
    const brokenImages = await tab.evaluate(async () => {
        const images = [...document.images];
        await Promise.all(
            images.map((img) => img.decode().catch(() => undefined)),
        );
        return images.filter((img) => !img.naturalWidth || !img.naturalHeight)
            .length;
    });

    if (!redirectedToLogin && page.id === 'owner-codebridge-fleet') {
        const heading = await tab
            .getByRole('heading', {
                name: 'CodeBridge Control Center',
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
    if (!redirectedToLogin && page.id === 'codebridge-devices-deeplink') {
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
    await context.close();
    return judge({
        page: page.id,
        viewport: viewport.name,
        http: response?.status() ?? 0,
        consoleErrors,
        pageErrors,
        overflow,
        brokenImages,
        redirectedToLogin,
        problems,
    });
}

async function main() {
    const { problems, base } = validateEnv(process.env);
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
    const state = process.env.KMJ_QA_STORAGE_STATE;
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
        const served = await fetch(new URL('/build/manifest.json', base));
        const servedHash = served.ok
            ? sha256(Buffer.from(await served.arrayBuffer()))
            : null;
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
            process.exit(2);
        }
        for (const viewport of VIEWPORTS)
            for (const page of PAGES)
                receipt.results.push(
                    await runPage(browser, state, base, viewport, page),
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
