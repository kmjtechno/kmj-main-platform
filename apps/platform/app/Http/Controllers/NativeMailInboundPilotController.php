<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\User;
use App\Services\Mail\NativeInboundTextPilot;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;

final class NativeMailInboundPilotController
{
    public function __invoke(Request $request, PlatformOwnerAccess $ownerAccess): JsonResponse
    {
        abort_unless(config('kmj-mail-inbound.enabled') === true, 404);
        $secret = config('kmj-mail-inbound.secret_hex');
        $ownerId = (int) config('kmj-mail-inbound.owner_id');
        $recipient = (string) config('kmj-mail-inbound.recipient');
        abort_unless(is_string($secret) && preg_match('/\A[0-9a-f]{64}\z/D', $secret) === 1
            && $ownerId > 0 && $recipient === 'mail-pilot@kmjtechno.com', 503);

        abort_unless($request->header('Content-Type') === 'message/rfc822', 415);
        $raw = $request->getContent();
        abort_unless(strlen($raw) > 0 && strlen($raw) <= 262144, 413);

        $event = (string) $request->header('X-KMJ-Mail-Event');
        $timestamp = (string) $request->header('X-KMJ-Mail-Timestamp');
        $to = (string) $request->header('X-KMJ-Mail-Recipient');
        $from = (string) $request->header('X-KMJ-Mail-Envelope-From');
        $signature = (string) $request->header('X-KMJ-Mail-Signature');
        abort_unless(
            preg_match('/\A[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\z/D', $event) === 1
            && preg_match('/\A[0-9]{10}\z/D', $timestamp) === 1
            && abs(now()->getTimestamp() - (int) $timestamp) <= 300
            && $to === $recipient
            && strlen($from) <= 254
            && ($from === '' || filter_var($from, FILTER_VALIDATE_EMAIL) !== false)
            && preg_match('/[\x00-\x20\x7f]/', $from) !== 1
            && preg_match('/\A[0-9a-f]{64}\z/D', $signature) === 1,
            401,
        );

        $key = hex2bin($secret);
        abort_unless(is_string($key), 503);

        $digest = hash('sha256', $raw);
        $signed = implode("\n", ['kmj-inbound-v1', $event, $timestamp, $to, $from, $digest]);
        abort_unless(hash_equals(hash_hmac('sha256', $signed, $key), $signature), 401);

        return DB::transaction(function () use ($ownerId, $ownerAccess, $event, $recipient, $from, $raw, $digest): JsonResponse {
            $owner = User::query()->whereKey($ownerId)->lockForUpdate()->first();
            abort_unless($owner !== null && $ownerAccess->allows($owner), 403);

            $query = DB::table('kmj_mail_inbound_quarantine');
            $prior = (clone $query)->where('event_id', $event)->first();
            if ($prior !== null) {
                abort_unless((int) $prior->mailbox_user_id === $ownerId
                    && $prior->recipient === $recipient && $prior->raw_sha256 === $digest, 409);

                return $this->receipt('duplicate', 200);
            }

            $mailbox = (clone $query)->where('mailbox_user_id', $ownerId);
            if ((clone $mailbox)->where('recipient', $recipient)->where('raw_sha256', $digest)->exists()) {
                return $this->receipt('duplicate', 200);
            }

            // Pilot capacity is deliberately bounded; reject rather than silently discard.
            abort_if((clone $mailbox)->count() >= 1000
                || (clone $mailbox)->where('received_at', '>=', now()->subDay())->count() >= 100, 429);

            $query->insert([
                'mailbox_user_id' => $ownerId,
                'event_id' => $event,
                'recipient' => $recipient,
                'raw_sha256' => $digest,
                'raw_bytes' => strlen($raw),
                'encrypted_envelope_sender' => Crypt::encryptString($from),
                'encrypted_mime' => Crypt::encryptString($raw),
                'received_at' => now(),
            ]);

            // The separately gated text-only pilot can publish one safe Inbox copy.
            // The raw original always remains in encrypted quarantine.
            app(NativeInboundTextPilot::class)->publish($ownerId, $event, $recipient, $from, $raw);

            // This receipt confirms durable quarantine, not verified sender identity.
            return $this->receipt('quarantined', 201);
        });
    }

    private function receipt(string $state, int $status): JsonResponse
    {
        return response()->json(['state' => $state], $status)->header('Cache-Control', 'no-store, private');
    }
}
