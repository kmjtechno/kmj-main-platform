// CI-only driver: runs the REAL kmj-codebridge WorkspaceJobWorker + JobRunner against a live
// Main Platform (artisan serve) on a disposable database. No mocks of either side.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const [dir, origin, credential] = process.argv.slice(2);
if (process.env.GITHUB_ACTIONS !== 'true' || !dir || !origin || !credential) {
    console.error('BLOCKED: CI-only driver');
    process.exit(2);
}
const load = (f) => import(pathToFileURL(path.join(dir, 'src', f)).href);
const { JobRunner } = await load('jobs.js');
const { WorkspaceJobWorker } = await load('workspace-job-worker.js');

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'cb-roundtrip-'));
const root = path.join(tmp, 'repo');
fs.mkdirSync(root);
const git = (...a) => execFileSync('git', ['-C', root, ...a], { encoding: 'utf8' });
git('init', '-q', '-b', 'main');
git('config', 'user.email', 'ci@example.test');
git('config', 'user.name', 'ci');
fs.writeFileSync(path.join(root, 'a.txt'), 'a');
git('add', '.');
git('commit', '-q', '-m', 'init');

const runner = new JobRunner(path.join(tmp, 'jobs'), { archiveMaxEntries: 50 });
const project = {
    id: process.env.WORKER_PROJECT_ID ?? 'ci-roundtrip-proj',
    root,
    writable: true,
    gates: {
        fast: { command: process.execPath, args: ['-e', 'process.exit(0)'], timeoutMs: 20000 },
    },
    workspaceJobs: {
        enabled: true,
        tools: ['git_status', 'inspect_project', 'quality_gate'],
        gates: ['fast'],
        requireCleanCheckout: true,
    },
};
let delivered = 0;
const countingFetch = async (url, init) => {
    const res = await fetch(url, init);
    if (String(url).endsWith('/api/codebridge/v1/jobs/claim')) {
        const body = await res.clone().json();
        if (body.job) delivered += 1;
    }
    return res;
};
const statuses = [];
const worker = new WorkspaceJobWorker({
    origin,
    credential,
    projects: [project],
    runner,
    licenseProvider: () => ({ features: ['read', 'write', 'execute'] }),
    fetchImpl: countingFetch,
    onStatus: (s) => statuses.push(s),
});
const expected = Number(process.env.EXPECTED_JOBS ?? 3);
const deadline = Date.now() + Number(process.env.WORKER_DEADLINE_MS ?? 90_000);
// STOP_FILE (UI e2e): keep serving until the browser run is over, because the number of requests a
// real browser queues can vary with render timing; otherwise stop at the expected count.
const stopFile = process.env.STOP_FILE;
const finished = () => (stopFile ? fs.existsSync(stopFile) : delivered >= expected);
while (!finished() && Date.now() < deadline) {
    await worker.tick();
    await new Promise((r) => setTimeout(r, 400));
}
// One more tick proves the queue is drained and the worker idles.
await worker.tick();
await runner.close();
fs.rmSync(tmp, { recursive: true, force: true });
console.log(`WORKER_JOBS_DELIVERED=${delivered} STATUSES=${JSON.stringify(statuses)}`);
process.exit(stopFile ? (delivered >= expected ? 0 : 1) : delivered === expected ? 0 : 1);
