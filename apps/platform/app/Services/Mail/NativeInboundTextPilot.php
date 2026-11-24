<?php

declare(strict_types=1);

namespace App\Services\Mail;

use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

/**
 * Deliberately narrow plain-text pilot, not a general MIME parser or spam filter.
 * Complex, malformed, attachment-bearing and unverified envelope/header mismatch
 * messages stay in encrypted quarantine; they are never discarded or rendered.
 */
final class NativeInboundTextPilot
{
    public function publish(int $ownerId, string $event, string $recipient, string $envelopeSender, string $raw): bool
    {
        if (config('kmj-mail-inbound.publish_text') !== true) {
            return false;
        }

        $parsed = $this->parse($envelopeSender, $raw);
        if ($parsed === null) {
            return false;
        }

        // Caller holds the configured owner row lock and the quarantine insert
        // in the same transaction. A duplicate event is never promoted twice.
        $now = now();
        DB::table('kmj_mail_messages')->insert([
            'mailbox_user_id' => $ownerId,
            'sender_user_id' => null,
            'recipient_user_id' => $ownerId,
            'sender_email' => $parsed['sender'],
            'recipient_email' => $recipient,
            'thread_id' => (string) Str::uuid(),
            'folder' => 'inbox',
            'subject' => $parsed['subject'],
            'body' => $parsed['body'],
            'client_key' => $event,
            'delivery_state' => 'inbound_unverified',
            'read_at' => null,
            'created_at' => $now,
            'updated_at' => $now,
        ]);

        return true;
    }

    /** @return array{sender:string,subject:string,body:string}|null */
    public function parse(string $envelopeSender, string $raw): ?array
    {
        // Reject ambiguous line endings and NULs. Normalize CRLF only.
        if ($envelopeSender === '' || strlen($raw) > 262144
            || str_contains($raw, "\0") || preg_match('/\r(?!\n)/', $raw) === 1) {
            return null;
        }
        $message = str_replace("\r\n", "\n", $raw);
        $parts = explode("\n\n", $message, 2);
        if (count($parts) !== 2 || strlen($parts[0]) > 16384) {
            return null;
        }

        $headers = [];
        $unfolded = preg_replace('/\n[ \t]+/', ' ', $parts[0]);
        if ($unfolded === null) {
            return null;
        }
        foreach (explode("\n", $unfolded) as $line) {
            if (preg_match('/\A([A-Za-z0-9-]+):[ \t]*(.*)\z/D', $line, $matches) !== 1) {
                return null;
            }
            $name = strtolower($matches[1]);
            if (! in_array($name, ['from', 'subject', 'content-type', 'content-transfer-encoding', 'content-disposition'], true)) {
                continue;
            }
            if (isset($headers[$name])) {
                return null;
            }
            $headers[$name] = trim($matches[2]);
        }

        $from = $headers['from'] ?? '';
        if (preg_match('/\A[^<>]*<([^<>]+)>\z/D', $from, $matches) === 1) {
            $from = trim($matches[1]);
        }
        // This checks envelope/header consistency, NOT SPF/DKIM/DMARC.
        if (filter_var($from, FILTER_VALIDATE_EMAIL) === false
            || strlen($from) > 254 || strcasecmp($from, $envelopeSender) !== 0) {
            return null;
        }
        $type = $headers['content-type'] ?? 'text/plain';
        if (preg_match('/\Atext\/plain(?:\s*;\s*charset\s*=\s*"? (?:utf-8|us-ascii) "?)?\s*\z/ixD', $type) !== 1
            || (isset($headers['content-disposition']) && strtolower($headers['content-disposition']) !== 'inline')) {
            return null;
        }

        $body = $parts[1];
        $encoding = strtolower($headers['content-transfer-encoding'] ?? '7bit');
        if ($encoding === 'base64') {
            $decoded = base64_decode($body, true);
            if ($decoded === false) {
                return null;
            }
            $body = $decoded;
        } elseif ($encoding === 'quoted-printable') {
            $body = quoted_printable_decode($body);
        } elseif (! in_array($encoding, ['7bit', '8bit'], true)) {
            return null;
        }
        $body = trim(str_replace("\r\n", "\n", $body));
        $subject = trim(mb_decode_mimeheader($headers['subject'] ?? '(No subject)'));

        if (! mb_check_encoding($subject, 'UTF-8') || ! mb_check_encoding($body, 'UTF-8')
            || $subject === '' || mb_strlen($subject) > 180 || $body === '' || mb_strlen($body) > 12000
            || preg_match('/[\x00-\x1f\x7f]/', $subject) === 1
            || preg_match('/[\x00-\x08\x0b-\x1f\x7f]/', $body) === 1) {
            return null;
        }

        return ['sender' => strtolower($from), 'subject' => $subject, 'body' => $body];
    }
}
