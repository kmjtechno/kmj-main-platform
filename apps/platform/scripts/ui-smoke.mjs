// Real-browser smoke checks for the KMJ Main Platform UI.
//
// Environment:
//   UI_BASE      base URL of a running app            (default http://127.0.0.1:8000)
//   UI_MODE      "public" | "dashboard"               (default public)
//   CHROME_PATH  Chrome/Chromium executable           (default /usr/bin/google-chrome)
//   UI_EMAIL / UI_PASSWORD  verified account for dashboard mode
//
// Every check is an assertion that fails the run; nothing is reported as passing
// unless it was actually observed in the browser. Needs `playwright-core` and
// `axe-core` (installed with --no-save by CI, not part of the app's dependencies).

import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { chromium } from 'playwright-core';

const require = createRequire(import.meta.url);
const axeSource = readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');

const BASE = (process.env.UI_BASE ?? 'http://127.0.0.1:8000').replace(
    /\/$/,
    '',
);
const MODE = process.env.UI_MODE ?? 'public';
const CHROME = process.env.CHROME_PATH ?? '/usr/bin/google-chrome';

const VIEWPORTS = [
    { name: 'mobile-390', width: 390, height: 844 },
    { name: 'tablet-768', width: 768, height: 1024 },
    { name: 'desktop-1280', width: 1280, height: 800 },
    { name: 'desktop-1920', width: 1920, height: 1080 },
];

// UI_CHECKS selects check groups (comma separated, default "all"):
//   layout, images, network, a11y, keyboard (public + dashboard), manage (dashboard).
// CI runs each group as its own job so a failing group is identifiable from the
// commit status alone. Page loads and the HTTP 200 check always run.
const ENABLED = new Set(
    (process.env.UI_CHECKS ?? 'all').split(',').map((g) => g.trim()),
);
const on = (group) => ENABLED.has('all') || ENABLED.has(group);
const INSPECT = ['layout', 'images', 'network', 'a11y'].some(on);

const PUBLIC_PATHS = ['/', '/products', '/products/kmj-codebridge', '/login'];

const failures = [];
const warnings = [];
let checks = 0;

function check(ok, label, detail = '') {
    checks += 1;
    if (ok) {
        console.log(`  ok   ${label}`);
    } else {
        failures.push(`${label}${detail ? ` — ${detail}` : ''}`);
        console.log(`  FAIL ${label}${detail ? ` — ${detail}` : ''}`);
    }
}

function warn(label) {
    warnings.push(label);
    console.log(`  warn ${label}`);
}

async function inspectPage(page, path, viewport, { requireIcon = false } = {}) {
    const tag = `${path} @ ${viewport.name}`;
    const problems = { console: [], failed: [] };
    const onConsole = (message) => {
        if (message.type() === 'error') problems.console.push(message.text());
    };
    const onResponse = (response) => {
        if (response.url().startsWith(BASE) && response.status() >= 400) {
            problems.failed.push(`${response.status()} ${response.url()}`);
        }
    };
    page.on('console', onConsole);
    page.on('response', onResponse);

    const response = await page.goto(`${BASE}${path}`, {
        waitUntil: 'networkidle',
    });
    check(
        response !== null && response.status() === 200,
        `${tag}: HTTP 200`,
        `got ${response?.status()}`,
    );

    // Lazy images only load once scrolled into view.
    await page.evaluate(async () => {
        for (let y = 0; y < document.body.scrollHeight; y += 600) {
            window.scrollTo(0, y);
            await new Promise((resolve) => setTimeout(resolve, 40));
        }
        window.scrollTo(0, 0);
    });
    await page.waitForLoadState('networkidle');

    const metrics = await page.evaluate(() => ({
        title: document.title,
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
        landing: (() => {
            const element = document.querySelector('.locked-landing');
            if (!element) return null;
            const rect = element.getBoundingClientRect();
            return { width: rect.width, left: rect.left };
        })(),
        brokenImages: [...document.images]
            .filter((img) => !(img.complete && img.naturalWidth > 0))
            .map((img) => img.currentSrc || img.src),
        imagesWithoutAlt: [...document.images]
            .filter((img) => !img.hasAttribute('alt'))
            .map((img) => img.currentSrc || img.src),
        icons: [
            ...document.querySelectorAll(
                'link[rel~="icon"], link[rel="apple-touch-icon"]',
            ),
        ].map((link) => link.getAttribute('href')),
        officialIcon: [...document.images].some((img) =>
            /kmj-codebridge-icon/.test(img.currentSrc || img.src),
        ),
    }));

    if (on('layout')) {
        check(
            metrics.title.trim() !== '' && !/laravel/i.test(metrics.title),
            `${tag}: page title is branded`,
            metrics.title,
        );
        check(
            metrics.scrollWidth <= metrics.clientWidth + 1,
            `${tag}: no horizontal overflow`,
            `scrollWidth ${metrics.scrollWidth} > clientWidth ${metrics.clientWidth}`,
        );
        check(
            metrics.icons.length >= 2,
            `${tag}: favicon and touch icon declared`,
            metrics.icons.join(', '),
        );
    }
    if (on('layout') && path === '/') {
        check(
            metrics.landing !== null &&
                Math.abs(metrics.landing.width - metrics.clientWidth) <= 1 &&
                Math.abs(metrics.landing.left) <= 1,
            `${tag}: deployed landing fills viewport after production CSS chunks load`,
            JSON.stringify(metrics.landing),
        );
    }
    if (on('images')) {
        check(
            metrics.brokenImages.length === 0,
            `${tag}: every image loaded`,
            metrics.brokenImages.join(', '),
        );
        check(
            metrics.imagesWithoutAlt.length === 0,
            `${tag}: every image has an alt attribute`,
            metrics.imagesWithoutAlt.join(', '),
        );
        if (requireIcon)
            check(
                metrics.officialIcon,
                `${tag}: official CodeBridge product icon is shown`,
            );
    }
    if (on('network')) {
        check(
            problems.failed.length === 0,
            `${tag}: no same-origin request failed`,
            problems.failed.slice(0, 5).join(' | '),
        );
        check(
            problems.console.length === 0,
            `${tag}: no console errors`,
            problems.console.slice(0, 3).join(' | '),
        );
    }
    if (on('a11y')) {
        await page.evaluate(axeSource);
        const axe = await page.evaluate(async () => {
            const result = await window.axe.run(document, {
                resultTypes: ['violations'],
            });
            return result.violations.map((v) => ({
                id: v.id,
                impact: v.impact,
                nodes: v.nodes.length,
                targets: v.nodes.slice(0, 3).map((n) => n.target.join(' ')),
            }));
        });
        if (path === '/login') {
            check(
                !axe.some((v) => v.id === 'tabindex'),
                `${tag}: login does not override the natural tab order (axe)`,
            );
        }
        if (path === '/products/kmj-codebridge') {
            check(
                !axe.some((v) => v.id === 'color-contrast'),
                `${tag}: CodeBridge product contrast meets axe (no violations)`,
            );
        }
        const critical = axe.filter((v) => v.impact === 'critical');
        check(
            critical.length === 0,
            `${tag}: no critical accessibility violations (axe)`,
            critical.map((v) => `${v.id}×${v.nodes}`).join(', '),
        );
        for (const v of axe.filter((x) => x.impact === 'serious'))
            warn(
                `${tag}: serious a11y — ${v.id}×${v.nodes} at ${v.targets.join(', ')}`,
            );
    }

    page.off('console', onConsole);
    page.off('response', onResponse);
    return metrics;
}

async function keyboardReachable(page, path) {
    await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' });
    await page.keyboard.press('Tab');
    const first = await page.evaluate(() => {
        const el = document.activeElement;
        return el && el !== document.body ? el.tagName : null;
    });
    check(
        first !== null,
        `${path}: first Tab lands on a focusable element`,
        String(first),
    );
}

async function runPublic(browser) {
    for (const viewport of VIEWPORTS) {
        const context = await browser.newContext({ viewport });
        const page = await context.newPage();
        console.log(`\n== public @ ${viewport.name}`);
        if (INSPECT)
            for (const path of PUBLIC_PATHS)
                await inspectPage(page, path, viewport);
        await context.close();
    }
    if (on('keyboard')) {
        const context = await browser.newContext({ viewport: VIEWPORTS[2] });
        const page = await context.newPage();
        for (const path of PUBLIC_PATHS) await keyboardReachable(page, path);
        await context.close();
    }
}

async function runDashboard(browser) {
    const email = process.env.UI_EMAIL;
    const password = process.env.UI_PASSWORD;
    if (!email || !password)
        throw new Error(
            'UI_EMAIL and UI_PASSWORD are required in dashboard mode',
        );
    for (const viewport of VIEWPORTS) {
        const context = await browser.newContext({ viewport });
        const page = await context.newPage();
        console.log(`\n== dashboard @ ${viewport.name}`);
        await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
        await page.fill('input[name="email"]', email);
        await page.fill('input[name="password"]', password);
        await Promise.all([
            page.waitForURL((url) => !url.pathname.startsWith('/login'), {
                timeout: 20000,
            }),
            page.click('button[type="submit"]'),
        ]);
        check(
            !page.url().includes('/login'),
            `login succeeds @ ${viewport.name}`,
            page.url(),
        );
        if (INSPECT)
            await inspectPage(page, '/services/kmj-codebridge', viewport, {
                requireIcon: true,
            });
        if (!on('manage')) {
            await context.close();
            continue;
        }
        await page.goto(`${BASE}/services/kmj-codebridge`, {
            waitUntil: 'networkidle',
        });

        const manage = page
            .getByRole('link', { name: /manage devices/i })
            .or(page.getByRole('button', { name: /manage devices/i }));
        check(
            (await manage.count()) > 0,
            `/services/kmj-codebridge @ ${viewport.name}: "Manage devices" control exists`,
        );
        if ((await manage.count()) > 0) {
            await manage.first().focus();
            const focused = await page.evaluate(
                () => document.activeElement?.textContent ?? '',
            );
            check(
                /manage devices/i.test(focused),
                `/services/kmj-codebridge @ ${viewport.name}: "Manage devices" is keyboard-focusable`,
                focused.trim(),
            );
            await manage.first().click();
            await page.waitForLoadState('networkidle');
            const devicesVisible = await page.evaluate(() =>
                /devices/i.test(document.body.innerText),
            );
            check(
                devicesVisible,
                `/services/kmj-codebridge @ ${viewport.name}: Devices workspace opens`,
            );
        }
        await context.close();
    }
}

const browser = await chromium.launch({
    executablePath: CHROME,
    args: ['--no-sandbox'],
});
try {
    if (MODE === 'public') await runPublic(browser);
    else if (MODE === 'dashboard') await runDashboard(browser);
    else throw new Error(`Unknown UI_MODE ${MODE}`);
} finally {
    await browser.close();
}

console.log(
    `\n${checks} checks, ${failures.length} failed, ${warnings.length} warnings`,
);
if (failures.length > 0) {
    console.log('FAILURES:');
    for (const f of failures) console.log(` - ${f}`);
    process.exit(1);
}
