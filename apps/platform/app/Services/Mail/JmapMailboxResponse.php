<?php

declare(strict_types=1);

namespace App\Services\Mail;

use UnexpectedValueException;

/**
 * Validate a decoded response from an authenticated, bounded transport.
 * Mailbox names are plain text, not trusted HTML.
 */
final class JmapMailboxResponse
{
    private const MAX_MAILBOXES = 5000;

    /**
     * @param  array<string, mixed>  $session
     * @param  array<string, mixed>  $response
     * @return list<array{id: string, name: string, parentId: ?string, role: ?string, sortOrder: int, totalEmails: int, unreadEmails: int}>
     */
    public function parse(array $session, array $response): array
    {
        $account = (new JmapMailboxContract)->primaryMailAccount($session);
        $calls = $response['methodResponses'] ?? null;
        if (! is_array($calls) || ! array_is_list($calls) || count($calls) !== 1) {
            throw new UnexpectedValueException('Unexpected KMJ mailbox response.');
        }

        $call = $calls[0];
        if (! is_array($call) || ! array_is_list($call) || count($call) !== 3
            || $call[0] !== 'Mailbox/get' || $call[2] !== 'mailboxes' || ! is_array($call[1])) {
            throw new UnexpectedValueException('Unexpected KMJ mailbox method.');
        }

        $payload = $call[1];
        $list = $payload['list'] ?? null;
        if (($payload['accountId'] ?? null) !== $account['accountId']
            || ! is_string($payload['state'] ?? null)
            || ($payload['notFound'] ?? null) !== []
            || ! is_array($list) || ! array_is_list($list) || count($list) > self::MAX_MAILBOXES) {
            throw new UnexpectedValueException('Invalid KMJ mailbox result.');
        }

        $result = [];
        $seen = [];
        foreach ($list as $mailbox) {
            if (! is_array($mailbox)) {
                throw new UnexpectedValueException('Invalid KMJ mailbox record.');
            }

            $id = $mailbox['id'] ?? null;
            $name = $mailbox['name'] ?? null;
            $parent = $mailbox['parentId'] ?? null;
            $role = $mailbox['role'] ?? null;
            $order = $mailbox['sortOrder'] ?? null;
            $total = $mailbox['totalEmails'] ?? null;
            $unread = $mailbox['unreadEmails'] ?? null;

            if (! is_string($id) || ! $this->validId($id) || isset($seen[$id])
                || ! is_string($name) || $name === '' || strlen($name) > 1024
                || ! array_key_exists('parentId', $mailbox) || ! array_key_exists('role', $mailbox)
                || ($parent !== null && (! is_string($parent) || ! $this->validId($parent) || $parent === $id))
                || ($role !== null && (! is_string($role) || strlen($role) > 128))
                || ! is_int($order) || $order < 0 || ! is_int($total) || $total < 0
                || ! is_int($unread) || $unread < 0 || $unread > $total) {
                throw new UnexpectedValueException('Invalid KMJ mailbox metadata.');
            }

            $seen[$id] = true;
            $result[] = [
                'id' => $id,
                'name' => $name,
                'parentId' => $parent,
                'role' => $role,
                'sortOrder' => $order,
                'totalEmails' => $total,
                'unreadEmails' => $unread,
            ];
        }

        return $result;
    }

    private function validId(string $id): bool
    {
        return preg_match('/\A[A-Za-z0-9_-]{1,128}\z/D', $id) === 1;
    }
}
