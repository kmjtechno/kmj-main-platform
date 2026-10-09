import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REQUIRED = ['resources/css/app.css', 'resources/js/app.tsx'];
const OWNER_PAGE = 'resources/js/pages/operator-codebridge-owner.tsx';

function pageFiles(root, relative = 'resources/js/pages') {
    const dir = path.join(root, relative);
    if (!existsSync(dir)) throw new Error('PAGE_SOURCE_DIRECTORY_MISSING');
    const found = [];
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
        const candidate = path.posix.join(relative, entry.name);
        if (entry.isDirectory()) found.push(...pageFiles(root, candidate));
        else if (entry.isFile() && /\.(tsx|jsx)$/.test(entry.name)) found.push(candidate);
    }
    return found;
}

function assetPath(buildDir, relative) {
    if (typeof relative !== 'string' || !relative || relative.includes('\\') ||
        relative.startsWith('/') || relative.split('/').some(part => part === '..' || part === '.')) {
        throw new Error('UNSAFE_MANIFEST_ASSET_PATH');
    }
    const full = path.join(buildDir, relative);
    if (!existsSync(full) || !statSync(full).isFile()) throw new Error('MISSING_COMPILED_ASSET: ' + relative);
    return full;
}

export function verifyViteManifest(root) {
    const base = path.resolve(root);
    const buildDir = path.join(base, 'public', 'build');
    const file = path.join(buildDir, 'manifest.json');
    if (!existsSync(file)) throw new Error('VITE_MANIFEST_MISSING');
    let manifest;
    try {
        manifest = JSON.parse(readFileSync(file, 'utf8'));
    } catch {
        throw new Error('VITE_MANIFEST_INVALID_JSON');
    }
    if (!manifest || Array.isArray(manifest) || typeof manifest !== 'object') {
        throw new Error('VITE_MANIFEST_INVALID');
    }

    const pages = pageFiles(base);
    const absent = [...REQUIRED, OWNER_PAGE, ...pages]
        .filter((entry, i, list) => list.indexOf(entry) === i)
        .filter(entry => !Object.hasOwn(manifest, entry));
    if (absent.length) throw new Error('MISSING_VITE_ENTRYPOINTS: ' + absent.join(', '));

    let checkedFiles = 0;
    for (const [entry, record] of Object.entries(manifest)) {
        if (!record || typeof record !== 'object' || typeof record.file !== 'string') {
            throw new Error('INVALID_VITE_ENTRY: ' + entry);
        }
        assetPath(buildDir, record.file);
        checkedFiles += 1;
        for (const field of ['css', 'assets']) {
            if (record[field] === undefined) continue;
            if (!Array.isArray(record[field])) throw new Error('INVALID_MANIFEST_ARRAY: ' + field);
            for (const relative of record[field]) {
                assetPath(buildDir, relative);
                checkedFiles += 1;
            }
        }
        for (const field of ['imports', 'dynamicImports']) {
            if (record[field] === undefined) continue;
            if (!Array.isArray(record[field])) throw new Error('INVALID_MANIFEST_ARRAY: ' + field);
            for (const dependency of record[field]) {
                if (!Object.hasOwn(manifest, dependency)) throw new Error('UNRESOLVED_VITE_IMPORT: ' + dependency);
            }
        }
    }
    return { pages: pages.length, entries: Object.keys(manifest).length, assetsChecked: checkedFiles };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
    try {
        const result = verifyViteManifest(process.argv[2] ?? process.cwd());
        console.log('VITE_RELEASE_MANIFEST_PASS', JSON.stringify(result));
    } catch (error) {
        console.error('VITE_RELEASE_MANIFEST_FAIL', error instanceof Error ? error.message : String(error));
        process.exitCode = 1;
    }
}
