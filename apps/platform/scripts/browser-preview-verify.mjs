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
let args = ['--no-sandbox'];
let executablePath = process.env.KMJ_CHROMIUM_EXECUTABLE;
if (process.env.KMJ_CHROMIUM_MODULE) {
    const loaded = require(process.env.KMJ_CHROMIUM_MODULE);
    const binary = loaded.default || loaded;
    executablePath = await binary.executablePath();
    args = binary.args;
}
const browser = await chromium.launch({ headless: true, args, executablePath });
const results = [];
try {
    // Covers the smallest supported mobile layout through full desktop.
    for (const width of [320, 390, 768, 1170, 1440, 1536])
        for (const [name, route] of [
            ['landing', '/'],
            ['super-admin', '/operator'],
            ['owner-ops', '/operator/ops'],
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
                const overview = page.getByRole('button', {
                    name: 'Watch Company Video',
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
                        name: "Hi, I'm Kristi",
                        exact: true,
                    })
                    .click();
            } else if (name === 'super-admin') {
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
                        .getByRole('complementary', {
                            name: 'Owner navigation',
                        })
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
                        .getByRole('navigation', { name: 'Super Admin modules' })
                        .count()) !== 1
                )
                    errors.push('Real Operations module tabs missing');
                if (
                    (await page.getByText('My workspace', { exact: true }).count()) >
                    0
                )
                    errors.push('Old customer workspace leaked into owner page');
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
