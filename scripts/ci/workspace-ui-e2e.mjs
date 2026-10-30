// CI-only: REAL authenticated browser session against the real Laravel app on a disposable PG18
// database. A verified customer logs in, queues approved named tools from the AI Workspace UI, the
// real kmj-codebridge worker claims and runs them, and the UI shows the durable events and evidence.
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.KMJ_PLAYWRIGHT_MODULE || 'playwright');
const [origin, email, password, device, project] = process.argv.slice(2);
if (process.env.GITHUB_ACTIONS !== 'true' || !origin || !email || !password) {
    console.error('BLOCKED: CI-only browser e2e');
    process.exit(2);
}
const failures = [];
const expect = (ok, message) => {
    if (!ok) failures.push(message);
    else console.log('ok -', message);
};
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const pageErrors = [];
page.on('pageerror', (e) => pageErrors.push(e.message));
const diag = [];
page.on('console', (m) => ['error', 'warning'].includes(m.type()) && diag.push(`console.${m.type()}: ${m.text().slice(0, 200)}`));
page.on('requestfailed', (r) => diag.push(`requestfailed: ${r.url()} ${r.failure()?.errorText}`));
page.on('response', (r) => r.status() >= 400 && diag.push(`http ${r.status()}: ${r.url()}`));
const url = `${origin}/services/kmj-codebridge/workspace?device=${device}&project=${project}`;

async function waitForStatus(status, count, timeoutMs = 75_000) {
    const end = Date.now() + timeoutMs;
    while (Date.now() < end) {
        const n = await page.locator(`[data-testid="job-list"] li[data-status="${status}"]`).count();
        if (n >= count) return true;
        await page.waitForTimeout(1500);
        await page.reload({ waitUntil: 'networkidle' });
    }
    return false;
}

try {
    await page.goto(`${origin}/login`, { waitUntil: 'networkidle' });
    await page.fill('input[name="email"]', email);
    await page.fill('input[name="password"]', password);
    await Promise.all([
        page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 30_000 }),
        page.keyboard.press('Enter'),
    ]);
    expect(true, 'authenticated through the real login form');

    await page.goto(url, { waitUntil: 'networkidle' });
    expect(await page.getByTestId('ai-workspace').isVisible(), 'AI workspace renders for the entitled customer');
    expect(await page.getByTestId('tool-jobs').isVisible(), 'device tool request panel is available');
    expect(await page.getByTestId('jobs-empty').isVisible(), 'no synthetic jobs are shown before any request');

    // 1) read tool
    await page.selectOption('#ws-tool', 'git_status');
    await page.getByTestId('queue-tool').click();
    expect(await waitForStatus('succeeded', 1), 'git_status was claimed and completed by the real device worker');
    await page.locator('[data-testid="job-list"] li[data-status="succeeded"] button').first().click();
    const jobEvents = page.getByTestId('job-list').getByTestId('job-events');
    await jobEvents.waitFor({ timeout: 20_000 });
    const events1 = (await jobEvents.innerText()).toLowerCase();
    for (const kind of ['queued', 'claimed', 'started', 'succeeded'])
        expect(events1.includes(kind), `durable event "${kind}" is shown for git_status`);
    const list1 = (await page.getByTestId('job-list').innerText()).toLowerCase();
    expect(list1.includes('commit_sha') && list1.includes('pass'), 'evidence shows commit_sha and result=pass');

    // 2) execute tool with a configured gate
    await page.selectOption('#ws-tool', 'quality_gate');
    await page.fill('#ws-gate', 'fast');
    await page.getByTestId('queue-tool').click();
    expect(await waitForStatus('succeeded', 2), 'quality_gate "fast" completed on the device');
    const list2 = (await page.getByTestId('job-list').innerText()).toLowerCase();
    expect(list2.includes('exit_code') && list2.includes('fast'), `gate evidence shows the gate id and exit_code ${list2.includes('exit_code') ? '' : JSON.stringify(list2.slice(0, 700))}`);

    // 3) an unconfigured gate is refused by the device and reported honestly, never faked as success
    await page.selectOption('#ws-tool', 'quality_gate');
    await page.fill('#ws-gate', 'nonexistent');
    await page.getByTestId('queue-tool').click();
    expect(await waitForStatus('failed', 1), 'unconfigured gate is reported as failed by the device');
    expect(
        (await page.getByTestId('job-list').innerText()).toLowerCase().includes('gate_not_allowed'),
        'the failure is explained in the UI',
    );
    await page.screenshot({ path: process.env.KMJ_E2E_SHOT || 'workspace-ui-e2e.png', fullPage: true });
    expect(pageErrors.length === 0, `no uncaught page errors ${JSON.stringify(pageErrors)}`);
} catch (error) {
    failures.push(`exception: ${String(error).slice(0, 400)}`);
    console.log('DIAG', JSON.stringify(diag.slice(0, 25)), 'PAGE_ERRORS', JSON.stringify(pageErrors.slice(0, 5)));
    try {
        console.log('URL', page.url());
        const html = await page.content();
        console.log('TAGS', JSON.stringify((html.match(/<(link|script)[^>]*(build|vite)[^>]*>/g) ?? []).slice(0, 12)));
        const res = await fetch(`${origin}/login`);
        console.log('LINK_HEADER', JSON.stringify(res.headers.get('link')?.slice(0, 600) ?? null));
    } catch {}
}
await browser.close();
if (failures.length) {
    console.log('WORKSPACE_UI_E2E=FAIL', JSON.stringify(failures));
    process.exit(1);
}
console.log('WORKSPACE_UI_E2E=PASS');
