<?php

declare(strict_types=1);

namespace App\Services\Mail;

use UnexpectedValueException;

/**
 * Pure read-only Inbox summary contract. IDs must originate from a validated
 * Email/query response in the same authenticated session, never browser input.
 */
final class JmapInboxMetadata
{
    private const PROPERTIES = ['id', 'threadId', 'receivedAt', 'subject', 'from', 'keywords', 'hasAttachment'];

    /**
     * @param  array<string, mixed>  $session
     * @param  list<string>  $ids
     * @return array<string, mixed>
     */
    public function request(array $session, array $ids): array
    {
        $this->validateIds($ids);
        $account = (new JmapMailboxContract)->primaryMailAccount($session);

        return [
            'using' => ['urn:ietf:params:jmap:core', 'urn:ietf:params:jmap:mail'],
            'methodCalls' => [
                ['Email/get', [
                    'accountId' => $account['accountId'],
                    'ids' => $ids,
                    'properties' => self::PROPERTIES,
                ], 'inbox-metadata'],
            ],
        ];
    }

    /**
     * @param  array<string, mixed>  $session
     * @param  list<string>  $ids
     * @param  array<string, mixed>  $response
     * @return array{messages: list<array<string, mixed>>, missing: list<string>}
     */
    public function parse(array $session, array $ids, array $response): array
    {
        $this->validateIds($ids);
        $account = (new JmapMailboxContract)->primaryMailAccount($session);
        $calls = $response['methodResponses'] ?? null;
        if (! is_array($calls) || ! array_is_list($calls) || count($calls) !== 1) {
            throw new UnexpectedValueException('Invalid KMJ Inbox metadata response.');
        }
        $call = $calls[0];
        if (! is_array($call) || ! array_is_list($call) || count($call) !== 3
            || $call[0] !== 'Email/get' || $call[2] !== 'inbox-metadata' || ! is_array($call[1])) {
            throw new UnexpectedValueException('Invalid KMJ Inbox metadata method.');
        }
        $data = $call[1];
        $list = $data['list'] ?? null;
        $missing = $data['notFound'] ?? null;
        if (($data['accountId'] ?? null) !== $account['accountId']
            || ! is_string($data['state'] ?? null)
            || ! is_array($list) || ! array_is_list($list)
            || ! is_array($missing) || ! array_is_list($missing)
            || count($list) + count($missing) !== count($ids)) {
            throw new UnexpectedValueException('Invalid KMJ Inbox metadata page.');
        }

        $this->validateIds($missing);
        $messages = [];
        foreach ($list as $entry) {
            if (! is_array($entry) || ! $this->validId($entry['id'] ?? null)
                || ! in_array($entry['id'], $ids, true)
                || isset($messages[$entry['id']]) || in_array($entry['id'], $missing, true)
                || ! $this->validId($entry['threadId'] ?? null)
                || ! $this->validDate($entry['receivedAt'] ?? null)
                || ! is_bool($entry['hasAttachment'] ?? null)) {
                throw new UnexpectedValueException('Invalid KMJ Inbox message metadata.');
            }
            $subject = $this->boundedText($entry['subject'] ?? null, 4096, true);
            $from = $entry['from'] ?? null;
            if ($from !== null && (! is_array($from) || ! array_is_list($from) || count($from) > 20)) {
                throw new UnexpectedValueException('Invalid KMJ Inbox sender metadata.');
            }
            $senders = [];
            foreach ($from ?? [] as $sender) {
                if (! is_array($sender)) {
                    throw new UnexpectedValueException('Invalid KMJ Inbox sender.');
                }
                $senders[] = [
                    'name' => $this->boundedText($sender['name'] ?? null, 1024, true),
                    'email' => $this->boundedText($sender['email'] ?? null, 320, false),
                ];
            }
            $keywords = $entry['keywords'] ?? null;
            if (! is_array($keywords) || count($keywords) > 128) {
                throw new UnexpectedValueException('Invalid KMJ Inbox keywords.');
            }
            foreach ($keywords as $keyword => $value) {
                if (! is_string($keyword) || $keyword === '' || strlen($keyword) > 255 || $value !== true) {
                    throw new UnexpectedValueException('Invalid KMJ Inbox keyword.');
                }
            }
            $messages[$entry['id']] = [
                'id' => $entry['id'],
                'threadId' => $entry['threadId'],
                'receivedAt' => $entry['receivedAt'],
                'subject' => $subject,
                'from' => $senders,
                'isRead' => isset($keywords['$seen']),
                'isFlagged' => isset($keywords['$flagged']),
                'hasAttachment' => $entry['hasAttachment'],
            ];
        }
        $ordered = [];
        $orderedMissing = [];
        foreach ($ids as $id) {
            if (isset($messages[$id])) {
                $ordered[] = $messages[$id];
            } elseif (in_array($id, $missing, true)) {
                $orderedMissing[] = $id;
            } else {
                throw new UnexpectedValueException('Incomplete KMJ Inbox metadata coverage.');
            }
        }

        return ['messages' => $ordered, 'missing' => $orderedMissing];
    }

    /** @param  array<mixed>  $ids */
    private function validateIds(array $ids): void
    {
        if (! array_is_list($ids) || count($ids) > JmapInboxQuery::PAGE_SIZE) {
            throw new UnexpectedValueException('Invalid KMJ Inbox metadata identifiers.');
        }
        $seen = [];
        foreach ($ids as $id) {
            if (! $this->validId($id) || in_array($id, $seen, true)) {
                throw new UnexpectedValueException('Invalid KMJ Inbox metadata identifier.');
            }
            $seen[] = $id;
        }
    }

    private function validId(mixed $value): bool
    {
        return is_string($value) && preg_match('/\A[A-Za-z0-9_-]{1,128}\z/D', $value) === 1;
    }

    private function validDate(mixed $value): bool
    {
        return is_string($value)
            && preg_match('/\A(\d{4})-(\d{2})-(\d{2})T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,9})?Z\z/D', $value, $parts) === 1
            && checkdate((int) $parts[2], (int) $parts[3], (int) $parts[1]);
    }

    private function boundedText(mixed $value, int $limit, bool $nullable): ?string
    {
        if ($value === null && $nullable) {
            return null;
        }
        if (! is_string($value) || strlen($value) > $limit || (! $nullable && $value === '')
            || preg_match('//u', $value) !== 1 || preg_match('/[\x00-\x1F\x7F]/', $value) === 1) {
            throw new UnexpectedValueException('Invalid KMJ Inbox display metadata.');
        }

        return $value;
    }
}
