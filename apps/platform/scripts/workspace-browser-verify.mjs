import { createRequire } from 'node:module';
import { createServer } from 'vite';
import { fileURLToPath } from 'node:url';
// Loopback-only browser check of the 3-pane AI workspace. The Inertia responses are
// SYNTHETIC (intercepted in the browser), so this proves UI state handling only.
// It is not release evidence and does not exercise Laravel, the database or a provider.
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.KMJ_PLAYWRIGHT_MODULE || 'playwright');
const server = await createServer({
    configFile: fileURLToPath(
        new URL('../visual/vite.config.ts', import.meta.url),
    ),
});
await server.listen();
const fixture = await server.ssrLoadModule('/workspace-fixture.ts');
const { message, workspaceProps } = fixture;
const base = new URL(server.resolvedUrls.local[0]);
const PAGE = '/services/kmj-codebridge/workspace';
const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.KMJ_CHROMIUM_EXECUTABLE,
});
const failures = [];
const expect = (ok, message) => {
    if (!ok) failures.push(message);
};
const inertia = (props) => ({
    status: 200,
    headers: {
        'X-Inertia': 'true',
        'Content-Type': 'application/json',
        Vary: 'X-Inertia',
    },
    body: JSON.stringify({
        component: 'services/codebridge-workspace',
        props: { errors: {}, ...props },
        url: PAGE,
        version: 'locked-ui-visual-fixture',
    }),
});
const ev = (id, kind, status, detail = null) => ({
    id,
    message_id: 'm2',
    kind,
    status,
    detail,
    at: '2026-10-29T12:00:0' + id + '+00:00',
});

async function layoutChecks(width) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await page.goto(new URL(PAGE, base).href, { waitUntil: 'networkidle' });
    const tag = `w${width}`;
    expect(
        await page.getByTestId('ai-workspace').isVisible(),
        `${tag}: workspace missing`,
    );
    const text = await page.getByTestId('ai-workspace').innerText();
    expect(!/\b\d+\s?%/.test(text), `${tag}: percentage shown without data`);
    expect(
        !/12 of 18|GPT-4o|unlimited/i.test(text),
        `${tag}: forbidden dummy/claim text`,
    );
    expect(
        text.includes('not verified'),
        `${tag}: live status must say not verified`,
    );
    expect(
        await page.getByTestId('composer').isEnabled(),
        `${tag}: composer should be enabled with project+chat+model`,
    );
    expect(
        await page.getByTestId('send').isDisabled(),
        `${tag}: send must be disabled when empty`,
    );
    expect(
        !(await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth,
        )),
        `${tag}: horizontal overflow`,
    );
    if (width < 1024) {
        await page.getByRole('button', { name: 'Open projects' }).click();
        await page.waitForTimeout(350);
        expect(
            (await page.getByTestId('pane-left').boundingBox())?.x >= 0,
            `${tag}: left drawer did not open`,
        );
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
        await page
            .getByRole('button', {
                name: 'Close tools and context',
                exact: true,
            })
            .click();
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
    expect(errors.length === 0, `${tag}: page errors ${errors.join(';')}`);
    await page.close();
}

async function sendFlow() {
    const page = await browser.newPage({
        viewport: { width: 1440, height: 900 },
    });
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message));
    const posts = [];
    let polls = 0;
    const user = message('u1', 'user', 'complete', 'Explain the build');
    const running = message('m2', 'assistant', 'running', '', {
        elapsed_seconds: 4,
    });
    const done = message(
        'm2',
        'assistant',
        'complete',
        'Synthetic reply text',
        { finished_at: '2026-10-29T12:00:05+00:00', elapsed_seconds: 5 },
    );
    await page.route(
        '**/services/kmj-codebridge/workspace/conversations/qa-conv/messages',
        (route) => {
            posts.push(route.request().postDataJSON());
            route.fulfill(
                inertia(
                    workspaceProps(
                        [user, running],
                        [
                            ev(
                                1,
                                'inference_started',
                                'running',
                                'qa-free-model',
                            ),
                        ],
                    ),
                ),
            );
        },
    );
    await page.route(
        (url) => url.pathname === PAGE,
        (route) => {
            if (route.request().headers()['x-inertia'] !== 'true')
                return route.fallback();
            polls += 1;
            return route.fulfill(
                inertia(
                    workspaceProps(
                        [user, done],
                        [
                            ev(
                                1,
                                'inference_started',
                                'running',
                                'qa-free-model',
                            ),
                            ev(
                                2,
                                'inference_completed',
                                'complete',
                                'qa-free-model',
                            ),
                        ],
                    ),
                ),
            );
        },
    );
    await page.goto(new URL(PAGE, base).href, { waitUntil: 'networkidle' });
    await page.getByTestId('composer').fill('Explain the build');
    await page.getByTestId('send').click();
    await page.getByTestId('running-status').waitFor({ timeout: 5000 });
    expect(
        posts.length === 1 &&
            posts[0].content === 'Explain the build' &&
            posts[0].provider_id === 'qa-provider' &&
            posts[0].model === 'qa-free-model',
        'send: wrong request body',
    );
    expect(
        (await page.getByTestId('running-status').innerText()).includes(
            '4s elapsed',
        ),
        'send: running status must show the server elapsed time',
    );
    expect(
        await page.getByTestId('cancel').isVisible(),
        'send: cancel missing while running',
    );
    expect(
        await page.getByTestId('composer').isDisabled(),
        'send: composer must be disabled while running',
    );
    await page
        .getByTestId('message-assistant')
        .filter({ hasText: 'Synthetic reply text' })
        .waitFor({ timeout: 8000 });
    expect(polls >= 1, 'send: transcript was not re-read while running');
    expect(
        await page.getByTestId('composer').isEnabled(),
        'send: composer must re-enable after completion',
    );
    if (!(await page.getByTestId('event-list').isVisible()))
        await page.getByText('Workflow events').click();
    expect(
        (await page.getByTestId('event-list').innerText()).includes(
            'Reply received',
        ),
        'send: completed event not listed',
    );
    expect(errors.length === 0, `send: page errors ${errors.join(';')}`);
    await page.close();
}

async function failureAndRetryFlow() {
    const page = await browser.newPage({
        viewport: { width: 1440, height: 900 },
    });
    const user = message('u1', 'user', 'complete', 'Hi');
    const failed = message('m2', 'assistant', 'failed', '', {
        error_code: 'rate_limited',
        finished_at: '2026-10-29T12:00:02+00:00',
    });
    const retried = message('m3', 'assistant', 'complete', 'Recovered text', {
        retry_of: 'm2',
    });
    let retryBody = null;
    await page.route('**/messages/m2/retry', (route) => {
        retryBody = route.request().postDataJSON();
        route.fulfill(inertia(workspaceProps([user, failed, retried])));
    });
    await page.route(
        (url) => url.pathname === PAGE,
        (route) =>
            route.request().headers()['x-inertia'] === 'true'
                ? route.fulfill(
                      inertia(
                          workspaceProps(
                              [user, failed],
                              [
                                  ev(
                                      1,
                                      'inference_failed',
                                      'failed',
                                      'rate_limited',
                                  ),
                              ],
                          ),
                      ),
                  )
                : route.fallback(),
    );
    await page.goto(new URL(PAGE, base).href + '?c=x', {
        waitUntil: 'networkidle',
    });
    // Initial synthetic props are the empty chat; load the failed state through the project click.
    await page
        .getByRole('button', { name: /Synthetic preview project/ })
        .click();
    await page.getByTestId('message-problem').waitFor({ timeout: 5000 });
    expect(
        (await page.getByTestId('message-problem').innerText()).includes(
            'rate limiting',
        ),
        'failure: plain-language reason missing',
    );
    await page.getByTestId('retry').click();
    await page.getByText('Recovered text').waitFor({ timeout: 5000 });
    expect(
        retryBody && retryBody.model === 'qa-free-model',
        'retry: wrong request body',
    );
    expect(
        (await page.getByTestId('message-assistant').count()) === 2,
        'retry: failed attempt must stay on record',
    );
    await page.close();
}

try {
    for (const width of [390, 768, 1440]) await layoutChecks(width);
    await sendFlow();
    await failureAndRetryFlow();
} finally {
    await browser.close();
    await server.close();
}
if (failures.length) {
    console.error(failures.join('\n'));
    process.exit(1);
}
console.log(
    'WORKSPACE_BROWSER_VERIFY PASS (layout 390/768/1440 + send/running/cancel UI/failure/retry; synthetic Inertia responses, not release evidence)',
);
