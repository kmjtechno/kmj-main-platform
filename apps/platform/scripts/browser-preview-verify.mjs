import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.KMJ_PLAYWRIGHT_MODULE || 'playwright');
const base = new URL(process.env.KMJ_PREVIEW_URL || 'http://127.0.0.1:4173');
if (!['127.0.0.1', 'localhost', '[::1]'].includes(base.hostname))
    throw new Error(
        'Preview verification is restricted to loopback. Use a separately reviewed authenticated live-smoke profile for production.',
    );
const out = path.resolve(process.env.KMJ_SCREENSHOT_DIR || 'visual-results');
await mkdir(out, { recursive: true });
let args = [];
let executablePath = process.env.KMJ_CHROMIUM_EXECUTABLE;
if (process.env.KMJ_CHROMIUM_MODULE) {
    const loaded = require(process.env.KMJ_CHROMIUM_MODULE);
    const binary = loaded.default || loaded;
    executablePath = await binary.executablePath();
    args = binary.args;
}
if (
    args.some((arg) =>
        /^--(?:no-sandbox|disable-(?:setuid|namespace|seccomp-filter|gpu)-sandbox)(?:=|$)/.test(
            arg,
        ),
    )
)
    throw new Error('Sandbox-disabled Chromium arguments are not permitted');
const browser = await chromium.launch({
    headless: true,
    args,
    executablePath,
    chromiumSandbox: true,
});
const results = [];
try {
    // Covers the smallest supported mobile layout through full desktop.
    for (const width of [320, 390, 768, 1170, 1440, 1536, 1920, 2560])
        for (const [name, route] of [
            ['landing', '/'],
            ['super-admin', '/super-admin'],
            ['owner-ops', '/operator/ops'],
            ['owner-developer', '/developer/apps'],
            ['owner-devices', '/operator/codebridge/owner-plan'],
        ]) {
            const page = await browser.newPage({
                viewport: { width, height: 1024 },
                reducedMotion: 'reduce',
            });
            const errors = [];
            page.on('pageerror', (e) => errors.push(e.message));
            const response = await page.goto(new URL(route, base).href, {
                waitUntil: 'networkidle',
            });
            await page.evaluate(async () => {
                for (let y = 0; y < document.body.scrollHeight; y += 600) {
                    scrollTo(0, y);
                    await new Promise((r) => setTimeout(r, 40));
                }
                scrollTo(0, 0);
                await document.fonts.ready;
            });
            if (name === 'owner-developer') {
                const shell = page.locator('.owner-module-shell');
                if ((await shell.count()) !== 1)
                    errors.push(
                        'Verified owner developer page lost its locked shell',
                    );
                const appearance = await page
                    .locator('.owner-shared-page > section')
                    .first()
                    .evaluate((el) => ({
                        background: getComputedStyle(el).backgroundImage,
                        color: getComputedStyle(el).color,
                    }));
                if (!appearance.background.includes('rgb(11, 16, 22)'))
                    errors.push('Owner developer card theme drifted');
            }
            if (name === 'super-admin') {
                const advanced = page.locator('.kmj-os-advanced');
                await advanced.locator(':scope > summary').click();
                if (!(await advanced.evaluate((node) => node.open)))
                    errors.push(
                        'Real dashboard advanced controls did not open',
                    );
                const card = await advanced
                    .locator('.kmj-admin-category')
                    .first()
                    .evaluate((node) => ({
                        background: getComputedStyle(node).backgroundImage,
                        radius: getComputedStyle(node).borderRadius,
                    }));
                if (
                    !card.background.includes('rgb(11, 16, 22)') ||
                    card.radius !== '11px'
                )
                    errors.push(
                        'Expanded dashboard controls drifted from the locked owner theme',
                    );
                if (
                    await page.evaluate(
                        () =>
                            document.documentElement.scrollWidth >
                            innerWidth + 1,
                    )
                )
                    errors.push('Expanded dashboard controls overflow');
                if (width === 390 || width === 1440)
                    await page.screenshot({
                        path: path.join(
                            out,
                            name + '-advanced-' + width + '.png',
                        ),
                        fullPage: true,
                    });
                await advanced.locator(':scope > summary').click();
            }
            if (name === 'owner-devices') {
                await page
                    .getByRole('heading', {
                        name: 'CodeBridge Control Center',
                        exact: true,
                    })
                    .waitFor();
            } else
                await page
                    .locator(
                        name === 'landing'
                            ? 'h1'
                            : name === 'owner-ops'
                              ? '.owner-module-main h1'
                              : '.owner-main h1',
                    )
                    .waitFor();
            // Horizontal carousels can keep valid lazy images outside the
            // viewport. Decode every asset before checking failures so that
            // off-screen, unrequested images are not counted as broken.
            const broken = await page
                .locator('img')
                .evaluateAll(async (images) => {
                    for (const image of images) image.loading = 'eager';
                    const decoded = await Promise.allSettled(
                        images.map((image) => image.decode()),
                    );
                    return images
                        .filter(
                            (image, index) =>
                                decoded[index]?.status === 'rejected' ||
                                !image.complete ||
                                image.naturalWidth === 0,
                        )
                        .map((image) => image.getAttribute('src'));
                });
            const overflow = await page.evaluate(
                () => document.documentElement.scrollWidth > innerWidth + 1,
            );
            if (name === 'landing') {
                // Previous fixture was signed in and never displayed the
                // public Login / Register CTAs. Check actual rendered bounds.
                const account = await page.evaluate(() => {
                    const shell = document.querySelector('.locked-landing');
                    const login = document.querySelector(
                        '.lock-auth .lock-auth-login',
                    );
                    const register = document.querySelector(
                        '.lock-auth .lock-auth-register',
                    );
                    const rect = (el) => {
                        if (!el) return null;
                        const r = el.getBoundingClientRect();
                        const style = getComputedStyle(el);
                        return {
                            left: r.left,
                            right: r.right,
                            width: r.width,
                            height: r.height,
                            visible:
                                style.display !== 'none' &&
                                style.visibility !== 'hidden' &&
                                r.width > 0 &&
                                r.height > 0,
                        };
                    };
                    return {
                        shell: rect(shell),
                        viewportWidth: document.documentElement.clientWidth,
                        login: rect(login),
                        register: rect(register),
                        loginHref: login?.getAttribute('href'),
                        registerHref: register?.getAttribute('href'),
                        registerText: register?.textContent?.trim(),
                    };
                });
                const withinViewport = (rect) =>
                    !!rect &&
                    rect.visible &&
                    rect.left >= -1 &&
                    rect.right <= width + 1;
                if (
                    !withinViewport(account.login) ||
                    account.loginHref !== '/login'
                )
                    errors.push(
                        'Signed-out Login CTA missing or outside viewport',
                    );
                if (
                    !withinViewport(account.register) ||
                    account.registerHref !== '/register'
                )
                    errors.push(
                        'Signed-out Register CTA missing or outside viewport',
                    );
                if (account.registerText !== 'Register')
                    errors.push('Paused-registration label was not disclosed');
                if (
                    !withinViewport(account.shell) ||
                    Math.abs(account.shell.width - account.viewportWidth) > 1 ||
                    Math.abs(account.shell.left) > 1
                )
                    errors.push('Landing canvas must fill the viewport width');
                const expected = [
                    'Our Flagship Products',
                    'What We Build',
                    'A Complete and Connected Ecosystem',
                    'Industries We Serve',
                    'Our Roadmap',
                ];
                const headings = await page.locator('h2').allTextContents();
                let previous = -1;
                for (const heading of expected) {
                    const index = headings.indexOf(heading);
                    if (index <= previous)
                        errors.push('Missing or reordered section: ' + heading);
                    previous = index;
                }
                if (await page.locator('.lock-kristi-box').count())
                    errors.push('Kristi must start collapsed');
                await page
                    .getByRole('button', { name: 'Ask Kristi', exact: true })
                    .click();
                await page
                    .getByRole('button', {
                        name: 'Licensing & pricing',
                        exact: true,
                    })
                    .click();
                if (
                    !(await page.getByRole('status').innerText()).includes(
                        'Licensing Hub',
                    )
                )
                    errors.push('Kristi guidance failed');
                await page
                    .getByRole('textbox', { name: 'Ask Kristi', exact: true })
                    .fill('technical support');
                await page
                    .getByRole('button', { name: 'Send message', exact: true })
                    .click();
                if (
                    !(await page.getByRole('status').innerText()).includes(
                        'Visit support',
                    )
                )
                    errors.push(
                        'Typed technical support selected the wrong topic',
                    );
                const overview = page.getByRole('button', {
                    name: 'Company overview',
                });
                await overview.click();
                await page
                    .getByRole('dialog', { name: 'Company overview' })
                    .waitFor();
                await page.keyboard.press('Escape');
                await page
                    .getByRole('dialog', { name: 'Company overview' })
                    .waitFor({ state: 'hidden' });
                if (
                    !(await overview.evaluate(
                        (element) => element === document.activeElement,
                    ))
                )
                    errors.push(
                        'Company overview did not restore keyboard focus',
                    );
                await page
                    .getByRole('button', { name: 'Close Kristi', exact: true })
                    .click();
                await page
                    .getByRole('button', {
                        name: 'Ask Kristi',
                        exact: true,
                    })
                    .click();
                await page
                    .getByRole('button', { name: 'Close Kristi', exact: true })
                    .click();
            } else if (name === 'super-admin') {
                // Canonical URL is required; a preview silently serving the
                // guest landing at this path must never satisfy visual QA.
                const ownerShell = await page
                    .locator('.owner-lock')
                    .boundingBox();
                const availableWidth = await page.evaluate(
                    () => document.documentElement.clientWidth,
                );
                if (
                    !ownerShell ||
                    Math.abs(ownerShell.x) > 1 ||
                    Math.abs(ownerShell.width - availableWidth) > 1
                )
                    errors.push(
                        'Owner Command OS must fill the viewport width',
                    );
                await page.keyboard.press('Control+k');
                await page.getByRole('dialog').waitFor();
                await page
                    .getByRole('textbox', {
                        name: 'Search owner workspaces and catalog products',
                    })
                    .fill('payment');
                if (
                    !(await page.getByRole('dialog').innerText()).includes(
                        'Orders & Payments',
                    )
                )
                    errors.push('Command search failed');
                await page.keyboard.press('Escape');
                await page.getByRole('dialog').waitFor({ state: 'hidden' });
                if (width <= 390) {
                    await page
                        .getByRole('button', {
                            name: 'Toggle owner navigation',
                        })
                        .click();
                    await page
                        .getByRole('navigation', { name: 'BUSINESS' })
                        .waitFor({ state: 'visible' });
                    await page.keyboard.press('Escape');
                }
            }
            if (name === 'owner-devices') {
                if (
                    (await page
                        .getByRole('heading', {
                            name: 'CodeBridge Control Center',
                            exact: true,
                        })
                        .count()) !== 1
                )
                    errors.push('Owner CodeBridge controls missing');
                if (
                    (await page
                        .getByRole('heading', {
                            name: 'Device Control Center',
                            exact: true,
                        })
                        .count()) !== 1
                )
                    errors.push('Real device control component missing');
                const search = page.getByRole('textbox', {
                    name: 'Search devices and projects',
                });
                await search.fill('no-such-preview-device');
                if (
                    !(await page
                        .getByText('No devices match these filters.', {
                            exact: true,
                        })
                        .isVisible())
                )
                    errors.push('Device search failed');
                await search.fill('');
                await page
                    .getByRole('button', {
                        name: 'Details & diagnose',
                        exact: true,
                    })
                    .click();
                if (
                    (await page
                        .getByRole('button', {
                            name: 'Hide details',
                            exact: true,
                        })
                        .getAttribute('aria-expanded')) !== 'true'
                )
                    errors.push('Device details did not open');
            }
            if (name === 'owner-ops') {
                if (
                    (await page
                        .getByRole('heading', {
                            name: 'KMJ Ops Command Center',
                            exact: true,
                        })
                        .count()) !== 1
                )
                    errors.push('Real Operations component missing');
                if (
                    (await page
                        .locator('aside[aria-label="Owner navigation"]')
                        .count()) !== 1
                )
                    errors.push('Shared owner sidebar missing');
                if (
                    (await page
                        .locator('.owner-sidebar [aria-current="page"]')
                        .count()) !== 1
                )
                    errors.push('Exactly one current owner module required');
                if (
                    (await page
                        .getByRole('navigation', {
                            name: 'Super Admin modules',
                        })
                        .count()) !== 1
                )
                    errors.push('Real Operations module tabs missing');
                if (
                    (await page
                        .getByText('My workspace', { exact: true })
                        .count()) > 0
                )
                    errors.push(
                        'Old customer workspace leaked into owner page',
                    );
                if (width <= 390) {
                    await page
                        .getByRole('button', {
                            name: 'Toggle owner navigation',
                        })
                        .click();
                    await page
                        .getByRole('navigation', { name: 'OPERATIONS' })
                        .waitFor({ state: 'visible' });
                    await page.keyboard.press('Escape');
                    await page
                        .getByRole('navigation', { name: 'OPERATIONS' })
                        .waitFor({ state: 'hidden' });
                }
            }
            if (name === 'landing') {
                await page.reload({ waitUntil: 'networkidle' });
                await page.setViewportSize({
                    width,
                    height: await page.evaluate(
                        () => document.documentElement.scrollHeight,
                    ),
                });
            }
            const screenshot = path.join(out, `${name}-${width}.png`);
            await page.screenshot({ path: screenshot, fullPage: true });
            results.push({
                page: name,
                width,
                http: response.status(),
                broken,
                overflow,
                errors,
                screenshot,
                pass:
                    response.status() === 200 &&
                    !broken.length &&
                    !overflow &&
                    !errors.length,
            });
            await page.close();
        }
} finally {
    await browser.close();
}
await writeFile(
    path.join(out, 'verification.json'),
    JSON.stringify(
        { mode: 'local-real-components-synthetic-data', results },
        null,
        2,
    ),
);
console.log(JSON.stringify(results, null, 2));
if (results.some((r) => !r.pass)) process.exitCode = 1;
