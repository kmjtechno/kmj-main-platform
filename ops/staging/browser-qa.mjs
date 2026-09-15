// Bounded staging QA: browser evidence without an LLM or additional dependencies.
import { spawn } from 'node:child_process';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const origin = 'https://staging.kmjtechno.com';
const pages = [
    { path: '/', marker: 'Verified delivery progress' },
    { path: '/info', marker: 'Staging live operations monitor' },
    { path: '/login', marker: null },
];

export function matchesMarker(text, marker) {
    if (marker === null) return true;
    const normalize = value => value.replace(/\s+/g, ' ').trim().toLowerCase();
    return normalize(text).includes(normalize(marker));
}

export function assess(sample) {
    const failures = [];
    if (sample.url !== origin + sample.path) failures.push('unexpected_navigation');
    if (sample.httpStatus !== 200) failures.push('document_http_status');
    if (sample.bodyLength < 40) failures.push('blank_page');
    if (!sample.markerFound) failures.push('expected_content_missing');
    if (sample.exceptions > 0) failures.push('javascript_exception');
    return { failures, warnings: sample.overflowPx > 2 ? ['horizontal_overflow'] : [] };
}

export async function main() {
    const expectedSha = process.argv[2];
    if (!/^[0-9a-f]{40}$/.test(expectedSha || '')) throw new Error('full_commit_sha_required');
    const executable = process.env.KMJ_STAGING_CHROME;
    if (!executable) throw new Error('staging_browser_required');
    const output = process.env.KMJ_QA_OUTPUT || 'staging-qa';
    await mkdir(output, { recursive: true });
    const profile = await mkdtemp(join(tmpdir(), 'kmj-qa-'));
    // Reuse the existing staging headless-shell launch posture. No exposed port.
    const browser = spawn(executable, [
        '--headless', '--no-sandbox', '--disable-gpu', '--remote-debugging-pipe',
        '--no-first-run', `--user-data-dir=${profile}`, 'about:blank',
    ], { stdio: ['ignore', 'ignore', 'ignore', 'pipe', 'pipe'] });
    const pending = new Map();
    const stopped = new Promise(resolve => browser.once('close', resolve));
    const sessions = new Map();
    let sequence = 0;
    let buffer = '';
    function failPending() {
        for (const entry of pending.values()) {
            clearTimeout(entry.timer);
            entry.reject(new Error('browser_disconnected'));
        }
        pending.clear();
    }
    browser.on('error', failPending);
    browser.on('exit', failPending);
    browser.stdio[3].on('error', failPending);
    browser.stdio[4].on('data', chunk => {
        buffer += chunk.toString();
        let end;
        while ((end = buffer.indexOf('\0')) >= 0) {
            const raw = buffer.slice(0, end);
            buffer = buffer.slice(end + 1);
            if (!raw) continue;
            const message = JSON.parse(raw);
            const entry = pending.get(message.id);
            if (entry) {
                clearTimeout(entry.timer);
                pending.delete(message.id);
                if (message.error) entry.reject(new Error('browser_command_failed'));
                else entry.resolve(message.result);
            }
            const state = sessions.get(message.sessionId);
            if (!state) continue;
            if (message.method === 'Runtime.exceptionThrown') state.exceptions++;
            if (message.method === 'Network.responseReceived' && message.params.type === 'Document'
                    && message.params.response.url === state.expectedUrl) {
                state.httpStatus = message.params.response.status;
            }
            if (message.method === 'Page.loadEventFired') state.loaded = true;
        }
    });
    function send(method, params = {}, sessionId) {
        return new Promise((resolve, reject) => {
            const id = ++sequence;
            const timer = setTimeout(() => {
                pending.delete(id);
                reject(new Error('browser_command_timeout'));
            }, 20000);
            pending.set(id, { resolve, reject, timer });
            browser.stdio[3].write(JSON.stringify({ id, method, params, sessionId }) + '\0');
        });
    }
    const report = { schema: 1, expectedSha, origin, sampledAt: new Date().toISOString(),
        inferenceCalls: 0, pages: [], result: 'FAIL' };
    const deadline = setTimeout(() => browser.kill('SIGKILL'), 150000);
    try {
        await send('Browser.getVersion');
        for (const viewport of [{ name: 'desktop', width: 1440, height: 1000 }, { name: 'mobile', width: 390, height: 844 }]) {
            for (const page of pages) {
                const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
                const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
                const state = { exceptions: 0, httpStatus: null, loaded: false, expectedUrl: origin + page.path };
                sessions.set(sessionId, state);
                await send('Page.enable', {}, sessionId);
                await send('Runtime.enable', {}, sessionId);
                await send('Network.enable', {}, sessionId);
                await send('Emulation.setDeviceMetricsOverride', { width: viewport.width, height: viewport.height,
                    deviceScaleFactor: 1, mobile: viewport.name === 'mobile' }, sessionId);
                const navigation = await send('Page.navigate', { url: origin + page.path }, sessionId);
                if (navigation.errorText) throw new Error('navigation_failed');
                const started = Date.now();
                while (!state.loaded && Date.now() - started < 20000) await new Promise(r => setTimeout(r, 100));
                if (!state.loaded) throw new Error('page_load_timeout');
                const { result, exceptionDetails } = await send('Runtime.evaluate', {
                    awaitPromise: true, returnByValue: true,
                    expression: `(async () => {
                        await document.fonts.ready;
                        const stop = Date.now() + 5000;
                        while ((document.body?.innerText.length || 0) < 40 && Date.now() < stop)
                            await new Promise(r => setTimeout(r, 100));
                        await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
                        const nav = performance.getEntriesByType('navigation')[0];
                        return { url: location.href, bodyLength: document.body.innerText.length,
                            markerFound: (${matchesMarker.toString()})(document.body.innerText, ${JSON.stringify(page.marker)}),
                            overflowPx: Math.max(0, document.documentElement.scrollWidth - innerWidth),
                            domContentLoadedMs: nav ? Math.round(nav.domContentLoadedEventEnd) : null,
                            loadEventMs: nav ? Math.round(nav.loadEventEnd) : null,
                            resources: performance.getEntriesByType('resource').length };
                    })()`,
                }, sessionId);
                if (exceptionDetails || !result.value) throw new Error('page_measurement_failed');
                const sample = { path: page.path, viewport: viewport.name, ...result.value,
                    httpStatus: state.httpStatus, exceptions: state.exceptions };
                Object.assign(sample, assess(sample));
                const screenshot = `${viewport.name}-${page.path === '/' ? 'home' : page.path.slice(1)}.png`;
                const capture = await send('Page.captureScreenshot', { format: 'png' }, sessionId);
                await writeFile(join(output, screenshot), Buffer.from(capture.data, 'base64'));
                sample.screenshot = screenshot;
                report.pages.push(sample);
                sessions.delete(sessionId);
                await send('Target.closeTarget', { targetId });
            }
        }
        report.result = report.pages.every(p => p.failures.length === 0) ? 'PASS' : 'FAIL';
    } catch (error) {
        // Fixed internal reason codes only: never persist browser console text or response bodies.
        report.error = /^[a-z_]+$/.test(error.message) ? error.message : 'qa_failed';
    } finally {
        clearTimeout(deadline);
        browser.kill('SIGKILL');
        failPending();
        await stopped;
        await rm(profile, { recursive: true, force: true });
        await writeFile(join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
    }
    console.log(JSON.stringify(report));
    if (report.result !== 'PASS') process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
    main().catch(() => { console.error('Staging QA setup failed'); process.exitCode = 1; });
}
