import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const server = await createServer({
    configFile: fileURLToPath(
        new URL('../visual/vite.config.ts', import.meta.url),
    ),
});
const results = [];
const out = 'visual-results/mail-workspace';
await mkdir(out, { recursive: true });
let browser;
try {
    await server.listen();
    const base = new URL(server.resolvedUrls.local[0]);
    assert.equal(base.hostname, '127.0.0.1');
    browser = await chromium.launch({
        headless: true,
        chromiumSandbox: true,
        executablePath: process.env.KMJ_CHROMIUM_EXECUTABLE,
    });
    for (const width of [390, 768, 1170, 1536, 1920]) {
        const page = await browser.newPage({
            viewport: { width, height: 960 },
            reducedMotion: 'reduce',
        });
        const errors = [];
        const mutations = [];
        page.on('pageerror', (error) => errors.push(error.message));
        await page.route('**/*', async (route) => {
            const request = route.request();
            const url = new URL(request.url());
            if (request.method() !== 'GET') {
                mutations.push(request.method());
                await route.abort();
                return;
            }
            if (url.origin !== base.origin) {
                await route.abort();
                return;
            }
            await route.continue();
        });
        try {
            await page.goto(new URL('/mail-workspace.html', base).href, {
                waitUntil: 'networkidle',
            });
            const reader = page.locator('.kmj-mail-reader');
            const ai = page.locator('#kmj-ai-copilot');
            await reader.getByRole('heading', { name: 'Inbox is clear' }).waitFor();
            assert.equal(
                await page.getByText('Synthetic sent-only record', { exact: true }).count(),
                0,
            );
            assert.equal(await ai.getAttribute('data-expanded'), 'false');
            assert.equal(await page.locator('#kmj-mail-ai-content').isVisible(), false);
            assert.equal(await reader.getByRole('button', { name: 'View Sent' }).isVisible(), true);
            const overflow = async () => {
                const state = await page.evaluate(() => ({
                    overflow: document.documentElement.scrollWidth - innerWidth,
                    elements: Array.from(document.querySelectorAll('body *'))
                        .map((node) => ({
                            tag: node.tagName,
                            className: node.getAttribute('class'),
                            right: Math.round(node.getBoundingClientRect().right),
                            width: Math.round(node.getBoundingClientRect().width),
                        }))
                        .filter((node) => node.right > innerWidth + 1 && node.width > 0)
                        .slice(0, 20),
                }));
                if (state.overflow > 1) {
                    console.error('MAIL_LAYOUT_OVERFLOW', width, JSON.stringify(state));
                    await page.screenshot({ path: out + '/overflow-' + width + '.png', fullPage: true });
                }
                return state.overflow;
            };
            assert.ok(await overflow() <= 1, 'Inbox overflow at ' + width);
            await page.screenshot({ path: out + '/inbox-' + width + '.png', fullPage: true });
            await ai.getByRole('button', { name: 'Open AI Assistant' }).click();
            assert.equal(await ai.getAttribute('data-expanded'), 'true');
            assert.equal(await page.locator('#kmj-mail-ai-content').isVisible(), true);
            assert.ok(await overflow() <= 1, 'Expanded AI overflow at ' + width);
            await page.screenshot({ path: out + '/ai-' + width + '.png', fullPage: true });
            await ai.getByRole('button', { name: 'Collapse AI Assistant' }).click();
            assert.equal(await ai.getAttribute('data-expanded'), 'false');
            await page.goto(new URL('/mail-workspace.html?folder=sent', base).href, {
                waitUntil: 'networkidle',
            });
            await reader.getByRole('heading', { name: 'Select a conversation' }).waitFor();
            assert.equal(await page.getByText('Synthetic sent-only record', { exact: true }).count(), 1);
            assert.equal(await reader.getByRole('button', { name: 'View Sent' }).count(), 0);
            assert.ok(await overflow() <= 1, 'Sent overflow at ' + width);
            await page.screenshot({ path: out + '/sent-' + width + '.png', fullPage: true });
            assert.deepEqual(mutations, []);
            assert.deepEqual(errors, []);
            results.push({ width, inbox: 'PASS', ai: 'PASS', sent: 'PASS', providerCalls: 0 });
        } finally {
            await page.close();
        }
    }
} finally {
    if (browser) await browser.close();
    await server.close();
    await writeFile(out + '/results.json', JSON.stringify(results, null, 2) + '\n');
}
assert.equal(results.length, 5);
console.log('MAIL_WORKSPACE_REAL_COMPONENT=PASS samples=15 SMTP_SEND=NONE');
