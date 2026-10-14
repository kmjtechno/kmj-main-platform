import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { readOllama, readQueue, reportOnce } from './codebridge-local-telemetry.mjs';

test('autopilot queue is taken from a real bounded local journal', () => {
    const root = mkdtempSync(join(tmpdir(), 'kmj-telemetry-'));
    try {
        mkdirSync(join(root, 'autopilot'));
        writeFileSync(join(root, 'autopilot', 'state.json'), JSON.stringify({
            version: 2,
            missions: [],
            tasks: [
                { project: 'kmj-main-platform', state: 'queued' },
                { project: 'kmj-main-platform', state: 'running' },
                { project: 'kmj-main-platform', state: 'waiting' },
                { project: 'another-project', state: 'queued' },
            ],
        }));
        assert.deepEqual(readQueue(root, 'kmj-main-platform'), {
            queued: 1, running: 1, waiting: 1,
        });
        assert.deepEqual(readQueue(root, 'another-project'), {
            queued: 1, running: 0, waiting: 0,
        });
        writeFileSync(join(root, 'autopilot', 'state.json'), '{bad-json');
        assert.equal(readQueue(root, 'kmj-main-platform'), null);
    } finally {
        rmSync(root, { recursive: true, force: true });
    }
});

test('Ollama probes fixed loopback ports only; unknown model strings are dropped', async () => {
    const seen = [];
    const result = await readOllama(async (url) => {
        seen.push(url);
        return {
            ok: true,
            headers: { get: () => null },
            text: async () => JSON.stringify({
                models: [{ name: 'qwen3:4b' }, { name: 'unsafe token=secret' }],
            }),
        };
    });
    assert.deepEqual(seen, [11434, 11435, 11436].map((port) =>
        'http://127.0.0.1:' + port + '/api/tags'));
    assert.deepEqual(result, { reachable: true, models: ['qwen3:4b'] });
});

test('device credential never enters posted payload and no unknown hosts are contacted', async () => {
    const root = mkdtempSync(join(tmpdir(), 'kmj-telemetry-'));
    try {
        const config = join(root, 'agent.json');
        const token = 'Q'.repeat(48);
        writeFileSync(config, JSON.stringify({
            id: 'p720-agent', tenant: 'tenant-a', token, stateDir: root,
            projects: [{ id: 'kmj-main-platform' }],
        }));
        const calls = [];
        const result = await reportOnce(config, async (url, options) => {
            calls.push({ url, options });
            if (url.endsWith('/api/tags'))
                throw new Error('No local Ollama service');
            return { status: 202 };
        });
        assert.equal(result.accepted, true);
        assert.equal(result.queueSampled, false);
        assert.equal(calls.length, 4);
        assert.equal(calls[3].url, 'https://kmjtechno.com/api/codebridge/v1/telemetry');
        const payload = JSON.parse(calls[3].options.body);
        assert.deepEqual(payload, {
            project_id: 'kmj-main-platform',
            ollama: { reachable: false, models: [] },
        });
        assert.ok(!calls[3].options.body.includes(token));
        assert.equal(calls[3].options.headers.Authorization, 'Bearer ' + token);
    } finally {
        rmSync(root, { recursive: true, force: true });
    }
});

test('authenticated dashboard route is tenant-limited; no fake status fixtures', () => {
    const web = readFileSync('routes/web.php', 'utf8');
    const api = readFileSync('routes/codebridge-telemetry-api.php', 'utf8');
    const browser = readFileSync('resources/js/components/codebridge/live-telemetry-card.tsx', 'utf8');
    assert.match(web, /require __DIR__.'\/codebridge-telemetry.php'/);
    assert.match(api, /c.token_hash/);
    assert.match(api, /whereNull\('c.revoked_at'\)/);
    assert.match(api, /hash_equals/);
    assert.match(browser, /Not reported/);
    assert.match(browser, /45_000/);
    assert.match(browser, /border-slate-700\/70 bg-slate-950/);
    assert.match(browser, /text-red-500/);
    assert.doesNotMatch(browser, /activeDevices: 4|queuedTasks: 15|fleetStatus: 'OPERATIONAL'/);
});
