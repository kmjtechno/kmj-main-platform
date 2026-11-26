import { spawnSync } from 'node:child_process';
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));

export function skipPattern(names) {
    const escaped = names.map((name) =>
        name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'),
    );
    return escaped.length === 0 ? null : `^(${escaped.join('|')})$`;
}

export function run() {
    const { names } = JSON.parse(
        readFileSync(join(here, 'known-failing-source-tests.json'), 'utf8'),
    );
    const files = readdirSync(here)
        .filter((f) => /^check-.*\.test\.mjs$/.test(f))
        .map((f) => join(here, f));
    const pattern = skipPattern(names);
    const args = [
        '--test',
        ...(pattern ? [`--test-skip-pattern=${pattern}`] : []),
        ...files,
    ];
    return spawnSync(process.execPath, args, { stdio: 'inherit' }).status ?? 1;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
    process.exit(run());
}
