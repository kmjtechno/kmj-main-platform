import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash, generateKeyPairSync, sign } from 'node:crypto';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { buildReceipt } from './P520-OFFSITE-SIGNED-RESTORE-RECEIPT-20261116.mjs';

// Synthetic-only keys and receipts. No real P520 key, archive, owner approval,
// production SHA publication, Docker execution or remote restore in CI.
const CANDIDATE = 'bd8975f0ee888a26013a6669e687db540f39f440';
const LEGACY = '4c9d59103b99a6cfe675bb7b8961fc956eb294f0';
const CURRENT = 'platform-ce6ad7dc9d89';
const CIPHER = 'a'.repeat(64);
const SOURCE = 'b'.repeat(64);
const VERIFIER = 'scripts/operations/verify-p520-independent-restore-v2-20261118.py';

function syntheticReceipt(change = () => {}) {
    const payload = {
        ...buildReceipt(CIPHER, SOURCE, 441334),
        candidateSha: CANDIDATE,
        completedAtUtc: new Date().toISOString(),
    };
    change(payload);
    return Buffer.from(JSON.stringify(payload), 'utf8');
}
function check(receipt, overrides = {}) {
    const temp = mkdtempSync(join(tmpdir(), 'kmj-p520-candidate-v2-'));
    try {
        const pair = generateKeyPairSync('ed25519');
        const pub = Buffer.from(pair.publicKey.export({ format: 'pem', type: 'spki' }));
        const payload = overrides.duplicate
            ? Buffer.from(
                receipt.toString().replace(
                    '"candidateSha":"' + CANDIDATE + '"',
                    '"candidateSha":"' + LEGACY + '","candidateSha":"' + CANDIDATE + '"',
                ),
            )
            : receipt;
        const sig = sign(null, payload, pair.privateKey);
        const files = {
            receipt: join(temp, 'receipt.json'),
            signature: join(temp, 'receipt.sig'),
            pub: join(temp, 'owner-test.pub.pem'),
        };
        writeFileSync(files.receipt, overrides.tamper ? Buffer.concat([payload, Buffer.from(' ')]) : payload);
        writeFileSync(files.signature, overrides.badSignature ? Buffer.alloc(64) : sig);
        writeFileSync(files.pub, pub);
        const args = [
            VERIFIER,
            '--receipt', files.receipt,
            '--signature', files.signature,
            '--owner-pinned-public-key', files.pub,
            '--expected-key-sha256',
            overrides.keySha ?? createHash('sha256').update(pub).digest('hex'),
            '--encrypted-sha256', CIPHER,
            '--source-local-sha256', SOURCE,
            '--expected-candidate-sha', overrides.expectedCandidate ?? CANDIDATE,
            '--expected-current-release', overrides.expectedRelease ?? CURRENT,
        ];
        return spawnSync('python3', args, { encoding: 'utf8', timeout: 15000 });
    } finally {
        rmSync(temp, { recursive: true, force: true });
    }
}
test('V2 verifier accepts only exact SHA-bound synthetic Ed25519 receipt without granting release', () => {
    const result = check(syntheticReceipt());
    assert.equal(result.status, 0, result.stderr + result.stdout);
    assert.match(result.stdout, /KMJ_P520_RECEIPT=CRYPTO_VALIDATED/);
    assert.match(result.stdout, new RegExp('CANDIDATE_SHA=' + CANDIDATE));
    assert.match(result.stdout, /INDEPENDENT_OPERATOR_REVIEW=REQUIRED/);
    assert.match(result.stdout, /PRODUCTION_APPROVAL=NOT_GRANTED/);
});
test('legacy 4C9 valid signed restore cannot satisfy new Licensing Hub candidate', () => {
    const result = check(syntheticReceipt(o => { o.candidateSha = LEGACY; }));
    assert.equal(result.status, 2);
    assert.match(result.stdout, /BLOCKED_RECOVERY_IDENTITY_OR_DIGEST/);
});
test('valid Ed25519 signature is insufficient if trusted caller expects another candidate or release', () => {
    for (const overrides of [
        { expectedCandidate: LEGACY },
        { expectedCandidate: 'not-a-sha' },
        { expectedRelease: 'platform-111111111111' },
        { expectedRelease: 'platform-' + CANDIDATE.slice(0, 12) },
        { expectedRelease: 'invalid release' },
    ]) {
        const result = check(syntheticReceipt(), overrides);
        assert.equal(result.status, 2, JSON.stringify(overrides));
        assert.match(result.stdout, /BLOCKED_/);
    }
});
test('invalid proof signature, tampered payload and wrong owner public-key pin fail closed', () => {
    for (const overrides of [
        { badSignature: true },
        { tamper: true },
        { keySha: '0'.repeat(64) },
        { duplicate: true },
    ]) {
        const result = check(syntheticReceipt(), overrides);
        assert.equal(result.status, 2, JSON.stringify(overrides));
        assert.match(result.stdout, /BLOCKED_/);
    }
});
test('stale/future receipt, wrong cipher, and forged proof flag are rejected', () => {
    for (const change of [
        o => { o.completedAtUtc = '2026-01-01T00:00:00.000Z'; },
        o => { o.completedAtUtc = '2099-01-01T00:00:00.000Z'; },
        o => { o.encryptedSha256 = 'f'.repeat(64); },
        o => { o.isolatedPostgresRestoreVerified = false; },
    ]) {
        const result = check(syntheticReceipt(change));
        assert.equal(result.status, 2);
        assert.match(result.stdout, /BLOCKED_/);
    }
});
test('verifier without required operator-pinned candidate cannot run', () => {
    const result = spawnSync('python3', [VERIFIER, '--help'], { encoding: 'utf8', timeout: 15000 });
    assert.equal(result.status, 0);
    assert.match(result.stdout, /--expected-candidate-sha/);
    assert.match(result.stdout, /--expected-current-release/);
});
