#!/usr/bin/env node
/**
 * KMJ local-first, opt-in, read-only sensor.
 *
 * Runs ON the paired CodeBridge device (P720 or the approved Linux agent).
 * It never sends prompts, tokens in logs, raw tasks, filesystem paths or
 * customer code. HTTPS uploads only small counts to fixed KMJ Main Platform.
 * No inference, model downloads, paid APIs or agent restart.
 *
 * node scripts/codebridge-local-telemetry.mjs /path/to/private/agent.json
 * node scripts/codebridge-local-telemetry.mjs /path/to/private/agent.json --watch
 */
import { readFileSync, lstatSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as sleep } from 'node:timers/promises';

const DESTINATION = 'https://kmjtechno.com/api/codebridge/v1/telemetry';
const MODEL = /^[A-Za-z0-9._:/-]{1,96}$/;
const PROJECT = /^[A-Za-z0-9_-]{1,64}$/;
const PORTS = Object.freeze([11434, 11435, 11436]);

function readPrivateJson(file, limit) {
    const s = lstatSync(file);
    if (!s.isFile() || s.isSymbolicLink() || s.size > limit || s.size < 2)
        throw new Error('TELEMETRY_LOCAL_SOURCE_UNSAFE');
    return JSON.parse(readFileSync(file, 'utf8'));
}

export function readQueue(stateDir, projectId) {
    try {
        const body = readPrivateJson(join(stateDir, 'autopilot', 'state.json'), 2_097_152);
        if (![1, 2].includes(body.version) || !Array.isArray(body.tasks) || body.tasks.length > 500)
            return null;
        const result = { queued: 0, running: 0, waiting: 0 };
        for (const task of body.tasks) {
            if (!task || typeof task.project !== 'string' || !PROJECT.test(task.project) ||
                !['queued', 'running', 'waiting', 'failed', 'succeeded', 'cancelled'].includes(task.state))
                return null;
            if (task.project === projectId && Object.hasOwn(result, task.state))
                result[task.state] += 1;
        }
        return result;
    } catch {
        // A missing/corrupt journal is unknown, never a made-up zero.
        return null;
    }
}

export async function readOllama(fetcher = fetch) {
    const models = new Set();
    let reachable = false;
    for (const port of PORTS) {
        try {
            const response = await fetcher('http://127.0.0.1:' + port + '/api/tags', {
                signal: AbortSignal.timeout(1_200),
                redirect: 'error',
                headers: { Accept: 'application/json' },
            });
            if (!response.ok || Number(response.headers.get('content-length') ?? 0) > 65536)
                continue;
            // Cap the parsed size even if the daemon omits Content-Length.
            const text = await response.text();
            if (text.length > 65536) continue;
            const payload = JSON.parse(text);
            if (!Array.isArray(payload.models)) continue;
            reachable = true;
            for (const item of payload.models) {
                if (typeof item?.name === 'string' && MODEL.test(item.name))
                    models.add(item.name);
                if (models.size >= 5) break;
            }
        } catch {
            // Local-only probe may be offline; do not contact a cloud fallback.
        }
    }
    return { reachable, models: [...models].slice(0, 5) };
}

function privateAgent(file) {
    const config = readPrivateJson(resolve(file), 131072);
    if (!config || typeof config !== 'object' || !Array.isArray(config.projects)
        || config.projects.length !== 1 || !PROJECT.test(config.projects[0]?.id)
        || !PROJECT.test(config.id) || !PROJECT.test(config.tenant)
        || typeof config.token !== 'string' || config.token.length < 32
        || typeof config.stateDir !== 'string' || !config.stateDir) {
        throw new Error('INVALID_SCOPED_CODEBRIDGE_AGENT');
    }
    return config;
}

export async function reportOnce(agentConfigFile, fetcher = fetch) {
    const config = privateAgent(agentConfigFile);
    const observation = {
        project_id: config.projects[0].id,
        ollama: await readOllama(fetcher),
    };
    const queue = readQueue(config.stateDir, observation.project_id);
    if (queue !== null) observation.queue = queue;

    const response = await fetcher(DESTINATION, {
        method: 'POST',
        redirect: 'error',
        signal: AbortSignal.timeout(4_000),
        headers: {
            Authorization: 'Bearer ' + config.token,
            'Content-Type': 'application/json',
            Accept: 'application/json',
        },
        body: JSON.stringify(observation),
    });
    if (response.status !== 202) throw new Error('TELEMETRY_UPLOAD_NOT_ACCEPTED');
    return { accepted: true, project: observation.project_id, queueSampled: queue !== null };
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
    const [file, mode] = process.argv.slice(2);
    if (!file || (mode !== undefined && mode !== '--watch')) {
        console.error('Usage: node codebridge-local-telemetry.mjs <private-agent-config> [--watch]');
        process.exitCode = 2;
    } else {
        const run = async () => {
            try {
                const status = await reportOnce(file);
                console.log('CodeBridge local telemetry acknowledged for ' + status.project);
            } catch {
                // Deliberately omit secrets, file paths, task names, and payloads.
                console.error('CodeBridge local telemetry unavailable (no agent data published).');
                process.exitCode = 1;
            }
        };
        if (mode === '--watch') {
            while (true) {
                await run();
                await sleep(45_000);
            }
        } else {
            await run();
        }
    }
}
