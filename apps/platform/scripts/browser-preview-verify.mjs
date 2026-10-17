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
    for (const width of [1536, 768, 390])
        for (const [name, route] of [
            ['landing', '/'],
            ['super-admin', '/operator'],
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
                .locator(name === 'landing' ? 'h1' : '.owner-main h1')
                .waitFor();
            const broken = await page
                .locator('img')
                .evaluateAll((images) =>
                    images
                        .filter((i) => !i.complete || i.naturalWidth === 0)
                        .map((i) => i.getAttribute('src')),
                );
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
                    errors.push('Company overview did not restore keyboard focus');
                await page
                    .getByRole('button', { name: 'Close Kristi', exact: true })
                    .click();
                await page
                    .getByRole('button', {
                        name: "Hi, I'm Kristi",
                        exact: true,
                    })
                    .click();
            } else {
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
                if (width === 390) {
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
