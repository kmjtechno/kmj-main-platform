import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import {
    formatIstClock,
    formatIstDate,
    formatIstDateTime,
    formatIstStamp,
} from '../resources/js/lib/format-ist-date-time.ts';

void test('dates are dd/mm/yyyy in India time regardless of host timezone', () => {
    // 2026-11-25 20:00 UTC is already 26 Nov 01:30 in India.
    assert.equal(formatIstDate('2026-11-25T20:00:00Z'), '26/11/2026');
    assert.equal(formatIstClock('2026-11-25T20:00:00Z'), '01:30:00');
    assert.equal(
        formatIstStamp('2026-11-25T20:00:00Z'),
        '26/11/2026 01:30:00 IST',
    );
    assert.equal(
        formatIstDateTime('2026-11-25T20:00:00Z'),
        '26/11/2026 01:30:00 IST',
    );
});

void test('zone-less server datetimes are read as UTC and bad input falls back', () => {
    assert.equal(
        formatIstStamp('2026-11-25 20:00:00'),
        '26/11/2026 01:30:00 IST',
    );
    assert.equal(formatIstDate(null), '—');
    assert.equal(formatIstDate('not a date', 'n/a'), 'n/a');
    assert.equal(formatIstClock(undefined), '');
    assert.equal(
        formatIstStamp(Date.parse('2026-11-25T20:00:00Z')),
        '26/11/2026 01:30:00 IST',
    );
});

void test('pages never format dates with browser-local toLocale date/time calls', () => {
    const offenders = [];
    const walk = (dir) => {
        for (const name of readdirSync(dir)) {
            const path = join(dir, name);
            if (statSync(path).isDirectory()) walk(path);
            else if (name.endsWith('.tsx')) {
                const source = readFileSync(path, 'utf8');
                if (/\.toLocale(Date|Time)String\(/.test(source))
                    offenders.push(path);
                if (/new Date\([^)]*\)\s*\.toLocaleString\(\)/.test(source))
                    offenders.push(path);
            }
        }
    };
    walk(new URL('../resources/js', import.meta.url).pathname);
    assert.deepEqual(offenders, []);
});
