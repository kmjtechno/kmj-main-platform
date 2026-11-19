/**
 * Audit the shipped browser-runtime dependency boundary without suppressing
 * the upstream full build-toolchain advisory. KSLP deployment remains blocked
 * until protected owner approvals and independent restore pass separately.
 *
 * This assertion is NOT a replacement for npm's advisory database scan.
 * It demonstrates that the dependencies flagged by the current Vite/globbing
 * advisory are not reachable from a production-omit-dev installation.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';

const app = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const manifest = JSON.parse(
    readFileSync(path.join(app, 'package.json'), 'utf8'),
);
const lock = JSON.parse(
    readFileSync(path.join(app, 'package-lock.json'), 'utf8'),
);
const pkgs = lock.packages;

assert.equal(lock.lockfileVersion, 3);
assert.deepEqual(pkgs[''].dependencies, manifest.dependencies);
assert.deepEqual(pkgs[''].devDependencies, manifest.devDependencies);
assert.deepEqual(pkgs[''].optionalDependencies, manifest.optionalDependencies);

const buildOnly = [
    '@inertiajs/vite',
    '@tailwindcss/vite',
    '@vitejs/plugin-react',
    '@types/react',
    '@types/react-dom',
    'concurrently',
    'laravel-vite-plugin',
    'tailwindcss',
    'tw-animate-css',
    'typescript',
    'vite',
];

for (const name of buildOnly) {
    assert.equal(
        typeof manifest.devDependencies[name],
        'string',
        name + ' must be a declared build-only dependency',
    );
    assert.equal(
        manifest.dependencies[name],
        undefined,
        name + ' must not be considered a production runtime dependency',
    );
}

function resolveDependency(from, name) {
    let here = from;
    while (here !== '') {
        const nested = here + '/node_modules/' + name;
        if (Object.hasOwn(pkgs, nested)) return nested;
        const index = here.lastIndexOf('/node_modules/');
        if (index === -1) break;
        here = here.slice(0, index);
    }
    const hoisted = 'node_modules/' + name;
    return Object.hasOwn(pkgs, hoisted) ? hoisted : null;
}

const queue = [
    ...Object.keys(manifest.dependencies),
    ...Object.keys(manifest.optionalDependencies ?? {}),
].map((name) => ['node_modules/' + name, name]);
const visited = new Set();
const vulnerablePaths = [];

for (let index = 0; index < queue.length; index++) {
    const [id, ancestry] = queue[index];
    if (!Object.hasOwn(pkgs, id)) {
        throw new Error(
            'Missing production dependency in lockfile: ' + ancestry,
        );
    }
    if (visited.has(id)) continue;
    visited.add(id);
    if (pkgs[id].dev) {
        throw new Error(
            'Production dependency incorrectly marked dev: ' + ancestry,
        );
    }
    // devOptional nodes can also be optional peer dependencies of a
    // production-optional package. npm's actual omit=dev install and advisory
    // scanner remain the authority for whether those are installed.
    if (id.endsWith('/picomatch')) {
        vulnerablePaths.push(ancestry);
    }

    const node = pkgs[id];
    // Include optional AND peer dependencies conservatively. If a new package
    // adds a picomatch peer edge, fail closed until reviewed rather than
    // relying on one specific npm Arborist installation layout.
    const required = node.dependencies ?? {};
    const optional = { ...node.optionalDependencies, ...node.peerDependencies };
    for (const dependency of Object.keys({ ...required, ...optional })) {
        const next = resolveDependency(id, dependency);
        if (!next) {
            if (Object.hasOwn(required, dependency)) {
                throw new Error(
                    'Unresolved required dependency: ' +
                        ancestry +
                        ' > ' +
                        dependency,
                );
            }
            // Peer/optional packages may legitimately be absent from a
            // platform-specific lockfile (e.g. Vue peers of a React app).
            continue;
        }
        queue.push([next, ancestry + ' > ' + dependency]);
    }
}

assert.deepEqual(
    vulnerablePaths,
    [],
    'Unpatched picomatch appears in the runtime dependency closure',
);
for (const id of Object.keys(pkgs).filter((p) => p.endsWith('/picomatch'))) {
    assert.equal(
        pkgs[id].dev,
        true,
        'picomatch remains installed in the build toolchain, not in shipped production dependencies: ' +
            id,
    );
}
console.log('KMJ_RUNTIME_NODE_DEPENDENCY_BOUNDARY=PASS');
console.log('RUNTIME_LOCKED_DEPENDENCIES=' + visited.size);
console.log('PUBLISHABLE_FULL_BUILD_SECURITY_AUDIT_PASS=NOT_CLAIMED');
console.log('PICOMATCH_BUILD_TOOLCHAIN_ADVISORY=UNRESOLVED');
