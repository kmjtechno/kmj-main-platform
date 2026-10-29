import { createRequire } from 'node:module';
import { createServer } from 'vite';
import { fileURLToPath } from 'node:url';
// Loopback-only, synthetic-data browser check of the 3-pane AI workspace.
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.KMJ_PLAYWRIGHT_MODULE || 'playwright');
const server = await createServer({
    configFile: fileURLToPath(
        new URL('../visual/vite.config.ts', import.meta.url),
    ),
});
await server.listen();
const base = new URL(server.resolvedUrls.local[0]);
const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.KMJ_CHROMIUM_EXECUTABLE,
});
const failures = [];
const expect = (ok, message) => {
    if (!ok) failures.push(message);
};
try {
    for (const width of [390, 768, 1440]) {
        const page = await browser.newPage({
            viewport: { width, height: 900 },
        });
        const errors = [];
        page.on('pageerror', (e) => errors.push(e.message));
        await page.goto(
            new URL('/services/kmj-codebridge/workspace', base).href,
            { waitUntil: 'networkidle' },
        );
        const tag = `w${width}`;
        expect(
            await page.getByTestId('ai-workspace').isVisible(),
            `${tag}: workspace missing`,
        );
        expect(
            await page.getByTestId('composer').isDisabled(),
            `${tag}: composer must be disabled`,
        );
        expect(
            (await page.getByTestId('composer-blocked').innerText()).includes(
                'Blocked',
            ),
            `${tag}: blocked reason missing`,
        );
        const text = await page.getByTestId('ai-workspace').innerText();
        expect(
            !/\b\d+\s?%/.test(text),
            `${tag}: percentage shown without data`,
        );
        expect(
            !/12 of 18|GPT-4o|unlimited/i.test(text),
            `${tag}: forbidden dummy/claim text`,
        );
        expect(
            text.includes('not verified'),
            `${tag}: live status must say not verified`,
        );
        expect(
            await page
                .getByTestId('admitted-models')
                .innerText()
                .then((t) => t.includes('qa-free-model')),
            `${tag}: admitted model missing`,
        );
        const overflow = await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth,
        );
        expect(!overflow, `${tag}: horizontal overflow`);
        if (width < 1024) {
            const left = page.getByTestId('pane-left');
            expect(
                !(await left
                    .isVisible()
                    .then(
                        (v) =>
                            v && left.boundingBox().then((b) => b && b.x >= 0),
                    )),
                `${tag}: left drawer open by default`,
            );
            await page.getByRole('button', { name: 'Open projects' }).click();
            await page.waitForTimeout(350);
            const box = await left.boundingBox();
            expect(box && box.x >= 0, `${tag}: left drawer did not open`);
            await page
                .getByRole('button', { name: 'Close projects', exact: true })
                .click();
            await page
                .getByRole('button', { name: 'Open tools and context' })
                .click();
            await page.waitForTimeout(350);
            const right = await page.getByTestId('pane-right').boundingBox();
            expect(
                right && right.x + right.width <= width + 1,
                `${tag}: right drawer did not open`,
            );
        } else {
            const [l, c, r] = await Promise.all(
                ['pane-left', 'pane-center', 'pane-right'].map((id) =>
                    page.getByTestId(id).boundingBox(),
                ),
            );
            expect(l.x < c.x && c.x < r.x, `${tag}: panes not in 3 columns`);
            expect(
                c.width > l.width && c.width > r.width,
                `${tag}: center pane not dominant`,
            );
        }
        if (width < 1024)
            await page
                .getByRole('button', {
                    name: 'Close tools and context',
                    exact: true,
                })
                .click();
        await page.getByText('Tool & job timeline').click();
        expect(
            await page
                .getByText('Job status lives on the paired device')
                .isVisible(),
            `${tag}: job events reason missing`,
        );
        expect(errors.length === 0, `${tag}: page errors ${errors.join(';')}`);
        await page.close();
    }
} finally {
    await browser.close();
    await server.close();
}
if (failures.length) {
    console.error(failures.join('\n'));
    process.exit(1);
}
console.log(
    'WORKSPACE_BROWSER_VERIFY PASS (390/768/1440, synthetic data, not release evidence)',
);
