<?php

declare(strict_types=1);

namespace App\Services\Mail;

use UnexpectedValueException;

/**
 * Pure read-only query and response boundary. Never accept a mailbox ID from
 * browser input. The mailbox response must come from the same authenticated session.
 */
final class JmapInboxQuery
{
    public const PAGE_SIZE = 40;

    /**
     * @param  array<string, mixed>  $session
     * @param  array<string, mixed>  $mailboxResponse
     * @return array{using: list<string>, methodCalls: list<array{string, array{accountId: string, filter: array{inMailbox: string}, sort: list<array{property: string, isAscending: bool}>, position: int, limit: int, calculateTotal: bool}, string}>}
     */
    public function request(array $session, array $mailboxResponse, int $position = 0): array
    {
        if ($position < 0 || $position > 40000) {
            throw new UnexpectedValueException('Invalid KMJ Inbox position.');
        }

        $account = (new JmapMailboxContract)->primaryMailAccount($session);
        $inboxes = array_values(array_filter(
            (new JmapMailboxResponse)->parse($session, $mailboxResponse),
            static fn (array $mailbox): bool => $mailbox['role'] === 'inbox',
        ));
        if (count($inboxes) !== 1) {
            throw new UnexpectedValueException('Unique KMJ Inbox unavailable.');
        }

        return [
            'using' => ['urn:ietf:params:jmap:core', 'urn:ietf:params:jmap:mail'],
            'methodCalls' => [
                ['Email/query', [
                    'accountId' => $account['accountId'],
                    'filter' => ['inMailbox' => $inboxes[0]['id']],
                    'sort' => [['property' => 'receivedAt', 'isAscending' => false]],
                    'position' => $position,
                    'limit' => self::PAGE_SIZE,
                    'calculateTotal' => true,
                ], 'inbox-query'],
            ],
        ];
    }

    /**
     * @param  array<string, mixed>  $session
     * @param  array<string, mixed>  $response
     * @return array{ids: list<string>, position: int, total: int}
     */
    public function parse(array $session, array $response, int $position = 0): array
    {
        $account = (new JmapMailboxContract)->primaryMailAccount($session);
        $calls = $response['methodResponses'] ?? null;
        if ($position < 0 || $position > 40000 || ! is_array($calls)
            || ! array_is_list($calls) || count($calls) !== 1) {
            throw new UnexpectedValueException('Invalid KMJ Inbox result.');
        }

        $call = $calls[0];
        if (! is_array($call) || ! array_is_list($call) || count($call) !== 3
            || $call[0] !== 'Email/query' || $call[2] !== 'inbox-query' || ! is_array($call[1])) {
            throw new UnexpectedValueException('Invalid KMJ Inbox method.');
        }

        $data = $call[1];
        $ids = $data['ids'] ?? null;
        $total = $data['total'] ?? null;
        if (($data['accountId'] ?? null) !== $account['accountId']
            || ($data['position'] ?? null) !== $position
            || ! is_string($data['queryState'] ?? null)
            || ! is_int($total) || $total < 0
            || ! is_array($ids) || ! array_is_list($ids) || count($ids) > self::PAGE_SIZE
            || count($ids) > max(0, $total - $position)) {
            throw new UnexpectedValueException('Invalid KMJ Inbox page.');
        }

        $validated = [];
        foreach ($ids as $id) {
            if (! is_string($id) || preg_match('/\A[A-Za-z0-9_-]{1,128}\z/D', $id) !== 1
                || in_array($id, $validated, true)) {
                throw new UnexpectedValueException('Invalid KMJ Inbox message identifier.');
            }
            $validated[] = $id;
        }

        return ['ids' => $validated, 'position' => $position, 'total' => $total];
    }
}
