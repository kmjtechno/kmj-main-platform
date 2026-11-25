// Source-only Cloudflare Email Routing pilot. Do not deploy or add routing rules
// before the exact Elite receiver, storage, review and owner activation gates pass.
// The existing info@ routing is not a destination for this worker.

const RECIPIENT = 'mail-pilot@kmjtechno.com';
const ENDPOINT = 'https://kmjtechno.com/api/kmj-mail/inbound/pilot';
const MAX_BYTES = 262144;

function hex(bytes) {
    return Array.from(new Uint8Array(bytes), (byte) =>
        byte.toString(16).padStart(2, '0'),
    ).join('');
}

export default {
    async email(message, env) {
        if (
            message.to !== RECIPIENT ||
            message.rawSize <= 0 ||
            message.rawSize > MAX_BYTES ||
            !/^[0-9a-f]{64}$/.test(env.KMJ_MAIL_INBOUND_PILOT_SECRET_HEX ?? '')
        ) {
            message.setReject('KMJ pilot unavailable or message outside pilot limits');
            return;
        }

        const raw = await new Response(message.raw).arrayBuffer();
        if (raw.byteLength <= 0 || raw.byteLength > MAX_BYTES) {
            message.setReject('Message outside KMJ pilot size limit');
            return;
        }
        const event = crypto.randomUUID();
        const timestamp = String(Math.floor(Date.now() / 1000));
        const sender = message.from;
        const digest = hex(await crypto.subtle.digest('SHA-256', raw));
        const key = await crypto.subtle.importKey(
            'raw',
            Uint8Array.from(
                env.KMJ_MAIL_INBOUND_PILOT_SECRET_HEX.match(/../g),
                (pair) => parseInt(pair, 16),
            ),
            { name: 'HMAC', hash: 'SHA-256' },
            false,
            ['sign'],
        );
        const signed = [
            'kmj-inbound-v1',
            event,
            timestamp,
            RECIPIENT,
            sender,
            digest,
        ].join('\n');
        const signature = hex(
            await crypto.subtle.sign(
                'HMAC',
                key,
                new TextEncoder().encode(signed),
            ),
        );
        try {
            const response = await fetch(ENDPOINT, {
                method: 'POST',
                redirect: 'error',
                signal: AbortSignal.timeout(10000),
                headers: {
                    'Content-Type': 'message/rfc822',
                    'X-KMJ-Mail-Event': event,
                    'X-KMJ-Mail-Timestamp': timestamp,
                    'X-KMJ-Mail-Recipient': RECIPIENT,
                    'X-KMJ-Mail-Envelope-From': sender,
                    'X-KMJ-Mail-Signature': signature,
                },
                body: raw,
            });
            if (response.status === 200 || response.status === 201) {
                const receipt = await response.json();
                if (
                    (response.status === 201 && receipt.state === 'quarantined') ||
                    (response.status === 200 && receipt.state === 'duplicate')
                ) {
                    return;
                }
            }
        } catch {
            // Never log addresses, MIME, signatures, credentials or response bodies.
        }
        message.setReject('KMJ pilot could not durably accept the message');
    },
};
