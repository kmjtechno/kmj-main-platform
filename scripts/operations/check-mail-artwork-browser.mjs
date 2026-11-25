import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';

const root = process.cwd();
const require = createRequire(resolve(root, 'package.json'));
const { chromium } = require('playwright');
const out = resolve(root, 'visual-results/mail-artwork');
const themes = ['signature-red', 'blue-wave', 'white-geometric', 'blue-letterhead', 'blue-signature', 'executive-gold'];
const browser = await chromium.launch({
    headless: true,
    chromiumSandbox: true,
    executablePath: process.env.KMJ_CHROMIUM_EXECUTABLE,
});
const results = [];
try {
    for (const theme of themes) {
        const html = await readFile(resolve(out, theme + '.html'), 'utf8');
        for (const width of [760, 390, 320]) {
            const page = await browser.newPage({ viewport: { width, height: 1000 } });
            const errors = [];
            page.on('pageerror', error => errors.push(error.message));
            // Serve only the exact checked-in first-party assets. No live network, login or SMTP.
            await page.route('**/*', async route => {
                const url = new URL(route.request().url());
                const match = url.pathname.match(/^\/assets\/brand\/mail\/([a-z-]+)\/(header\.jpg|footer\.jpg|enterprise\.png|projection\.png|remote\.png|cloud\.png|ai\.png)$/);
                if (url.origin !== 'https://kmjtechno.com' || !match || match[1] !== theme) {
                    await route.abort();
                    return;
                }
                await route.fulfill({ path: resolve(root, 'public', url.pathname.slice(1)), contentType: match[2].endsWith('.jpg') ? 'image/jpeg' : 'image/png' });
            });
            try {
                await page.setContent(html, { waitUntil: 'load' });
                const state = await page.evaluate(() => ({
                    overflow: document.documentElement.scrollWidth - innerWidth,
                    images: Array.from(document.images).map(img => ({ src: img.getAttribute('src'), ok: img.complete && img.naturalWidth > 0, width: img.getBoundingClientRect().width })),
                    heading: document.querySelector('h1')?.textContent,
                    text: document.body.innerText,
                }));
                await page.screenshot({ path: resolve(out, theme + '-' + width + '.png'), fullPage: true });
                assert.equal(state.images.length, 7, theme + ' image count');
                assert.ok(state.images.every(img => img.ok && img.width > 0), theme + ' broken artwork');
                assert.ok(state.overflow <= 1, theme + ' horizontal overflow at ' + width);
                assert.equal(state.heading, 'Project status update');
                assert.ok(state.text.includes('synthetic no-send preview'));
                assert.ok(state.text.includes('info@kmjtechno.com'));
                assert.deepEqual(errors, []);
                results.push({ theme, width, images: state.images.length, overflow: state.overflow, verdict: 'PASS' });
            } finally {
                await page.close();
            }
        }
    }
} finally {
    await browser.close();
    await writeFile(resolve(out, 'results.json'), JSON.stringify(results, null, 2) + '\n');
}
assert.equal(results.length, 18);
console.log('REAL_BLADE_EMAIL_BROWSER=PASS samples=18 SMTP_SEND=NONE');
