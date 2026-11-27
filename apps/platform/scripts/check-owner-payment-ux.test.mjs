/** Owner Payment Gateway visual QA. Source-only, no account or gateway requests. */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (path) => readFileSync(resolve(root, path), 'utf8');
const page = read('resources/js/pages/operator-payments.tsx');
const css = read('resources/css/owner-payments-premium.css');
const onboarding = read(
    'resources/js/components/payment-gateway-onboarding.tsx',
);
const settings = read('resources/js/components/operator-payment-settings.tsx');

const gitBlobHash = (source) =>
    createHash('sha1')
        .update('blob ' + Buffer.byteLength(source) + '\0')
        .update(source)
        .digest('hex');

void test('real owner Payment Gateway page opts into owner-only design scope', () => {
    assert.match(page, /import '\.\.\/\.\.\/css\/owner-payments-premium\.css'/);
    assert.match(page, /kmj-admin-shell kmj-owner-payments/);
    assert.match(page, /<PaymentGatewayOnboarding/);
    assert.match(page, /<OperatorPaymentSettings/);
});

void test('layout fills owner workspace without changing customer-facing styles', () => {
    assert.match(css, /\.owner-module-shell \.kmj-owner-payments/);
    assert.match(css, /\.kmj-owner-payments \.max-w-6xl/);
    assert.match(css, /max-width: none;/);
    assert.doesNotMatch(css, /^(?:html|body)\s*\{/m);
    assert.doesNotMatch(css, /(?<!\.)\b:root\s*\{/);
});

void test('readable, keyboard accessible and responsive locked enterprise UI', () => {
    assert.match(css, /font-size: 14px/);
    assert.match(css, /min-height: 44px/);
    assert.match(css, /:focus-visible/);
    assert.match(css, /@media \(max-width: 850px\)/);
    assert.match(css, /prefers-reduced-motion/);
    assert.match(css, /--kmj-pay-card: var\(--card\)/);
    assert.doesNotMatch(
        css,
        /#[0-9a-fA-F]{6}\b/,
        'use shared admin tokens, not private colors',
    );
});

void test('payment security state and live charging guard stay real', () => {
    assert.match(page, /paymentReadiness\.live_charging_enabled/);
    assert.match(
        page,
        /Live charging disabled until reconciled end-to-end tests pass/,
    );
    assert.match(page, /live_transaction_verified/);
    assert.match(page, /sandbox_credentials_present/);
});

void test('sandbox probe and credential lifecycle files remain pinned (onboarding hash re-pinned only to link the webhook secret generator; settings hash only for the browser-autofill guard)', () => {
    assert.equal(
        gitBlobHash(onboarding),
        '6af2bacb25f4b7fcf6381c99f4f54ff542b65e0c',
    );
    assert.equal(
        gitBlobHash(settings),
        '8be41ac29e5b2b17c9107333f4e36cf135cb03b9',
    );
});

void test('sandbox probe remains guarded by real stored keys', () => {
    assert.match(onboarding, /if \(!keysSaved \|\| probe\.processing\) return/);
    assert.match(onboarding, /test-connection/);
    assert.match(onboarding, /webhookSecretSaved/);
});

void test('payment secrets remain test-only with explicit owner revocation', () => {
    assert.match(settings, /TEST MODE ONLY/);
    assert.match(settings, /Store sandbox keys in encrypted server storage/);
    assert.match(settings, /window\.confirm/);
    assert.match(settings, /\/credentials/);
});

void test('credential fields never invite browser login autofill', () => {
    const settings = read(
        'resources/js/components/operator-payment-settings.tsx',
    );
    assert.match(settings, /new-password/);
    assert.match(settings, /data-1p-ignore/);
    assert.match(settings, /name=\{`gateway_\$\{key\}`\}/);
    assert.doesNotMatch(settings, /name=\{key\}/);
});

void test('webhook guide prevents the known Live-mode, empty-secret and wrong-key mistakes', () => {
    const guide = read('resources/js/components/webhook-setup-guide.tsx');
    assert.match(guide, /Test Mode toggle ON/);
    assert.match(guide, /never receives test payments/);
    assert.match(guide, /2023-08-01/);
    assert.match(guide, /Batch Resend/);
    assert.match(guide, /Cashfree signs with your Secret/);
});
