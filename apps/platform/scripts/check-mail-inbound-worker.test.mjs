import assert from 'node:assert/strict';
import { createHash, createHmac } from 'node:crypto';
import test from 'node:test';
import worker from '../../../scripts/operations/kmj-mail-inbound-worker.mjs';

const recipient = 'mail-pilot@kmjtechno.com';
const sender = 'sender@example.net';
const secret = '0123456789abcdef'.repeat(4);
const env = { KMJ_MAIL_INBOUND_PILOT_SECRET_HEX: secret };
const raw = Buffer.from(
    'From: sender@example.net\r\nSubject: Pilot\r\n\r\nTest.',
);

function message(overrides = {}) {
    const rejections = [];
    return {
        to: recipient,
        from: sender,
        rawSize: raw.length,
        raw: new Response(raw).body,
        setReject: (reason) => rejections.push(reason),
        rejections,
        ...overrides,
    };
}

await test('worker HMAC binds exact raw MIME and accepts only durable receipts', async (t) => {
    const calls = [];
    t.mock.method(globalThis, 'fetch', async (url, options) => {
        calls.push(url);
        assert.equal(url, 'https://kmjtechno.com/api/kmj-mail/inbound/pilot');
        assert.equal(options.redirect, 'error');
        const h = options.headers;
        assert.equal(h['X-KMJ-Mail-Recipient'], recipient);
        assert.equal(h['X-KMJ-Mail-Envelope-From'], sender);
        assert.deepEqual(Buffer.from(options.body), raw);
        const signed = [
            'kmj-inbound-v1',
            h['X-KMJ-Mail-Event'],
            h['X-KMJ-Mail-Timestamp'],
            recipient,
            sender,
            createHash('sha256').update(raw).digest('hex'),
        ].join('\n');
        assert.equal(
            h['X-KMJ-Mail-Signature'],
            createHmac('sha256', Buffer.from(secret, 'hex'))
                .update(signed)
                .digest('hex'),
        );
        return Response.json(
            { state: calls.length === 1 ? 'quarantined' : 'duplicate' },
            { status: calls.length === 1 ? 201 : 200 },
        );
    });
    for (let index = 0; index < 2; index++) {
        const mail = message();
        await worker.email(mail, env);
        assert.deepEqual(mail.rejections, []);
    }
    assert.equal(calls.length, 2);
});

await test('worker rejects malformed metadata, size mismatch and broken stream before forwarding', async (t) => {
    const fetchMock = t.mock.method(globalThis, 'fetch', async () => {
        throw new Error('unexpected network');
    });
    const invalid = [
        message({ to: 'other@example.net' }),
        message({ rawSize: raw.length + 1 }),
        message({ rawSize: 1.5 }),
        message({ rawSize: 262145 }),
        message({ raw: new Response(new Uint8Array(262145)).body }),
        message({
            raw: new ReadableStream({
                start(controller) {
                    controller.error(new Error('synthetic broken stream'));
                },
            }),
        }),
    ];
    for (const mail of invalid) {
        await worker.email(mail, env);
        assert.equal(mail.rejections.length, 1);
    }
    const noSecret = message();
    await worker.email(noSecret, {});
    assert.equal(noSecret.rejections.length, 1);
    assert.equal(fetchMock.mock.callCount(), 0);
});

await test('worker rejects HTTP failures, invalid receipts and network errors', async (t) => {
    let attempt = 0;
    t.mock.method(globalThis, 'fetch', async () => {
        attempt++;
        if (attempt === 1) return new Response('unavailable', { status: 503 });
        if (attempt === 2)
            return Response.json({ state: 'unexpected' }, { status: 201 });
        if (attempt === 3) return new Response('not-json', { status: 200 });
        throw new Error('synthetic timeout');
    });
    for (let index = 0; index < 4; index++) {
        const mail = message();
        await worker.email(mail, env);
        assert.equal(mail.rejections.length, 1);
    }
});
