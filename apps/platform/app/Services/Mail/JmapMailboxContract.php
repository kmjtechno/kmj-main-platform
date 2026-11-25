<?php

declare(strict_types=1);

namespace App\Services\Mail;

use UnexpectedValueException;

/**
 * Pure, read-only JMAP session contract. No network, credentials or application routes.
 * A future user-scoped transport must authenticate before calling this boundary.
 */
final class JmapMailboxContract
{
    private const CORE = 'urn:ietf:params:jmap:core';

    private const MAIL = 'urn:ietf:params:jmap:mail';

    private const API = 'https://mail.kmjtechno.com/jmap';

    /**
     * @param  array<string, mixed>  $session
     * @return array{apiUrl: string, accountId: string}
     */
    public function primaryMailAccount(array $session): array
    {
        $url = $session['apiUrl'] ?? null;
        $capabilities = $session['capabilities'] ?? null;
        $primary = $session['primaryAccounts'] ?? null;
        $accounts = $session['accounts'] ?? null;

        if (! is_string($url) || ! in_array($url, [self::API, self::API.'/'], true)
            || ! is_array($capabilities) || ! is_array($primary) || ! is_array($accounts)
            || ! is_array($capabilities[self::CORE] ?? null)
            || ! is_array($capabilities[self::MAIL] ?? null)) {
            throw new UnexpectedValueException('Unsupported KMJ JMAP session.');
        }

        $account = $primary[self::MAIL] ?? null;
        if (! is_string($account) || preg_match('/\A[A-Za-z0-9_-]{1,128}\z/D', $account) !== 1) {
            throw new UnexpectedValueException('Missing primary KMJ mail account.');
        }

        $record = $accounts[$account] ?? null;
        if (! is_array($record) || ($record['isPersonal'] ?? null) !== true
            || ! is_array($record['accountCapabilities'] ?? null)
            || ! is_array($record['accountCapabilities'][self::MAIL] ?? null)) {
            throw new UnexpectedValueException('Unsupported KMJ mail account.');
        }

        return ['apiUrl' => $url, 'accountId' => $account];
    }

    /**
     * Build only the authenticated user's primary personal mailbox discovery request.
     * Shared accounts and writes require a separate reviewed authorization boundary.
     *
     * @param  array<string, mixed>  $session
     * @return array{using: list<string>, methodCalls: list<array{string, array{accountId: string, ids: null, properties: list<string>}, string}>}
     */
    public function mailboxGet(array $session): array
    {
        $account = $this->primaryMailAccount($session);

        return [
            'using' => [self::CORE, self::MAIL],
            'methodCalls' => [
                ['Mailbox/get', [
                    'accountId' => $account['accountId'],
                    'ids' => null,
                    'properties' => ['id', 'name', 'parentId', 'role', 'sortOrder', 'totalEmails', 'unreadEmails'],
                ], 'mailboxes'],
            ],
        ];
    }
}
