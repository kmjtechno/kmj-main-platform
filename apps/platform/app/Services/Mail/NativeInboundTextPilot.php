<?php

declare(strict_types=1);

namespace App\Services\Mail;

use Illuminate\Support\Facades\DB;

/**
 * Bounded text projection, not a general MIME parser or spam filter.
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
        DB::table('kmj_mail_external_inbox')->insert([
            'mailbox_user_id' => $ownerId,
            'sender_email' => $parsed['sender'],
            'recipient_email' => $recipient,
            'subject' => $parsed['subject'],
            'body' => $parsed['body'],
            'event_id' => $event,
            'read_at' => null,
            'created_at' => $now,
            'updated_at' => $now,
        ]);

        return true;
    }

    /**
     * @return array{total:int,unread:int,matching:int,items:list<array{id:int,sender:string,subject:string,at:string,unread:bool}>,selected:array{id:int,sender:string,recipient:string,subject:string,body:string,at:string}|null}
     */
    public function inbox(int $ownerId, string $search, ?int $selectedId): array
    {
        $scope = DB::table('kmj_mail_external_inbox')->where('mailbox_user_id', $ownerId);
        $selected = null;
        if ($selectedId !== null) {
            $row = (clone $scope)->where('id', $selectedId)->first();
            abort_if($row === null, 404);
            (clone $scope)->where('id', $selectedId)->whereNull('read_at')
                ->update(['read_at' => now(), 'updated_at' => now()]);
            $selected = [
                'id' => (int) $row->id,
                'sender' => (string) $row->sender_email,
                'recipient' => (string) $row->recipient_email,
                'subject' => (string) $row->subject,
                'body' => (string) $row->body,
                'at' => (string) $row->created_at,
            ];
        }

        $matching = clone $scope;
        if ($search !== '') {
            $escaped = addcslashes($search, '%_\\');
            $matching->where(function ($query) use ($escaped): void {
                $query->where('subject', 'like', '%'.$escaped.'%')
                    ->orWhere('sender_email', 'like', '%'.$escaped.'%')
                    ->orWhere('body', 'like', '%'.$escaped.'%');
            });
        }

        return [
            'total' => (int) (clone $scope)->count(),
            'unread' => (int) (clone $scope)->whereNull('read_at')->count(),
            'matching' => (int) (clone $matching)->count(),
            'items' => array_values($matching->orderByDesc('id')->limit(40)
                ->get(['id', 'sender_email', 'subject', 'created_at', 'read_at'])
                ->map(static fn (object $row): array => [
                    'id' => (int) $row->id,
                    'sender' => (string) $row->sender_email,
                    'subject' => (string) $row->subject,
                    'at' => (string) $row->created_at,
                    'unread' => $row->read_at === null,
                ])->all()),
            'selected' => $selected,
        ];
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

        $headers = $this->headers($parts[0]);
        if ($headers === null) {
            return null;
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
        $body = $this->plainAlternative($headers, $parts[1]);
        if ($body === null) {
            return null;
        }
        $subject = trim(mb_decode_mimeheader($headers['subject'] ?? '(No subject)'));

        if (! mb_check_encoding($subject, 'UTF-8') || ! mb_check_encoding($body, 'UTF-8')
            || $subject === '' || mb_strlen($subject) > 180 || $body === '' || mb_strlen($body) > 12000
            || preg_match('/[\x00-\x1f\x7f]/', $subject) === 1
            || preg_match('/[\x00-\x08\x0b-\x1f\x7f]/', $body) === 1) {
            return null;
        }

        return ['sender' => strtolower($from), 'subject' => $subject, 'body' => $body];
    }

    /** @return array<string, string>|null */
    private function headers(string $block): ?array
    {
        if (strlen($block) > 16384) {
            return null;
        }
        $headers = [];
        $unfolded = preg_replace('/\n[ \t]+/', ' ', $block);
        if ($unfolded === null) {
            return null;
        }
        foreach (explode("\n", $unfolded) as $line) {
            if (preg_match('/\A([A-Za-z0-9-]+):[ \t]*(.*)\z/D', $line, $matches) !== 1) {
                return null;
            }
            $name = strtolower($matches[1]);
            if (! in_array($name, ['from', 'subject', 'content-type', 'content-transfer-encoding', 'content-disposition'], true)) {
                // Unknown Content-* semantics could describe attachments.
                if (str_starts_with($name, 'content-')) {
                    return null;
                }

                continue;
            }
            if (isset($headers[$name])) {
                return null;
            }
            $headers[$name] = trim($matches[2]);
        }

        return $headers;
    }

    /** @param array<string, string> $headers */
    private function plainAlternative(array $headers, string $body): ?string
    {
        $type = $headers['content-type'] ?? 'text/plain';
        if (isset($headers['content-disposition']) && strtolower($headers['content-disposition']) !== 'inline') {
            return null;
        }
        if ($this->isTextType($type, 'plain')) {
            return $this->decodeText($headers, $body);
        }
        if (config('kmj-mail-inbound.publish_alternative') !== true
            || ! in_array(strtolower($headers['content-transfer-encoding'] ?? '7bit'), ['7bit', '8bit'], true)
            || preg_match('/\Amultipart\/alternative[ \t]*;[ \t]*boundary[ \t]*=[ \t]*(?:"([A-Za-z0-9_=+.-]{1,70})"|([A-Za-z0-9_=+.-]{1,70}))[ \t]*\z/iD', $type, $matches) !== 1) {
            return null;
        }

        // Exactly two non-nested alternatives, in the common plain/HTML order.
        // Never parse, decode, execute or expose the HTML alternative.
        $boundary = $matches[1] !== '' ? $matches[1] : $matches[2];
        $open = '--'.$boundary;
        $close = $open.'--';
        $parts = [];
        $current = null;
        $closed = false;
        foreach (explode("\n", $body) as $line) {
            if ($closed) {
                if (trim($line) !== '') {
                    return null;
                }

                continue;
            }
            if ($line === $open || $line === $close) {
                if ($current !== null) {
                    $parts[] = implode("\n", $current);
                }
                if ($line === $close) {
                    $closed = true;
                    $current = null;
                } else {
                    $current = [];
                }
                if (count($parts) > 2) {
                    return null;
                }

                continue;
            }
            if ($current !== null) {
                $current[] = $line;
            }
        }
        if (! $closed || count($parts) !== 2) {
            return null;
        }

        $plain = null;
        foreach ($parts as $index => $part) {
            $split = explode("\n\n", $part, 2);
            if (count($split) !== 2) {
                return null;
            }
            $partHeaders = $this->headers($split[0]);
            if ($partHeaders === null
                || isset($partHeaders['from']) || isset($partHeaders['subject'])
                || (isset($partHeaders['content-disposition']) && strtolower($partHeaders['content-disposition']) !== 'inline')
                || ! $this->isTextType($partHeaders['content-type'] ?? '', $index === 0 ? 'plain' : 'html')
                || ! in_array(strtolower($partHeaders['content-transfer-encoding'] ?? '7bit'), ['7bit', '8bit', 'base64', 'quoted-printable'], true)) {
                return null;
            }
            if ($index === 0) {
                $plain = $this->decodeText($partHeaders, $split[1]);
            }
        }

        return $plain;
    }

    private function isTextType(string $type, string $subtype): bool
    {
        return preg_match('/\Atext\/'.$subtype.'(?:\s*;\s*charset\s*=\s*(?:"(?:utf-8|us-ascii)"|(?:utf-8|us-ascii)))?\s*\z/iD', $type) === 1;
    }

    /** @param array<string, string> $headers */
    private function decodeText(array $headers, string $body): ?string
    {
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

        return trim(str_replace("\r\n", "\n", $body));
    }
}
