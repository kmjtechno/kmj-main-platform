import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

// Guards the owner navigation against drift: the dashboard sidebar
// (operator-command-os) and the module shell (owner-module-shell) keep
// separate lists, and a label pointing at different pages in each caused the
// "Communication opens the wrong page" bug.
const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');
const dashboard = read('../resources/js/components/operator-command-os.tsx');
const shell = read('../resources/js/layouts/owner-module-shell.tsx');

const dashboardItems = new Map(
    [...dashboard.matchAll(/\[\s*'([^']+)',\s*'([^']+)',\s*\w+,?\s*\]/g)].map(
        (m) => [m[1], m[2]],
    ),
);
const shellItems = new Map(
    [...shell.matchAll(/label:\s*'([^']+)',\s*href:\s*'([^']+)'/g)].map((m) => [
        m[1],
        m[2],
    ]),
);

// On /super-admin the revenue panel is an in-page anchor.
const normalise = (href) => href.replace('/super-admin#', '#');

void test('labels present in both navs point to the same destination', () => {
    const shared = [...dashboardItems.keys()].filter((l) => shellItems.has(l));
    assert.ok(shared.length >= 15, 'expected the shared owner nav labels');
    for (const label of shared) {
        assert.equal(
            normalise(shellItems.get(label)),
            normalise(dashboardItems.get(label)),
            `${label} differs between dashboard and module shell`,
        );
    }
});

void test('Communication opens the native mail page in both navs', () => {
    assert.equal(dashboardItems.get('Communication (Mail)'), '/operator/mail');
    assert.equal(shellItems.get('Communication (Mail)'), '/operator/mail');
});

void test('revenue anchor targets a page that owns it', () => {
    assert.match(dashboard, /id="owner-revenue"/);
    assert.equal(
        shellItems.get('Revenue & Analytics'),
        '/super-admin#owner-revenue',
    );
});
