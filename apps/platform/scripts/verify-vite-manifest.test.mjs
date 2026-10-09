import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { verifyViteManifest } from './verify-vite-manifest.mjs';

function fixture(t) {
    const root = mkdtempSync(path.join(tmpdir(), 'kmj-vite-guard-'));
    t.after(() => rmSync(root, { recursive: true, force: true }));
    const put = (name, content = '') => {
        const full = path.join(root, name);
        mkdirSync(path.dirname(full), { recursive: true });
        writeFileSync(full, content);
    };
    const manifest = {
        'resources/css/app.css': { file: 'assets/app-123.css', isEntry: true },
        'resources/js/app.tsx': { file: 'assets/app-123.js', isEntry: true, imports: ['_vendor.js'] },
        'resources/js/pages/welcome.tsx': { file: 'assets/home-123.js', isDynamicEntry: true },
        'resources/js/pages/operator-codebridge-owner.tsx': { file: 'assets/owner-123.js', isDynamicEntry: true },
        '_vendor.js': { file: 'assets/vendor-123.js' },
    };
    for (const key of Object.keys(manifest)) {
        if (key.startsWith('resources/js/pages/')) put(key, 'export default function Page(){}');
        put('public/build/' + manifest[key].file, 'test');
    }
    put('public/build/manifest.json', JSON.stringify(manifest));
    put('resources/js/app.tsx', 'import React from "react"');
    put('resources/css/app.css', ':root {}');
    return { root, put, manifest };
}

void test('checks every source page, the owner page and every compiled asset', t => {
    const f = fixture(t);
    assert.deepEqual(verifyViteManifest(f.root), { pages: 2, entries: 5, assetsChecked: 5 });
});

void test('rejects the exact owner-page omission that caused production HTTP 500', t => {
    const f = fixture(t);
    delete f.manifest['resources/js/pages/operator-codebridge-owner.tsx'];
    f.put('public/build/manifest.json', JSON.stringify(f.manifest));
    assert.throws(() => verifyViteManifest(f.root), /MISSING_VITE_ENTRYPOINTS.*operator-codebridge-owner/);
});

void test('rejects a newly introduced source page absent from the build', t => {
    const f = fixture(t);
    f.put('resources/js/pages/new-feature.tsx', 'export default function Feature(){}');
    assert.throws(() => verifyViteManifest(f.root), /MISSING_VITE_ENTRYPOINTS.*new-feature/);
});

void test('rejects absent compiled assets, invalid import keys and unsafe paths', t => {
    const f = fixture(t);
    f.manifest['resources/js/pages/welcome.tsx'].file = 'assets/missing.js';
    f.put('public/build/manifest.json', JSON.stringify(f.manifest));
    assert.throws(() => verifyViteManifest(f.root), /MISSING_COMPILED_ASSET/);
    f.manifest['resources/js/pages/welcome.tsx'].file = '../private/secret.js';
    f.put('public/build/manifest.json', JSON.stringify(f.manifest));
    assert.throws(() => verifyViteManifest(f.root), /UNSAFE_MANIFEST_ASSET_PATH/);
    f.manifest['resources/js/pages/welcome.tsx'].file = 'assets/home-123.js';
    f.manifest['resources/js/app.tsx'].imports = ['_missing.js'];
    f.put('public/build/manifest.json', JSON.stringify(f.manifest));
    assert.throws(() => verifyViteManifest(f.root), /UNRESOLVED_VITE_IMPORT/);
});

void test('rejects malformed or missing manifest', t => {
    const f = fixture(t);
    f.put('public/build/manifest.json', '{oops');
    assert.throws(() => verifyViteManifest(f.root), /VITE_MANIFEST_INVALID_JSON/);
});
